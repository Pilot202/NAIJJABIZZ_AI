"""Read-only calls to the backend API. The ML service never writes to the database.

Endpoint paths follow the draft API contract in the project doc; adjust to whatever the backend engineer ships.
"""
from typing import List

import httpx

from app.config import settings
from app.schemas import BusinessSnapshot, CatalogueItem


def _headers() -> dict:
    return {"X-API-Key": settings.backend_api_key} if settings.backend_api_key else {}


async def get_snapshot(business_id: str) -> BusinessSnapshot:
    """Aggregated business data for ask / insights / forecast.

    TODO: agree with the backend engineer on a single GET /ai/snapshot?business_id=... that returns
    the BusinessSnapshot shape from schemas.py (products with avg_daily_sales, debts, monthly totals).
    """
    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=20) as client:
        resp = await client.get("/ai/snapshot", params={"business_id": business_id}, headers=_headers())
        resp.raise_for_status()
        return BusinessSnapshot(**resp.json())


async def get_catalogue(business_id: str) -> List[CatalogueItem]:
    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=20) as client:
        resp = await client.get("/products", params={"business_id": business_id}, headers=_headers())
        resp.raise_for_status()
        return [CatalogueItem(id=str(p["id"]), name=p["name"]) for p in resp.json()]
