from app.schemas import BusinessSnapshot, DebtSnapshot, ProductSnapshot
from app.services import forecasting
from app.services.insights import generate_alerts


def test_days_of_stock_left():
    assert forecasting.days_of_stock_left(17, 2) == 8.5
    assert forecasting.days_of_stock_left(10, 0) is None


def test_peak_milk_restock_advice():
    p = ProductSnapshot(id="1", name="Peak Milk", unit="unit", stock=18, avg_daily_sales=6)
    f = forecasting.stock_forecast(p)
    assert f.days_left == 3.0
    assert "Restock" in f.restock_advice


def test_moving_average():
    assert forecasting.moving_average([100, 200, 300, 400], window=3) == 300
    assert forecasting.moving_average([]) is None


def test_affordability():
    ok = forecasting.affordability(600_000, 250_000)
    assert ok.can_afford
    assert not forecasting.affordability(-5, 100).can_afford


def test_alerts():
    s = BusinessSnapshot(
        products=[ProductSnapshot(id="1", name="Spaghetti", unit="carton", stock=4, min_stock=5, avg_daily_sales=1)],
        sales_this_week=80, avg_weekly_sales=100,
        revenue_this_month=100, revenue_last_month=100, expenses_this_month=80, expenses_last_month=50,
        debts=[DebtSnapshot(customer="Tunde", amount=35_000, days_outstanding=40)],
    )
    types = {a.type for a in generate_alerts(s)}
    assert types == {"low_stock", "sales_drop", "expense_growth", "overdue_debt"}


def test_health_score_range():
    assert 0 <= forecasting.health_score(BusinessSnapshot()) <= 100
