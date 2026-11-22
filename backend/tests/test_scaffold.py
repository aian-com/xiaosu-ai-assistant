from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from mock_api.main import app as mock_app, last_monday


def test_health_does_not_claim_live_integration():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/readiness").json()["im_verified"] is False


def test_employee_and_missing_employee():
    client = TestClient(mock_app)
    assert client.get("/api/employee/001").json()["dept"] == "研发部"
    assert client.get("/api/employee/999").status_code == 404


def test_last_week_across_year_boundary():
    assert last_monday(date(2026, 1, 1)) == date(2025, 12, 22)


def test_reversed_date_range_rejected():
    response = TestClient(mock_app).get("/api/orders", params={"start_date": "2026-11-20", "end_date": "2026-11-01"})
    assert response.status_code == 422
