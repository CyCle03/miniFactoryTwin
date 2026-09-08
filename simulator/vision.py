from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .product import ProductResult


@dataclass(frozen=True)
class InspectionResult:
    result: ProductResult
    confidence: float
    latency_ms: float
    model: str
    defect: str | None = None


class InspectionProvider(Protocol):
    def inspect(self, product_id: int) -> InspectionResult: ...


class BrightnessInference:
    """Deterministic development inference over normalized grayscale pixels."""

    name = "brightness-v1"

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def predict(self, pixels: list[float]) -> tuple[ProductResult, float, str | None]:
        if not pixels:
            raise ValueError("inspection image contains no pixels")
        score = sum(pixels) / len(pixels)
        if score >= self.threshold:
            return ProductResult.GOOD, score, None
        return ProductResult.REJECT, 1.0 - score, "low_brightness"


def load_image(path: Path) -> list[float]:
    """Load and normalize an image through OpenCV without leaking cv2 into callers."""
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"unable to read inspection image: {path}")
    resized = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    return (resized.astype("float32") / 255.0).reshape(-1).tolist()


class ImageInspectionAdapter:
    def __init__(
        self,
        image_paths: list[Path],
        minimum_confidence: float = 0.7,
        loader: Callable[[Path], list[float]] = load_image,
        inference: BrightnessInference | None = None,
    ) -> None:
        if not image_paths:
            raise ValueError("at least one inspection image is required")
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.image_paths = image_paths
        self.minimum_confidence = minimum_confidence
        self.loader = loader
        self.inference = inference or BrightnessInference()

    def inspect(self, product_id: int) -> InspectionResult:
        started = time.perf_counter()
        path = self.image_paths[(product_id - 1) % len(self.image_paths)]
        try:
            result, confidence, defect = self.inference.predict(self.loader(path))
            if confidence < self.minimum_confidence:
                result, defect = ProductResult.REJECT, "low_confidence"
        except Exception:
            result, confidence, defect = ProductResult.REJECT, 0.0, "inspection_error"
        return InspectionResult(
            result=result,
            confidence=round(confidence, 4),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            model=self.inference.name,
            defect=defect,
        )
