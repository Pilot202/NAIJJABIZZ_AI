from fastapi import APIRouter, HTTPException

from app.schemas import AskRequest, AskResponse
from app.services import backend_client
from app.services.ask_business import ask as ask_business

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """Ask My Business: answers from real figures. Pass `snapshot`, or a business_id to fetch it."""
    snapshot = req.snapshot
    if snapshot is None:
        if not req.business_id:
            raise HTTPException(422, "Provide either snapshot or business_id")
        try:
            snapshot = await backend_client.get_snapshot(req.business_id)
        except Exception as exc:
            raise HTTPException(502, f"Could not load business data from the backend: {exc}")
    return await ask_business(req.question, req.language, snapshot)
