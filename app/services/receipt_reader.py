"""Receipt/invoice photo -> structured items.

OCR pipeline (controlled by OCR_BACKEND env var):
  mock       -> returns the demo invoice (frontend/backend integration).
  tesseract  -> image preprocessing + pytesseract OCR + LLM structuring.
  easyocr    -> image preprocessing + EasyOCR + LLM structuring.

The pipeline:
  1. Preprocess the image (grayscale, denoise, contrast, deskew, binarize).
  2. Run OCR (Tesseract or EasyOCR) to extract raw text.
  3. Send the OCR text to the LLM to parse into structured JSON.
  4. Match product names against the merchant's catalogue.
  5. Validate (cross-check line totals, flag issues for the merchant).
"""
import io
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.schemas import CatalogueItem, ReceiptItem, ReceiptResponse
from app.services.llm import LLMUnavailable, chat_json
from app.services.product_matcher import match_product
from app.utils.naira import fmt_naira

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "receipt.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

def _mock_receipt() -> ReceiptResponse:
    return ReceiptResponse(
        supplier="ABC Distributors",
        items=[
            ReceiptItem(name="Rice", quantity=10, unit="bag", unit_price=85_000, line_total=850_000),
            ReceiptItem(name="Oil", quantity=20, unit="carton", unit_price=20_000, line_total=400_000),
            ReceiptItem(name="Milk", quantity=15, unit="carton", unit_price=12_000, line_total=180_000),
        ],
        total=1_430_000,
        confidence=0.9,
        raw_text="(mock receipt)",
    )


# ---------------------------------------------------------------------------
# OCR backends
# ---------------------------------------------------------------------------

def _ocr_tesseract(image_bytes: bytes) -> Tuple[str, float]:
    """Tesseract OCR with receipt-optimised config.

    Returns (text, per-character average confidence 0-1).
    """
    from PIL import Image  # requirements-ml.txt
    import pytesseract

    from app.utils.image_preprocessing import preprocess_receipt

    _, pil_img = preprocess_receipt(image_bytes)

    # PSM 6 = assume a uniform block of text (good for receipts/invoices).
    # OEM 3 = LSTM + legacy engine for best accuracy.
    custom_config = r"--oem 3 --psm 6"

    # Get detailed output for confidence scoring.
    data: Dict = pytesseract.image_to_data(pil_img, config=custom_config, output_type=pytesseract.Output.DICT)

    words, confs = [], []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text:
            words.append(text)
            conf = data["conf"][i]
            if isinstance(conf, (int, float)) and conf >= 0:
                confs.append(conf / 100.0)

    raw_text = " ".join(words)
    avg_conf = sum(confs) / len(confs) if confs else 0.0

    # Also get the normal string output for line structure preservation.
    line_text = pytesseract.image_to_string(pil_img, config=custom_config)

    # Prefer the line-structured output if it has reasonable content.
    final_text = line_text.strip() if len(line_text.strip()) >= len(raw_text) * 0.5 else raw_text

    logger.info("Tesseract OCR: %d words, avg confidence %.2f", len(words), avg_conf)
    return final_text, avg_conf


_easyocr_reader = None


def _ocr_easyocr(image_bytes: bytes) -> Tuple[str, float]:
    """EasyOCR — often better than Tesseract on phone photos.

    Returns (text, average confidence 0-1).
    """
    global _easyocr_reader
    import easyocr

    from app.utils.image_preprocessing import preprocess_receipt

    cv2_img, _ = preprocess_receipt(image_bytes)

    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)

    results = _easyocr_reader.readtext(cv2_img)

    if not results:
        return "", 0.0

    # Sort by vertical position (y coordinate) then horizontal (x) to preserve
    # the receipt's top-to-bottom, left-to-right reading order.
    results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))

    lines: List[str] = []
    confs: List[float] = []
    prev_y: Optional[float] = None

    for bbox, text, conf in results:
        y = bbox[0][1]
        if prev_y is not None and abs(y - prev_y) > 15:
            lines.append("\n")
        lines.append(text)
        confs.append(conf)
        prev_y = y

    raw_text = " ".join(lines).replace(" \n ", "\n").strip()
    avg_conf = sum(confs) / len(confs) if confs else 0.0

    logger.info("EasyOCR: %d text regions, avg confidence %.2f", len(results), avg_conf)
    return raw_text, avg_conf


def _run_ocr(image_bytes: bytes) -> Tuple[str, float]:
    """Dispatch to the configured OCR backend."""
    backend = settings.ocr_backend
    if backend == "tesseract":
        return _ocr_tesseract(image_bytes)
    elif backend == "easyocr":
        return _ocr_easyocr(image_bytes)
    else:
        raise ValueError(f"Unknown OCR_BACKEND: {backend!r}. Use mock, tesseract, or easyocr.")


