import asyncio
import json
import logging
import os
import time

import paho.mqtt.client as mqtt
from pymodbus.datastore import (
    ModbusSlaveContext, ModbusSequentialDataBlock, ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

from modbus_map import (
    COIL_CONVEYOR, COIL_CYLINDER, COIL_EMERGENCY, COIL_POWER, COIL_RUNNING,
    COIL_SENSOR_1, COIL_SENSOR_2, COMMAND_COILS, HOLDING_REGISTER_COUNT,
    MAX_PRODUCTS, PRODUCT_BASE, PRODUCT_STRIDE, REG_COMMAND_ACK,
    REG_CONVEYOR_SPEED, REG_GOOD_HI, REG_HEARTBEAT, REG_PPM,
    REG_PRODUCT_COUNT, REG_REJECT_HI, REG_SCHEMA_VERSION, REG_TOTAL_HI,
    RESULT_GOOD, RESULT_REJECT, SCHEMA_VERSION, STATUS_COIL_COUNT, encode_u32,
)
from simulator.constants import SimulationConfig
from simulator.machine import MachineSimulator

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class ModbusDeviceSimulator:
    def __init__(self) -> None:
        block_size = max(HOLDING_REGISTER_COUNT + 10, max(COMMAND_COILS.values()) + 10)
        self.device = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * block_size),
            co=ModbusSequentialDataBlock(0, [0] * block_size),
            hr=ModbusSequentialDataBlock(0, [0] * block_size),
            ir=ModbusSequentialDataBlock(0, [0] * block_size),
        )
        self.context = ModbusServerContext(slaves={1: self.device}, single=False)
        good_rate = float(os.getenv("SIM_GOOD_RATE", "0.95"))
        self.machine = MachineSimulator(SimulationConfig(good_probability=good_rate))
        self.tick_rate = float(os.getenv("SIM_TICK_RATE", "20"))
        self.heartbeat = 0
        self.command_ack = 0
        self.event_topic = os.getenv("MQTT_EVENT_TOPIC", "factory/machine/event")
        self.mqtt = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="minifactory-modbus-simulator",
        )
        self.mqtt.connect_async(os.getenv("MQTT_HOST", "mosquitto"),
                                int(os.getenv("MQTT_PORT", "1883")), 30)
        self.mqtt.loop_start()

    async def run_machine(self) -> None:
        interval = 1 / self.tick_rate
        previous = time.monotonic()
        while True:
            current = time.monotonic()
            self._handle_commands()
            self.machine.tick(min(current - previous, 0.25), current)
            previous = current
            self._publish_events()
            self._write_state(current)
            await asyncio.sleep(interval)

    def _handle_commands(self) -> None:
        for command, address in COMMAND_COILS.items():
            if self.device.getValues(1, address, count=1)[0]:
                try:
                    self.machine.handle_command(command)
                finally:
                    self.device.setValues(1, address, [False])
                    self.command_ack = (self.command_ack + 1) & 0xFFFF

    def _write_state(self, now: float) -> None:
        state = self.machine.state(now)
        machine = state["machine"]
        sensors = state["sensors"]
        production = state["production"]
        coils = [False] * STATUS_COIL_COUNT
        coils[COIL_POWER] = bool(machine["power"])
        coils[COIL_RUNNING] = bool(machine["running"])
        coils[COIL_EMERGENCY] = bool(machine["emergency"])
        coils[COIL_CONVEYOR] = bool(state["conveyor"]["running"])
        coils[COIL_SENSOR_1] = bool(sensors["photo_1"])
        coils[COIL_SENSOR_2] = bool(sensors["photo_2"])
        coils[COIL_CYLINDER] = state["cylinder"]["state"] == "extended"
        self.device.setValues(1, 0, coils)

        self.heartbeat = (self.heartbeat + 1) & 0xFFFF
        registers = [0] * HOLDING_REGISTER_COUNT
        registers[REG_SCHEMA_VERSION] = SCHEMA_VERSION
        registers[REG_HEARTBEAT] = self.heartbeat
        registers[REG_COMMAND_ACK] = self.command_ack
        registers[REG_CONVEYOR_SPEED] = round(float(state["conveyor"]["speed"]) * 1000)
        registers[REG_TOTAL_HI:REG_TOTAL_HI + 2] = encode_u32(int(production["total"]))
        registers[REG_GOOD_HI:REG_GOOD_HI + 2] = encode_u32(int(production["good"]))
        registers[REG_REJECT_HI:REG_REJECT_HI + 2] = encode_u32(int(production["reject"]))
        registers[REG_PPM] = min(int(production["ppm"]), 0xFFFF)
        products = list(state["products"])[:MAX_PRODUCTS]
        registers[REG_PRODUCT_COUNT] = len(products)
        for index, product in enumerate(products):
            offset = PRODUCT_BASE + index * PRODUCT_STRIDE
            registers[offset] = int(product["id"]) & 0xFFFF
            registers[offset + 1] = round(float(product["position"]) * 100)
            registers[offset + 2] = RESULT_GOOD if product["result"] == "GOOD" else RESULT_REJECT
            registers[offset + 3] = 1
        self.device.setValues(3, 0, registers)

    def _publish_events(self) -> None:
        for event in self.machine.drain_events():
            self.mqtt.publish(self.event_topic, json.dumps(event, separators=(",", ":")), qos=1)


async def main() -> None:
    simulator = ModbusDeviceSimulator()
    host = os.getenv("MODBUS_BIND", "0.0.0.0")
    port = int(os.getenv("MODBUS_PORT", "5020"))
    logger.info("Starting Modbus TCP simulator at %s:%d", host, port)
    await asyncio.gather(
        simulator.run_machine(),
        StartAsyncTcpServer(context=simulator.context, address=(host, port)),
    )


if __name__ == "__main__":
    asyncio.run(main())
