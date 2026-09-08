from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ProductResult(str, Enum):
    GOOD = "GOOD"
    REJECT = "REJECT"


@dataclass
class Product:
    id: int
    position: float
    result: ProductResult
    entered_at: datetime | None = None
    entered_monotonic: float | None = None
    inspected_at: datetime | None = None
    inspected: bool = False

    def move(self, distance: float) -> None:
        self.position = min(100.0, self.position + distance)

    def to_state(self) -> dict[str, int | float | str]:
        return {
            "id": self.id,
            "position": round(self.position, 2),
            "result": self.result.value,
        }

