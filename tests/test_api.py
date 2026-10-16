from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_interpret():
    r = client.post("/interpret", json={"text": "I bought 15 cartons of Indomie for 120,000 naira",
                                         "language": "en",
                                         "catalogue": [{"id": "p3", "name": "Indomie Noodles"}]})
    body = r.json()
    assert r.status_code == 200
    assert body["intent"] == "add_inventory"
    assert body["entities"]["unit_cost"] == 8000


def test_parse_receipt_mock():
    r = client.post("/parse-receipt", files={"image": ("r.jpg", b"fake", "image/jpeg")})
    body = r.json()
    assert r.status_code == 200 and body["total"] == 1_430_000 and not body["warnings"]


def test_transcribe_mock():
    r = client.post("/transcribe", files={"audio": ("a.m4a", b"fake", "audio/m4a")}, data={"language": "yo"})
    assert r.status_code == 200 and r.json()["language"] == "yo"


def test_ask_with_snapshot():
    snap = {"products": [{"id": "1", "name": "Rice", "unit": "bag", "stock": 17, "avg_daily_sales": 2}]}
    r = client.post("/ask", json={"question": "How much rice do I have left?", "snapshot": snap})
    assert r.status_code == 200 and "17" in r.json()["answer"]


def test_ask_requires_data():
    assert client.post("/ask", json={"question": "hi"}).status_code == 422


def test_forecast_and_insights():
    snap = {"products": [{"id": "1", "name": "Peak Milk", "stock": 18, "avg_daily_sales": 6}],
            "monthly_net_cashflow": [500000, 600000, 700000]}
    f = client.post("/forecast", json={"snapshot": snap, "purchase_price": 250000}).json()
    assert f["stock"][0]["days_left"] == 3.0 and f["affordability"]["can_afford"]
    assert client.post("/insights", json={"snapshot": snap}).json()["alerts"]
