import asyncio

from backend.app.modbus_adapter import ModbusAdapter
from backend.app.modbus_map import (
    HOLDING_REGISTER_COUNT, PRODUCT_BASE, PRODUCT_STRIDE, REG_COMMAND_ACK,
    REG_CONVEYOR_SPEED, REG_GOOD_HI, REG_HEARTBEAT, REG_PRODUCT_COUNT,
    REG_SCHEMA_VERSION, REG_TOTAL_HI, RESULT_GOOD, SCHEMA_VERSION, encode_u32,
)


class Response:
    def __init__(self, *, registers=None, bits=None, error=False):
        self.registers = registers or []
        self.bits = bits or []
        self._error = error

    def isError(self):
        return self._error


class FakeClient:
    def __init__(self):
        self.connected = True
        self.ack = 3
        self.written = None

    async def read_coils(self, address, *, count, slave):
        return Response(bits=[True, True, False, True, False, True, False])

    async def read_holding_registers(self, address, *, count, slave):
        if address == REG_COMMAND_ACK:
            value = self.ack
            if self.written is not None:
                self.ack += 1
            return Response(registers=[value])
        values = [0] * HOLDING_REGISTER_COUNT
        values[REG_SCHEMA_VERSION] = SCHEMA_VERSION
        values[REG_HEARTBEAT] = 10
        values[REG_CONVEYOR_SPEED] = 750
        values[REG_TOTAL_HI:REG_TOTAL_HI + 2] = encode_u32(4)
        values[REG_GOOD_HI:REG_GOOD_HI + 2] = encode_u32(4)
        values[REG_PRODUCT_COUNT] = 1
        values[PRODUCT_BASE:PRODUCT_BASE + PRODUCT_STRIDE] = [7, 4250, RESULT_GOOD, 1]
        return Response(registers=values[address:address + count])

    async def write_coil(self, address, value, *, slave):
        self.written = (address, value, slave)
        return Response()

    async def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False


def make_adapter(states, statuses):
    async def state_handler(state):
        states.append(state)

    async def status_handler(*status):
        statuses.append(status)

    adapter = ModbusAdapter("fake", 5020, 1, 0.1, 2, 0.5,
                            state_handler, status_handler)
    adapter.client = FakeClient()
    return adapter


def test_register_decoding_and_command_acknowledgement() -> None:
    async def scenario():
        states = []
        statuses = []
        adapter = make_adapter(states, statuses)
        adapter.connected = True
        adapter.stale = False
        await adapter._poll()
        assert states[0].production.total == 4
        assert states[0].conveyor.speed == 0.75
        assert states[0].products[0].id == 7
        assert await adapter.command("start") is True
        assert adapter.client.written == (100, True, 1)

    asyncio.run(scenario())


def test_invalid_register_map_is_rejected() -> None:
    async def scenario():
        adapter = make_adapter([], [])
        original = adapter.client.read_holding_registers

        async def invalid(address, *, count, slave):
            response = await original(address, count=count, slave=slave)
            if address == 0:
                response.registers[0] = 99
            return response

        adapter.client.read_holding_registers = invalid
        try:
            await adapter._poll()
        except ConnectionError as exc:
            assert "Unsupported register map" in str(exc)
        else:
            raise AssertionError("invalid schema was accepted")

    asyncio.run(scenario())
