import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import ActionProposal, CatalogueItem, InterpretRequest, Language
from app.services import asr, backend_client
from app.services.intent_parser import parse_command

router = APIRouter(tags=["interpret"])


@router.post("/interpret", response_model=ActionProposal)
async def interpret(req: InterpretRequest):
    """Text command -> proposed action. Nothing is saved; the backend confirms with the merchant first."""
    catalogue = req.catalogue
    if not catalogue and req.business_id:
        try:
            catalogue = await backend_client.get_catalogue(req.business_id)
        except Exception:
            catalogue = []  # still return a proposal; the merchant can pick the product on the confirm screen
    return await parse_command(req.text, req.language, catalogue)


@router.post("/interpret/audio", response_model=ActionProposal)
async def interpret_audio(
    audio: UploadFile = File(...),
    language: Language = Form(Language.en),
    business_id: Optional[str] = Form(None),
    catalogue_json: Optional[str] = Form(None),  # JSON list of {"id","name"}; optional
):
    """Voice command -> transcript -> proposed action, in one call."""
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")
    try:
        text, _ = asr.transcribe(data, language, audio.filename or "audio.m4a")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

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
    return await parse_command(text, language, catalogue)
