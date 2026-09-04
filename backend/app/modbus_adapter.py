import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from pymodbus.client import AsyncModbusTcpClient

from .modbus_map import (
    COIL_CONVEYOR, COIL_CYLINDER, COIL_EMERGENCY, COIL_POWER, COIL_RUNNING,
    COIL_SENSOR_1, COIL_SENSOR_2, COMMAND_COILS, HOLDING_REGISTER_COUNT,
    MAX_PRODUCTS, PRODUCT_BASE, PRODUCT_STRIDE, REG_COMMAND_ACK,
    REG_CONVEYOR_SPEED, REG_GOOD_HI, REG_HEARTBEAT, REG_PPM,
    REG_PRODUCT_COUNT, REG_REJECT_HI, REG_SCHEMA_VERSION, REG_TOTAL_HI,
    RESULT_GOOD, RESULT_REJECT, SCHEMA_VERSION, STATUS_COIL_COUNT, decode_u32,
)
from .models import (
    Cylinder, CylinderState, MachineFlags, MachineState, ProductResult,
    ProductState, ProductionState, SensorState, ConveyorState,
)

logger = logging.getLogger(__name__)
StateHandler = Callable[[MachineState], Awaitable[None]]
StatusHandler = Callable[[bool, bool, str | None], Awaitable[None]]


class ModbusAdapter:
    def __init__(self, host: str, port: int, unit_id: int, poll_interval: float,
                 stale_timeout: float, command_timeout: float,
                 state_handler: StateHandler, status_handler: StatusHandler) -> None:
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient | None = None
        self.unit_id = unit_id
        self.poll_interval = poll_interval
        self.stale_timeout = stale_timeout
        self.command_timeout = command_timeout
        self.state_handler = state_handler
        self.status_handler = status_handler
        self.connected = False
        self.stale = True
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_heartbeat: int | None = None
        self._last_heartbeat_at = 0.0
        self._command_lock = asyncio.Lock()

    async def start(self) -> None:
        self.client = AsyncModbusTcpClient(self.host, port=self.port, timeout=1)
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="modbus-adapter")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        if self.client is not None:
            self.client.close()

    async def command(self, command: str) -> bool:
        coil = COMMAND_COILS.get(command)
        if coil is None or self.client is None or not self.connected or self.stale:
            return False
        async with self._command_lock:
            before = await self.client.read_holding_registers(
                REG_COMMAND_ACK, count=1, slave=self.unit_id)
            if before.isError():
                return False
            result = await self.client.write_coil(coil, True, slave=self.unit_id)
            if result.isError():
                return False
            deadline = asyncio.get_running_loop().time() + self.command_timeout
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.05)
                after = await self.client.read_holding_registers(
                    REG_COMMAND_ACK, count=1, slave=self.unit_id)
                if not after.isError() and after.registers[0] != before.registers[0]:
                    return True
            return False

    async def _run(self) -> None:
        delay = self.poll_interval
        while not self._stop.is_set():
            if self.client is None:
                return
            try:
                if not self.client.connected and not await self.client.connect():
                    raise ConnectionError("Modbus connection failed")
                self.connected = True
                await self._poll()
                delay = self.poll_interval
            except (OSError, ConnectionError, asyncio.TimeoutError) as exc:
                if self.connected or not self.stale:
                    logger.warning("Modbus source unavailable: %s", exc)
                self.connected = False
                self.stale = True
                await self.status_handler(False, True, str(exc))
                self.client.close()
                delay = min(max(delay * 2, 0.5), 5.0)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _poll(self) -> None:
        if self.client is None:
            raise ConnectionError("Modbus client is not initialized")
        coils, header, product_data = await asyncio.gather(
            self.client.read_coils(0, count=STATUS_COIL_COUNT, slave=self.unit_id),
            self.client.read_holding_registers(
                0, count=REG_PRODUCT_COUNT + 1, slave=self.unit_id),
            self.client.read_holding_registers(
                PRODUCT_BASE, count=PRODUCT_STRIDE * MAX_PRODUCTS,
                slave=self.unit_id),
        )
        if coils.isError() or header.isError() or product_data.isError():
            raise ConnectionError("Invalid Modbus response")
        values = [0] * HOLDING_REGISTER_COUNT
        values[:len(header.registers)] = header.registers
        values[PRODUCT_BASE:PRODUCT_BASE + len(product_data.registers)] = product_data.registers
        if values[REG_SCHEMA_VERSION] != SCHEMA_VERSION:
            raise ConnectionError(
                f"Unsupported register map {values[REG_SCHEMA_VERSION]}")
        now = asyncio.get_running_loop().time()
        heartbeat = values[REG_HEARTBEAT]
        if heartbeat != self._last_heartbeat:
            self._last_heartbeat = heartbeat
            self._last_heartbeat_at = now
        self.stale = now - self._last_heartbeat_at > self.stale_timeout
        await self.status_handler(True, self.stale, None)
        if self.stale:
            return
        flags = coils.bits
        product_count = min(values[REG_PRODUCT_COUNT], MAX_PRODUCTS)
        products: list[ProductState] = []
        for index in range(product_count):
            offset = PRODUCT_BASE + index * PRODUCT_STRIDE
            result_code = values[offset + 2]
            if not values[offset + 3] or result_code not in (RESULT_GOOD, RESULT_REJECT):
                continue
            products.append(ProductState(
                id=values[offset], position=values[offset + 1] / 100,
                result=ProductResult.GOOD if result_code == RESULT_GOOD else ProductResult.REJECT,
            ))
        state = MachineState(
            timestamp=datetime.now(timezone.utc),
            machine=MachineFlags(power=flags[COIL_POWER], running=flags[COIL_RUNNING],
                                 emergency=flags[COIL_EMERGENCY]),
            conveyor=ConveyorState(running=flags[COIL_CONVEYOR],
                                   speed=values[REG_CONVEYOR_SPEED] / 1000),
            sensors=SensorState(photo_1=flags[COIL_SENSOR_1], photo_2=flags[COIL_SENSOR_2]),
            cylinder=Cylinder(state=CylinderState.EXTENDED if flags[COIL_CYLINDER]
                              else CylinderState.RETRACTED),
            production=ProductionState(
                total=decode_u32(values[REG_TOTAL_HI], values[REG_TOTAL_HI + 1]),
                good=decode_u32(values[REG_GOOD_HI], values[REG_GOOD_HI + 1]),
                reject=decode_u32(values[REG_REJECT_HI], values[REG_REJECT_HI + 1]),
                ppm=values[REG_PPM],
            ),
            products=products,
        )
        await self.state_handler(state)
