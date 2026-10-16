"""Tests for the receipt OCR pipeline.

Covers: mock mode, preprocessing, text cleaning, validation, and the
end-to-end read_receipt flow (with LLM mocked out).
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas import CatalogueItem, ReceiptItem, ReceiptResponse
from app.services.receipt_reader import _clean_ocr_text, _validate, read_receipt


# ---------------------------------------------------------------------------
# OCR text cleaning
# ---------------------------------------------------------------------------

class TestCleanOcrText:
    def test_removes_junk_characters(self):
        assert "hello world" == _clean_ocr_text("hello |||| world")
        assert "hello world" == _clean_ocr_text("hello ____ world")

    def test_normalises_naira_symbols(self):
        assert _clean_ocr_text("N#50,000") == "₦50,000"
        assert _clean_ocr_text("N=120,000") == "₦120,000"

    def test_preserves_line_structure(self):
        text = "Line1\n\nLine2\n\n\n\nLine3"
        cleaned = _clean_ocr_text(text)
        assert "Line1\n\nLine2\n\nLine3" == cleaned

    def test_collapses_excessive_spaces(self):
        assert "Rice  85,000" == _clean_ocr_text("Rice      85,000")

    def test_empty_string(self):
        assert "" == _clean_ocr_text("")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_no_items_warning(self):
        resp = ReceiptResponse(items=[], confidence=0.8)
        _validate(resp)
        assert any("No items" in w for w in resp.warnings)
        assert resp.confidence <= 0.2

    def test_total_mismatch_warning(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=10, unit_price=85_000, line_total=850_000),
                ReceiptItem(name="Oil", quantity=20, unit_price=20_000, line_total=400_000),
            ],
            total=1_500_000,  # Wrong: should be 1,250,000
            confidence=0.8,
        )
        _validate(resp)
        assert any("Items add up to" in w for w in resp.warnings)
        assert resp.confidence <= 0.6

    def test_line_arithmetic_warning(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=10, unit_price=85_000, line_total=900_000),  # 10*85k=850k ≠ 900k
            ],
            confidence=0.8,
        )
        _validate(resp)
        assert any("quantity × price" in w for w in resp.warnings)

    def test_suspicious_low_price(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=10, unit_price=2, line_total=20),  # ₦2 per bag?
            ],
            confidence=0.8,
        )
        _validate(resp)
        assert any("too low" in w for w in resp.warnings)

    def test_suspicious_high_price(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=1, unit_price=100_000_000, line_total=100_000_000),
            ],
            confidence=0.8,
        )
        _validate(resp)
        assert any("too high" in w for w in resp.warnings)

    def test_duplicate_items_warning(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=10, unit_price=85_000, line_total=850_000),
                ReceiptItem(name="Rice", quantity=5, unit_price=85_000, line_total=425_000),
            ],
            confidence=0.8,
        )
        _validate(resp)
        assert any("duplicate" in w.lower() for w in resp.warnings)

    def test_valid_receipt_no_warnings(self):
        resp = ReceiptResponse(
            items=[
                ReceiptItem(name="Rice", quantity=10, unit_price=85_000, line_total=850_000),
                ReceiptItem(name="Oil", quantity=20, unit_price=20_000, line_total=400_000),
            ],
            total=1_250_000,
            confidence=0.8,
        )
        _validate(resp)
        assert resp.warnings == []
        assert resp.confidence == 0.8


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_mode():
    with patch("app.services.receipt_reader.settings") as mock_settings:
        mock_settings.ocr_backend = "mock"
        resp = await read_receipt(b"fake-image-bytes", [])
    assert resp.supplier == "ABC Distributors"
    assert len(resp.items) == 3
    assert resp.total == 1_430_000
    assert resp.confidence > 0.5
    assert "3 items" in resp.confirmation_message


# ---------------------------------------------------------------------------
# Product matching integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_product_matching_on_receipt():
    catalogue = [
        CatalogueItem(id="p1", name="Premium Rice 50kg"),
        CatalogueItem(id="p2", name="Vegetable Oil"),
    ]
    with patch("app.services.receipt_reader.settings") as mock_settings:
        mock_settings.ocr_backend = "mock"
        resp = await read_receipt(b"fake-image-bytes", catalogue)
    # Rice should match Premium Rice, Oil should match Vegetable Oil.
    matched_ids = {i.matched_product_id for i in resp.items if i.matched_product_id}
    assert "p1" in matched_ids or "p2" in matched_ids  # at least one match


# ---------------------------------------------------------------------------
# OCR + LLM flow (LLM mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_with_llm_structuring():
    """Test the full pipeline with a fake OCR output and mocked LLM response."""
    fake_ocr_result = ("ABC Distributors\nRice  10 bags  85,000  850,000\nTotal: 850,000", 0.85)
    fake_llm_response = {
        "supplier": "ABC Distributors",
        "items": [{"name": "Rice", "quantity": 10, "unit": "bag", "unit_price": 85000, "line_total": 850000}],
        "total": 850000,
    }

    with patch("app.services.receipt_reader.settings") as mock_settings, \
         patch("app.services.receipt_reader._run_ocr", return_value=fake_ocr_result), \
         patch("app.services.receipt_reader.chat_json", new_callable=AsyncMock, return_value=fake_llm_response):
        mock_settings.ocr_backend = "tesseract"
        resp = await read_receipt(b"fake-image-bytes", [])

    assert resp.supplier == "ABC Distributors"
    assert len(resp.items) == 1
    assert resp.items[0].name == "Rice"
    assert resp.items[0].quantity == 10
    assert resp.total == 850_000
    assert resp.warnings == []


@pytest.mark.asyncio
async def test_ocr_with_llm_unavailable():
    """When the LLM is down, we still return the raw OCR text."""
    from app.services.llm import LLMUnavailable

    fake_ocr_result = ("Some receipt text", 0.7)

    with patch("app.services.receipt_reader.settings") as mock_settings, \
         patch("app.services.receipt_reader._run_ocr", return_value=fake_ocr_result), \
         patch("app.services.receipt_reader.chat_json", new_callable=AsyncMock, side_effect=LLMUnavailable("test")):
        mock_settings.ocr_backend = "tesseract"
        resp = await read_receipt(b"fake-image-bytes", [])

    assert "LLM unavailable" in resp.warnings[0]
    assert "Some receipt text" in resp.raw_text


@pytest.mark.asyncio
async def test_empty_ocr_returns_warning():
    """When OCR reads nothing, return a helpful warning."""
    fake_ocr_result = ("", 0.0)

    with patch("app.services.receipt_reader.settings") as mock_settings, \
         patch("app.services.receipt_reader._run_ocr", return_value=fake_ocr_result):
        mock_settings.ocr_backend = "tesseract"
        resp = await read_receipt(b"fake-image-bytes", [])

    assert any("could not read" in w.lower() for w in resp.warnings)
    assert resp.confidence <= 0.1
