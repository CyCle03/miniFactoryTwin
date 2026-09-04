import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from .models import CommandMessage, MachineState, empty_machine_state
from .mqtt_client import MqttBridge
from .websocket_manager import WebSocketManager

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

manager = WebSocketManager()
latest_state = empty_machine_state()


async def receive_state(state: MachineState) -> None:
    global latest_state
    latest_state = state
    await manager.broadcast(state)


mqtt_bridge = MqttBridge(
    host=os.getenv("MQTT_HOST", "localhost"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    state_topic=os.getenv("MQTT_STATE_TOPIC", "factory/machine/state"),
    command_topic=os.getenv("MQTT_COMMAND_TOPIC", "factory/machine/command"),
    state_handler=receive_state,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    mqtt_bridge.start(asyncio.get_running_loop())
    yield
    mqtt_bridge.stop()


app = FastAPI(
    title="MiniFactoryTwin API",
    version="0.1.0",
    description="MQTT-to-WebSocket bridge for the MiniFactoryTwin conveyor cell.",
    lifespan=lifespan,
)

cors_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "mqtt_connected": mqtt_bridge.connected}


@app.get("/api/state", response_model=MachineState)
async def get_state() -> MachineState:
    return latest_state


@app.post("/api/commands", status_code=status.HTTP_202_ACCEPTED)
async def post_command(command: CommandMessage) -> dict[str, str]:
    if not mqtt_bridge.publish_command(command):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MQTT broker is not connected",
        )
    logger.info("Published machine command: %s", command.command.value)
    return {"status": "accepted", "command": command.command.value}


@app.websocket("/ws/machine")
async def machine_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_text(latest_state.model_dump_json())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
        logger.exception("WebSocket connection failed")

