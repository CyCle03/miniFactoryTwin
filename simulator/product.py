from dataclasses import dataclass
from enum import Enum


class ProductResult(str, Enum):
    GOOD = "GOOD"
    REJECT = "REJECT"


@dataclass
class Product:
    id: int
    position: float
    result: ProductResult

    def move(self, distance: float) -> None:
        self.position = min(100.0, self.position + distance)

    def to_state(self) -> dict[str, int | float | str]:
        return {
            "id": self.id,
            "position": round(self.position, 2),
            "result": self.result.value,
        }

