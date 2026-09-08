from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from backend.app.history import HistoryRepository
from backend.app.models import MachineEvent


def completed(event_id: str = "event-1", with_inspection: bool = False) -> MachineEvent:
    now = datetime.now(timezone.utc)
    metadata = {"result": "GOOD", "started_at": now.isoformat(),
        "inspected_at": now.isoformat(), "completed_at": now.isoformat(),
        "cycle_time_seconds": 4.25}
    if with_inspection:
        metadata.update({"inspection_confidence": 0.97, "inspection_latency_ms": 3.2,
                         "inspection_model": "test-model", "inspection_defect": None})
    return MachineEvent(event_id=event_id, session_id="session-1", timestamp=now,
        event_type="product_completed", severity="INFO", message="Product completed",
        product_id=7, metadata=metadata)


def test_completed_product_is_stored_exactly_once_and_summarized() -> None:
    with TemporaryDirectory() as directory:
        repo = HistoryRepository(f"{directory}/history.db")
        assert repo.record_event(completed()) is True
        assert repo.record_event(completed()) is False
        rows = repo.production(50)
        assert len(rows) == 1
        assert rows[0]["cycle_time_seconds"] == 4.25
        assert repo.summary()["average_cycle_time"] == 4.25


def test_filters_and_limits() -> None:
    with TemporaryDirectory() as directory:
        repo = HistoryRepository(f"{directory}/history.db")
        repo.record_event(completed())
        assert len(repo.production(1, result=None)) == 1
        assert repo.events(1, severity="INFO")[0]["event_type"] == "product_completed"
        assert repo.events(1, severity="CRITICAL") == []


def test_inspection_metadata_is_stored_with_production() -> None:
    with TemporaryDirectory() as directory:
        repo = HistoryRepository(f"{directory}/history.db")
        repo.record_event(completed(with_inspection=True))
        row = repo.production(1)[0]
        assert row["inspection_confidence"] == 0.97
        assert row["inspection_latency_ms"] == 3.2
        assert row["inspection_model"] == "test-model"
        assert row["inspection_defect"] is None
