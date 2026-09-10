import asyncio
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app import main
from backend.app.history import HistoryRepository


def test_api_limit_filter_and_validation() -> None:
    with TemporaryDirectory() as directory:
        main.history = HistoryRepository(f"{directory}/api.db")
        operation = main.app.openapi()["paths"]["/api/history/production"]["get"]
        limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")
        assert limit["schema"]["minimum"] == 1
        assert limit["schema"]["maximum"] == 500
        with pytest.raises(ValueError):
            main.ProductResult("INVALID")
        with pytest.raises(HTTPException, match="start must not be after end"):
            main.production_history(
                limit=50,
                start=main.datetime.fromisoformat("2026-02-01T00:00:00+00:00"),
                end=main.datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            )
        assert main.event_history(
            limit=10, start=None, end=None,
            severity=main.EventSeverity.CRITICAL, event_type=None,
        ) == []


def test_inspection_image_endpoint_only_serves_supported_local_files() -> None:
    with TemporaryDirectory() as directory:
        image_directory = Path(directory)
        (image_directory / "sample.png").write_bytes(b"not-a-real-image")
        (image_directory / "secret.txt").write_text("secret")
        main.inspection_image_directory = image_directory.resolve()
        response = asyncio.run(main.inspection_image("sample.png"))
        assert Path(response.path) == image_directory / "sample.png"
        with pytest.raises(HTTPException):
            asyncio.run(main.inspection_image("secret.txt"))
        with pytest.raises(HTTPException):
            asyncio.run(main.inspection_image("../secret.txt"))
