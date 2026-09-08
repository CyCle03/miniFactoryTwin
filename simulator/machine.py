import random
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from .constants import SimulationConfig
from .product import Product, ProductResult
from .vision import InspectionProvider


class MachineSimulator:
    """Owns the conveyor cell state and advances it using fixed-duration ticks."""

    def __init__(
        self,
        config: SimulationConfig | None = None,
        seed: int | None = None,
        initial_time: float | None = None,
        inspection_provider: InspectionProvider | None = None,
    ) -> None:
        self.config = config or SimulationConfig()
        self._random = random.Random(seed)
        self.inspection_provider = inspection_provider
        self.power = False
        self.running = False
        self.emergency = False
        self.products: list[Product] = []
        self.total_count = 0
        self.good_count = 0
        self.reject_count = 0
        self._next_product_id = 1
        start_time = time.monotonic() if initial_time is None else initial_time
        self._last_spawn = start_time - self.config.spawn_interval_seconds
        self._cylinder_extended_until = 0.0
        self._completed_at: deque[float] = deque()
        self._events: deque[dict[str, object]] = deque()
        self.session_id = str(uuid.uuid4())

    def handle_command(self, command: str) -> None:
        if command == "start":
            changed = not self.running and not self.emergency
            self.power = True
            if not self.emergency:
                self.running = True
            if changed:
                self._emit("machine_started", "INFO", "Machine started")
        elif command == "stop":
            changed = self.running
            self.running = False
            if changed:
                self._emit("machine_stopped", "INFO", "Machine stopped")
        elif command == "reset":
            self._reset_production()
        elif command == "emergency_stop":
            changed = not self.emergency
            self.emergency = True
            self.running = False
            if changed:
                self._emit("emergency_stop_activated", "CRITICAL", "Emergency stop activated")
        elif command == "emergency_reset":
            changed = self.emergency
            self.emergency = False
            self.running = False
            if changed:
                self._emit("emergency_stop_reset", "WARNING", "Emergency stop reset")
        else:
            raise ValueError(f"Unsupported command: {command}")

    def tick(self, delta_seconds: float, now: float | None = None) -> None:
        if delta_seconds < 0:
            raise ValueError("delta_seconds must be non-negative")
        current_time = time.monotonic() if now is None else now
        self._prune_ppm_window(current_time)

        if not self.running or self.emergency:
            return

        self._spawn_if_due(current_time)
        distance = self.config.conveyor_speed_units_per_second * delta_seconds
        survivors: list[Product] = []

        for product in self.products:
            previous_position = product.position
            product.move(distance)
            if not product.inspected and previous_position < self.config.sensor_2_position <= product.position:
                product.inspected = True
                product.inspected_at = datetime.now(timezone.utc)
                inspection_metadata: dict[str, object] = {"result": product.result.value}
                if self.inspection_provider is not None:
                    inspection = self.inspection_provider.inspect(product.id)
                    product.result = inspection.result
                    inspection_metadata = {
                        "result": inspection.result.value,
                        "confidence": inspection.confidence,
                        "latency_ms": inspection.latency_ms,
                        "model": inspection.model,
                        "defect": inspection.defect,
                    }
                product.inspection_metadata = inspection_metadata
                self._emit("inspection_completed", "INFO", "Inspection completed", product.id, inspection_metadata)
                if product.result is ProductResult.REJECT:
                    self._emit("product_rejected", "WARNING", "Product rejected", product.id, {"result": product.result.value})
            if product.result is ProductResult.REJECT and product.position >= self.config.cylinder_position:
                self._complete(product, current_time)
                self._cylinder_extended_until = current_time + self.config.cylinder_extend_seconds
            elif product.position >= self.config.exit_position:
                self._complete(product, current_time)
            else:
                survivors.append(product)

        self.products = survivors

    def state(self, now: float | None = None) -> dict[str, object]:
        current_time = time.monotonic() if now is None else now
        self._prune_ppm_window(current_time)
        sensor_1 = self._sensor_active(self.config.sensor_1_position)
        sensor_2 = self._sensor_active(self.config.sensor_2_position)
        cylinder_extended = current_time < self._cylinder_extended_until

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "machine": {
                "power": self.power,
                "running": self.running,
                "emergency": self.emergency,
            },
            "conveyor": {
                "running": self.running and not self.emergency,
                "speed": self.config.displayed_speed_mps if self.running and not self.emergency else 0.0,
            },
            "sensors": {"photo_1": sensor_1, "photo_2": sensor_2},
            "cylinder": {"state": "extended" if cylinder_extended else "retracted"},
            "production": {
                "total": self.total_count,
                "good": self.good_count,
                "reject": self.reject_count,
                "ppm": len(self._completed_at),
            },
            "products": [product.to_state() for product in self.products],
        }

    def _spawn_if_due(self, now: float) -> None:
        if now - self._last_spawn + 1e-9 < self.config.spawn_interval_seconds:
            return
        result = (
            ProductResult.GOOD
            if self._random.random() < self.config.good_probability
            else ProductResult.REJECT
        )
        entered_at = datetime.now(timezone.utc)
        product = Product(self._next_product_id, 0.0, result, entered_at, now)
        self.products.append(product)
        self._emit("product_entered", "INFO", "Product entered", product.id)
        self._next_product_id += 1
        self._last_spawn = now

    def _sensor_active(self, sensor_position: float) -> bool:
        half_width = self.config.sensor_detection_width / 2
        return any(abs(product.position - sensor_position) <= half_width for product in self.products)

    def _complete(self, product: Product, now: float) -> None:
        self.total_count += 1
        if product.result is ProductResult.GOOD:
            self.good_count += 1
        else:
            self.reject_count += 1
        self._completed_at.append(now)
        completed_at = datetime.now(timezone.utc)
        entered_at = product.entered_at or completed_at
        inspected_at = product.inspected_at or completed_at
        cycle_time = max(0.0, now - product.entered_monotonic) if product.entered_monotonic is not None else 0.0
        metadata: dict[str, object] = {"result": product.result.value, "started_at": entered_at.isoformat(), "inspected_at": inspected_at.isoformat(), "completed_at": completed_at.isoformat(), "cycle_time_seconds": cycle_time}
        metadata.update({f"inspection_{key}": value for key, value in product.inspection_metadata.items() if key != "result"})
        self._emit("product_completed", "INFO", "Product completed", product.id, metadata)

    def drain_events(self) -> list[dict[str, object]]:
        events = list(self._events)
        self._events.clear()
        return events

    def _emit(self, event_type: str, severity: str, message: str, product_id: int | None = None, metadata: dict[str, object] | None = None) -> None:
        self._events.append({"event_id": str(uuid.uuid4()), "session_id": self.session_id, "timestamp": datetime.now(timezone.utc).isoformat(), "event_type": event_type, "severity": severity, "message": message, "product_id": product_id, "metadata": metadata or {}})

    def _prune_ppm_window(self, now: float) -> None:
        while self._completed_at and now - self._completed_at[0] > 60.0:
            self._completed_at.popleft()

    def _reset_production(self) -> None:
        self.running = False
        self.products.clear()
        self.total_count = 0
        self.good_count = 0
        self.reject_count = 0
        self._completed_at.clear()
        self._cylinder_extended_until = 0.0
        self._last_spawn = time.monotonic() - self.config.spawn_interval_seconds
