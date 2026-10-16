"""Deterministic forecasting: days of stock left, restock advice, cash flow, affordability, health score.

Kept as plain, testable functions. The thresholds are simple heuristics to tune with the team.
"""
from typing import List, Optional

from app.schemas import Affordability, BusinessSnapshot, ProductSnapshot, StockForecast
from app.utils.naira import fmt_naira

RESTOCK_WITHIN_DAYS = 5   # advise restocking when stock covers fewer days than this


def days_of_stock_left(stock: float, avg_daily_sales: float) -> Optional[float]:
    """Current stock divided by average daily sales. None when the product is not selling."""
    if avg_daily_sales <= 0:
        return None
    return round(stock / avg_daily_sales, 1)


def stock_forecast(p: ProductSnapshot) -> StockForecast:
    days = days_of_stock_left(p.stock, p.avg_daily_sales)
    if days is None:
        advice = f"{p.name} has not been selling recently ({p.stock:g} {p.unit} in stock)."
    elif days < RESTOCK_WITHIN_DAYS:
        advice = (f"Restock {p.name} within {max(1, int(days))} days. You have {p.stock:g} {p.unit} "
                  f"and sell about {p.avg_daily_sales:g} per day.")
    else:
        advice = f"You have about {days:g} days of {p.name} left."
    return StockForecast(product_id=p.id, product_name=p.name, days_left=days, restock_advice=advice)


def moving_average(values: List[float], window: int = 3) -> Optional[float]:
    if not values:
        return None
    recent = values[-window:]
    return round(sum(recent) / len(recent), 2)


def affordability(avg_monthly_net: Optional[float], price: float, reserve_ratio: float = 0.5) -> Affordability:
    """Heuristic: spending up to `reserve_ratio` of ~1 month of average net cash flow is 'safe'.

    TODO: also subtract upcoming stock commitments and keep a minimum operating-cash buffer.
    """
    if avg_monthly_net is None or avg_monthly_net <= 0:
        return Affordability(can_afford=False, safe_min=0, safe_max=0,
                             explanation="Your recent cash flow does not leave room for a large purchase.")
    safe_max = round(avg_monthly_net * reserve_ratio, -3)
    safe_min = round(safe_max * 0.8, -3)
    ok = price <= safe_max
    explanation = (
        f"Based on your average monthly cash flow of {fmt_naira(avg_monthly_net)}, you can spend roughly "
        f"{fmt_naira(safe_min)} to {fmt_naira(safe_max)} without putting your operating cash under pressure. "
        + ("This purchase fits." if ok else f"{fmt_naira(price)} is above that range.")
    )
    return Affordability(can_afford=ok, safe_min=safe_min, safe_max=safe_max, explanation=explanation)


def health_score(s: BusinessSnapshot) -> int:
    """0-100 score from profit margin, stock cover and customer debt. Weights are placeholders to tune."""
    score = 50.0
    if s.revenue_this_month > 0:
        margin = (s.revenue_this_month - s.expenses_this_month) / s.revenue_this_month
        score += max(-25, min(25, margin * 100 / 2))          # +-25 from margin
        debt_total = sum(d.amount for d in s.debts)
        score -= min(15, (debt_total / s.revenue_this_month) * 30)  # up to -15 from debt
    selling = [p for p in s.products if p.avg_daily_sales > 0]
    if selling:
        low = sum(1 for p in selling if (days_of_stock_left(p.stock, p.avg_daily_sales) or 99) < RESTOCK_WITHIN_DAYS)
        score -= min(15, 15 * low / len(selling))              # up to -15 from low stock
    if s.revenue_last_month > 0 and s.revenue_this_month >= s.revenue_last_month:
        score += 5
    return int(max(0, min(100, round(score))))
