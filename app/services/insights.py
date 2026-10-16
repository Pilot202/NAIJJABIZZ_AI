"""Proactive alert rules. Pure functions over a BusinessSnapshot so they are easy to test.

The backend can call this on a schedule and store the results in its alerts table.
"""
from typing import List

from app.schemas import Alert, BusinessSnapshot
from app.services.forecasting import RESTOCK_WITHIN_DAYS, days_of_stock_left
from app.utils.naira import fmt_naira

SALES_DROP_THRESHOLD = 0.15      # alert when this week is >=15% below the usual week
OVERDUE_DEBT_DAYS = 30
EXPENSE_GROWTH_MARGIN = 0.10     # expenses grew at least 10% faster than revenue


def generate_alerts(s: BusinessSnapshot) -> List[Alert]:
    alerts: List[Alert] = []

    for p in s.products:
        below_min = p.min_stock > 0 and p.stock <= p.min_stock
        days = days_of_stock_left(p.stock, p.avg_daily_sales)
        if below_min or (days is not None and days < RESTOCK_WITHIN_DAYS):
            msg = f"You have only {p.stock:g} {p.unit} of {p.name} left."
            if days is not None:
                msg += f" At your current sales rate that is about {days:g} days of stock."
            alerts.append(Alert(type="low_stock", severity="warning" if (days or 99) >= 2 else "critical",
                                message=msg, product_id=p.id))

    if s.avg_weekly_sales > 0:
        drop = (s.avg_weekly_sales - s.sales_this_week) / s.avg_weekly_sales
        if drop >= SALES_DROP_THRESHOLD:
            alerts.append(Alert(type="sales_drop", severity="warning",
                                message=f"Your sales have dropped {drop:.0%} this week compared with your average."))

    if s.revenue_last_month > 0 and s.expenses_last_month > 0:
        rev_growth = s.revenue_this_month / s.revenue_last_month - 1
        exp_growth = s.expenses_this_month / s.expenses_last_month - 1
        if exp_growth - rev_growth >= EXPENSE_GROWTH_MARGIN:
            alerts.append(Alert(type="expense_growth", severity="warning",
                                message="Your expenses are growing faster than your revenue this month."))

    overdue = [d for d in s.debts if d.days_outstanding > OVERDUE_DEBT_DAYS]
    if overdue:
        total = sum(d.amount for d in overdue)
        alerts.append(Alert(type="overdue_debt", severity="info",
                            message=f"{len(overdue)} customers owe {fmt_naira(total)} for more than "
                                    f"{OVERDUE_DEBT_DAYS} days."))
    return alerts
