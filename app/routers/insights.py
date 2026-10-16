from fastapi import APIRouter

from app.schemas import ForecastRequest, ForecastResponse, InsightsRequest, InsightsResponse
from app.services import forecasting
from app.services.insights import generate_alerts

router = APIRouter(tags=["insights"])


@router.post("/insights", response_model=InsightsResponse)
async def insights(req: InsightsRequest):
    """Proactive alerts (low stock, sales drop, expense growth, overdue debts)."""
    return InsightsResponse(alerts=generate_alerts(req.snapshot))


@router.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest):
    """Days of stock left, cash-flow estimate, health score, and an optional affordability check."""
    s = req.snapshot
    avg_net = forecasting.moving_average(s.monthly_net_cashflow)
    return ForecastResponse(
        stock=[forecasting.stock_forecast(p) for p in s.products],
        avg_monthly_net_cashflow=avg_net,
        next_month_net_cashflow=avg_net,  # simple moving average; swap in a better model if time allows
        health_score=forecasting.health_score(s),
        affordability=forecasting.affordability(avg_net, req.purchase_price) if req.purchase_price else None,
    )
