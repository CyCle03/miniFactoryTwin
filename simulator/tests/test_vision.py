from pathlib import Path

from simulator.product import ProductResult
from simulator.vision import BrightnessInference, ImageInspectionAdapter


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
