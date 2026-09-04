from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ProductResult(str, Enum):
    GOOD = "GOOD"
    REJECT = "REJECT"


class CylinderState(str, Enum):
    RETRACTED = "retracted"
    EXTENDED = "extended"


class CommandName(str, Enum):
    START = "start"
    STOP = "stop"
    RESET = "reset"
    EMERGENCY_STOP = "emergency_stop"
    EMERGENCY_RESET = "emergency_reset"


class CommandMessage(BaseModel):
    command: CommandName


class MachineFlags(BaseModel):
    power: bool
    running: bool
    emergency: bool


class ConveyorState(BaseModel):
    running: bool
    speed: float = Field(ge=0)


class SensorState(BaseModel):
    photo_1: bool
    photo_2: bool


class Cylinder(BaseModel):
    state: CylinderState


class ProductionState(BaseModel):
    total: int = Field(ge=0)
    good: int = Field(ge=0)
    reject: int = Field(ge=0)
    ppm: int = Field(ge=0)

    @model_validator(mode="after")
    def counters_are_consistent(self) -> "ProductionState":
        if self.total != self.good + self.reject:
            raise ValueError("total must equal good + reject")
        return self


class ProductState(BaseModel):
    id: int = Field(ge=1)
    position: float = Field(ge=0, le=100)
    result: ProductResult


class MachineState(BaseModel):
    timestamp: datetime
    machine: MachineFlags
    conveyor: ConveyorState
    sensors: SensorState
    cylinder: Cylinder
    production: ProductionState
    products: list[ProductState]


def empty_machine_state() -> MachineState:
    return MachineState(
        timestamp=datetime.now(timezone.utc),
        machine=MachineFlags(power=False, running=False, emergency=False),
        conveyor=ConveyorState(running=False, speed=0),
        sensors=SensorState(photo_1=False, photo_2=False),
        cylinder=Cylinder(state=CylinderState.RETRACTED),
        production=ProductionState(total=0, good=0, reject=0, ppm=0),
        products=[],
    )

