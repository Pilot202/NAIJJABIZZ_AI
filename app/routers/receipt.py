
import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import CatalogueItem, ReceiptResponse
from app.services import backend_client
from app.services.receipt_reader import read_receipt

router = APIRouter(tags=["receipt"])


@router.post("/parse-receipt", response_model=ReceiptResponse)
async def parse_receipt(
    image: UploadFile = File(...),
    business_id: Optional[str] = Form(None),
    catalogue_json: Optional[str] = Form(None),
):
    """Invoice/receipt photo -> items for the merchant to review and confirm."""
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty image file")
    catalogue = []
    if catalogue_json and catalogue_json.strip():
        try:
            items = json.loads(catalogue_json)
            if isinstance(items, list):
                catalogue = [CatalogueItem(**c) for c in items if isinstance(c, dict)]
        except Exception:
            catalogue = []
    if not catalogue and business_id:
        try:
            catalogue = await backend_client.get_catalogue(business_id)
        except Exception:
            catalogue = []
    return await read_receipt(data, catalogue)
