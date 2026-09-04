import json
import logging
import os
import signal
import threading
import time

import paho.mqtt.client as mqtt

from simulator.constants import SimulationConfig
from simulator.machine import MachineSimulator

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SimulatorService:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.state_topic = os.getenv("MQTT_STATE_TOPIC", "factory/machine/state")
        self.command_topic = os.getenv("MQTT_COMMAND_TOPIC", "factory/machine/command")
        self.tick_rate = float(os.getenv("SIM_TICK_RATE", "20"))
        self.publish_rate = float(os.getenv("SIM_PUBLISH_RATE", "10"))
        good_rate = float(os.getenv("SIM_GOOD_RATE", "0.95"))
        self.machine = MachineSimulator(SimulationConfig(good_probability=good_rate))
        self.machine_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.connected = False
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="minifactory-simulator",
            protocol=mqtt.MQTTv311,
        )
        self.client.enable_logger(logger)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def run(self) -> None:
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()
        logger.info("Simulator started; connecting to MQTT at %s:%d", self.host, self.port)

        tick_interval = 1.0 / self.tick_rate
        publish_interval = 1.0 / self.publish_rate
        previous = time.monotonic()
        next_publish = previous

        try:
            while not self.stop_event.wait(tick_interval):
                current = time.monotonic()
                with self.machine_lock:
                    self.machine.tick(min(current - previous, 0.25), current)
                previous = current
                if current >= next_publish:
                    self._publish_state(current)
                    next_publish = current + publish_interval
        finally:
            self.client.disconnect()
            self.client.loop_stop()
            logger.info("Simulator stopped")

    def stop(self, *_args: object) -> None:
        self.stop_event.set()

    def _publish_state(self, now: float) -> None:
        if not self.connected:
            return
        with self.machine_lock:
            state = self.machine.state(now)
        payload = json.dumps(state, separators=(",", ":"))
        result = self.client.publish(self.state_topic, payload, qos=0, retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("Machine state publish failed (rc=%s)", result.rc)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del userdata, flags, properties
        if reason_code.is_failure:
            logger.error("MQTT connection rejected: %s", reason_code)
            return
        self.connected = True
        client.subscribe(self.command_topic, qos=1)
        logger.info("MQTT connected; subscribed to %s", self.command_topic)
        self._publish_state(time.monotonic())

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self.connected = False
        if reason_code.is_failure:
            logger.warning("MQTT connection lost: %s", reason_code)

    def _on_message(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            command = payload["command"]
            if not isinstance(command, str):
                raise ValueError("command must be a string")
            with self.machine_lock:
                self.machine.handle_command(command)
            logger.info("Applied machine command: %s", command)
            self._publish_state(time.monotonic())
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Ignoring invalid command payload: %s", exc)


def main() -> None:
    service = SimulatorService()
    signal.signal(signal.SIGINT, service.stop)
    signal.signal(signal.SIGTERM, service.stop)
    service.run()


if __name__ == "__main__":
    main()
