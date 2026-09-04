import asyncio
import logging
import uuid
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from .models import CommandMessage, MachineEvent, MachineState

logger = logging.getLogger(__name__)
StateHandler = Callable[[MachineState], Awaitable[None]]
EventHandler = Callable[[MachineEvent], Awaitable[None]]


class MqttBridge:
    def __init__(
        self,
        host: str,
        port: int,
        state_topic: str,
        command_topic: str,
        event_topic: str,
        state_handler: StateHandler,
        event_handler: EventHandler,
    ) -> None:
        self.host = host
        self.port = port
        self.state_topic = state_topic
        self.command_topic = command_topic
        self.event_topic = event_topic
        self._state_handler = state_handler
        self._event_handler = event_handler
        self._loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="minifactory-backend",
            protocol=mqtt.MQTTv311,
        )
        self.client.enable_logger(logger)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        try:
            self.client.connect_async(self.host, self.port, keepalive=30)
            self.client.loop_start()
            logger.info("Connecting to MQTT at %s:%d", self.host, self.port)
        except OSError as exc:
            logger.error("Unable to start MQTT client: %s", exc)

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def publish_command(self, command: CommandMessage) -> bool:
        if not self.connected:
            return False
        result = self.client.publish(
            self.command_topic,
            command.model_dump_json(),
            qos=1,
        )
        return result.rc == mqtt.MQTT_ERR_SUCCESS

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
        client.subscribe([(self.state_topic, 0), (self.event_topic, 1)])
        logger.info("MQTT connected; subscribed to %s", self.state_topic)

    def _record_connection_error(self, message: str) -> None:
        if self._loop is None:
            return
        event = MachineEvent(event_id=str(uuid.uuid4()), session_id="backend", timestamp=datetime.now(timezone.utc), event_type="mqtt_connection_error", severity="ERROR", message=message)
        future = asyncio.run_coroutine_threadsafe(self._event_handler(event), self._loop)
        future.add_done_callback(self._log_handler_error)

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
            self._record_connection_error(f"MQTT connection lost: {reason_code}")
        else:
            logger.info("MQTT disconnected")

    def _on_message(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        del client, userdata
        try:
            if message.topic == self.event_topic:
                event = MachineEvent.model_validate_json(message.payload)
                handler = self._event_handler
                value = event
            else:
                handler = self._state_handler
                value = MachineState.model_validate_json(message.payload)
        except ValidationError as exc:
            logger.warning("Discarding invalid MachineState: %s", exc)
            return

        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(handler(value), self._loop)
        future.add_done_callback(self._log_handler_error)

    @staticmethod
    def _log_handler_error(future: "asyncio.Future[None]") -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Failed to forward machine state")

