from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.history import HistoryRepository


def test_api_limit_filter_and_validation() -> None:
    with TemporaryDirectory() as directory:
        main.history = HistoryRepository(f"{directory}/api.db")
        client = TestClient(main.app)
        assert client.get("/api/history/production?limit=0").status_code == 422
        assert client.get("/api/history/production?limit=501").status_code == 422
        assert client.get("/api/history/production?result=INVALID").status_code == 422
        assert client.get("/api/history/events?severity=CRITICAL&limit=10").json() == []
        response = client.get("/api/history/production?start=2026-02-01T00:00:00Z&end=2026-01-01T00:00:00Z")
        assert response.status_code == 422
        assert response.json()["detail"] == "start must not be after end"
