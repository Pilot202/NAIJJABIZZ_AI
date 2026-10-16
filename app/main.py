from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import settings
from app.routers import ask, command, insights, receipt, transcribe


def require_api_key(x_api_key: str = Header(default="")):
    """The backend sends the shared secret in X-API-Key. Disabled when ML_API_KEY is empty (dev only)."""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(401, "Invalid API key")


app = FastAPI(title="NaijaBiz AI - ML service", version="0.1.0", dependencies=[Depends(require_api_key)])

for r in (transcribe.router, command.router, receipt.router, ask.router, insights.router):
    app.include_router(r)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_backend": settings.llm_backend,
        "asr_backend": settings.asr_backend,
        "ocr_backend": settings.ocr_backend,
    }