# ---------------------------------------------------------------------------
# Post-OCR text cleaning (before LLM)
# ---------------------------------------------------------------------------

_JUNK_RE = re.compile(r"[|_~`]{2,}")  # OCR artefacts: ||, ___, ~~~
_MULTI_SPACE = re.compile(r" {3,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _clean_ocr_text(text: str) -> str:
    """Remove common OCR noise while preserving receipt structure."""
    text = _JUNK_RE.sub(" ", text)
    text = _MULTI_SPACE.sub("  ", text)       # keep double-space as column separator
    text = _MULTI_NEWLINE.sub("\n\n", text)   # keep paragraph breaks
    # Normalise Nigerian currency symbols OCR often mangles.
    text = text.replace("N#", "₦").replace("N=", "₦").replace("N ", "₦")
    return text.strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(resp: ReceiptResponse) -> None:
    """Flag problems so the merchant reviews them on the confirm screen."""
    if not resp.items:
        resp.warnings.append("No items were found. Try a clearer, well-lit photo.")
        resp.confidence = min(resp.confidence, 0.2)
        return

    # Check total vs sum of line items.
    line_sum = sum(i.line_total for i in resp.items if i.line_total is not None)
    if resp.total is not None and line_sum and abs(line_sum - resp.total) > 1:
        resp.warnings.append(
            f"Items add up to {fmt_naira(line_sum)} but the receipt total is {fmt_naira(resp.total)}. Please check."
        )
        resp.confidence = min(resp.confidence, 0.6)

    # Check each line item's arithmetic: quantity × unit_price ≈ line_total.
    for i in resp.items:
        if i.quantity and i.unit_price and i.line_total:
            expected = i.quantity * i.unit_price
            if abs(expected - i.line_total) > 1:
                resp.warnings.append(f"{i.name}: quantity × price ({fmt_naira(expected)}) "
                                     f"does not match the line total ({fmt_naira(i.line_total)}).")
                resp.confidence = min(resp.confidence, 0.6)

    # Flag suspiciously cheap or expensive items for the Nigerian market.
    for i in resp.items:
        if i.unit_price is not None and i.unit_price > 0:
            if i.unit_price < 5:
                resp.warnings.append(f"{i.name}: unit price {fmt_naira(i.unit_price)} seems too low.")
                resp.confidence = min(resp.confidence, 0.5)
            elif i.unit_price > 50_000_000:
                resp.warnings.append(f"{i.name}: unit price {fmt_naira(i.unit_price)} seems too high.")
                resp.confidence = min(resp.confidence, 0.5)

    # Detect duplicate item names (common OCR glitch: same line read twice).
    seen = {}
    for idx, i in enumerate(resp.items):
        key = i.name.lower().strip()
        if key in seen:
            resp.warnings.append(f"'{i.name}' appears more than once — possible duplicate from OCR.")
            resp.confidence = min(resp.confidence, 0.55)
        seen[key] = idx


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def read_receipt(image_bytes: bytes, catalogue: List[CatalogueItem]) -> ReceiptResponse:
    """Process a receipt image and return structured data for merchant confirmation."""

    if settings.ocr_backend == "mock":
        resp = _mock_receipt()
    else:
        raw_text, ocr_confidence = _run_ocr(image_bytes)
        cleaned_text = _clean_ocr_text(raw_text)

        if not cleaned_text.strip():
            return ReceiptResponse(
                raw_text=raw_text,
                confidence=0.1,
                warnings=["OCR could not read any text. Try a clearer, well-lit photo."],
            )

        try:
            data = await chat_json(_PROMPT, json.dumps({"ocr_text": cleaned_text}, ensure_ascii=False))
            # Base confidence = average of OCR confidence and a default LLM confidence.
            base_confidence = round((ocr_confidence + 0.8) / 2, 2)
            resp = ReceiptResponse(
                supplier=data.get("supplier"),
                items=[ReceiptItem(**{k: v for k, v in it.items() if k in ReceiptItem.model_fields})
                       for it in data.get("items", [])],
                total=data.get("total"),
                confidence=base_confidence,
                raw_text=cleaned_text,
            )
        except LLMUnavailable:
            # Without an LLM we cannot structure the OCR text, but we still
            # return it so the merchant can read and enter items manually.
            resp = ReceiptResponse(
                raw_text=cleaned_text,
                confidence=max(0.1, round(ocr_confidence * 0.3, 2)),
                warnings=["LLM unavailable: could not structure the receipt. Raw text is shown above."],
            )

    # Match products against the merchant's catalogue.
    for item in resp.items:
        m = match_product(item.name, catalogue)
        if m:
            item.matched_product_id = m.id

    _validate(resp)

    resp.confirmation_message = (
        f"I found {len(resp.items)} items"
        + (f" with a total of {fmt_naira(resp.total)}" if resp.total else "")
        + ". Add them to your inventory?"
    )
    return resp
