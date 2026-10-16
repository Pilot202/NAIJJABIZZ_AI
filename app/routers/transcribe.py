from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas import Language, TranscribeResponse
from app.services import asr

router = APIRouter(tags=["speech"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: Language = Form(Language.en)):
    """Audio in, transcript out."""
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")
    try:
        text, conf = asr.transcribe(data, language, audio.filename or "audio.m4a")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return TranscribeResponse(transcript=text, language=language, confidence=conf)
