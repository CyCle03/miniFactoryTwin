from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    conveyor_speed_units_per_second: float = 14.0
    displayed_speed_mps: float = 0.75
    spawn_interval_seconds: float = 2.8
    good_probability: float = 0.95
    sensor_1_position: float = 20.0
    sensor_2_position: float = 70.0
    sensor_detection_width: float = 3.0
    cylinder_position: float = 80.0
    cylinder_extend_seconds: float = 0.45
    exit_position: float = 100.0

