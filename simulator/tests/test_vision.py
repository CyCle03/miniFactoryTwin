from pathlib import Path

from simulator.product import ProductResult
from simulator.vision import BrightnessInference, ImageInspectionAdapter, YoloInspectionAdapter


class Values:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeYoloResult:
    names = {0: "good", 1: "scratch"}

    def __init__(self, classes: list[float], confidences: list[float]) -> None:
        self.boxes = type("Boxes", (), {
            "cls": Values(classes), "conf": Values(confidences),
        })()


class FakeYolo:
    def __init__(self, result: FakeYoloResult) -> None:
        self.result = result

    def __call__(self, _path: str, verbose: bool = False) -> list[FakeYoloResult]:
        assert verbose is False
        return [self.result]


def test_fixed_images_produce_reproducible_results() -> None:
    pixels = {"good.png": [0.9] * 4, "reject.png": [0.1] * 4}
    adapter = ImageInspectionAdapter(
        [Path("good.png"), Path("reject.png")],
        loader=lambda path: pixels[path.name],
    )

    assert adapter.inspect(1).result is ProductResult.GOOD
    assert adapter.inspect(2).result is ProductResult.REJECT
    assert adapter.inspect(3).result is ProductResult.GOOD


def test_low_confidence_and_loader_errors_fail_safe_to_reject() -> None:
    uncertain = ImageInspectionAdapter(
        [Path("uncertain.png")], loader=lambda _path: [0.55],
        minimum_confidence=0.7, inference=BrightnessInference(threshold=0.5),
    )
    broken = ImageInspectionAdapter(
        [Path("missing.png")], loader=lambda _path: (_ for _ in ()).throw(ValueError()),
    )

    assert uncertain.inspect(1).defect == "low_confidence"
    assert uncertain.inspect(1).result is ProductResult.REJECT
    assert broken.inspect(1).defect == "inspection_error"
    assert broken.inspect(1).result is ProductResult.REJECT


def test_yolo_uses_highest_confidence_detection() -> None:
    adapter = YoloInspectionAdapter(
        [Path("part.png")], Path("best.pt"), minimum_confidence=0.7,
        model=FakeYolo(FakeYoloResult([1, 0], [0.75, 0.95])),
    )
    result = adapter.inspect(1)
    assert result.result is ProductResult.GOOD
    assert result.confidence == 0.95
    assert result.model == "yolo:best.pt"


def test_yolo_low_confidence_and_missing_detection_fail_safe() -> None:
    low = YoloInspectionAdapter(
        [Path("part.png")], Path("best.pt"), minimum_confidence=0.7,
        model=FakeYolo(FakeYoloResult([0], [0.4])),
    )
    missing = YoloInspectionAdapter(
        [Path("part.png")], Path("best.pt"),
        model=FakeYolo(FakeYoloResult([], [])),
    )
    assert low.inspect(1).defect == "low_confidence"
    assert low.inspect(1).result is ProductResult.REJECT
    assert missing.inspect(1).defect == "no_detection"
