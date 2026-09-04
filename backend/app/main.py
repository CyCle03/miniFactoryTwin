import asyncio
import logging
import os
from contextlib import asynccontextmanager

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from .history import HistoryRepository
from .models import (AnalyticsSummary, CommandMessage, EventRecord, EventSeverity,
                     MachineEvent, MachineState, ProductResult, ProductionBucket,
                     ProductionRecord, empty_machine_state)
from .mqtt_client import MqttBridge
from .websocket_manager import WebSocketManager

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

manager = WebSocketManager()
history = HistoryRepository(os.getenv("DATABASE_PATH", "./data/minifactory.db"))
latest_state = empty_machine_state()
local_mode = os.getenv("LOCAL_SIMULATION", "false").lower() in {"1", "true", "yes"}
local_runtime: object | None = None


async def receive_state(state: MachineState) -> None:
    global latest_state
    latest_state = state
    await manager.broadcast(state)


async def receive_event(event: MachineEvent) -> None:
    history.record_event(event)


mqtt_bridge = MqttBridge(
    host=os.getenv("MQTT_HOST", "localhost"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    state_topic=os.getenv("MQTT_STATE_TOPIC", "factory/machine/state"),
    command_topic=os.getenv("MQTT_COMMAND_TOPIC", "factory/machine/command"),
    event_topic=os.getenv("MQTT_EVENT_TOPIC", "factory/machine/event"),
    state_handler=receive_state,
    event_handler=receive_event,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global local_runtime
    del app
    if local_mode:
        # Delayed import keeps production Docker images independent of this
        # development-only adapter and the simulator package.
        from .local_simulator import LocalSimulatorRuntime

        local_runtime = LocalSimulatorRuntime(receive_state, receive_event)
        await local_runtime.start()
        logger.info("Local simulator mode enabled; MQTT is bypassed")
    else:
        mqtt_bridge.start(asyncio.get_running_loop())
    yield
    if local_runtime is not None:
        await local_runtime.stop()  # type: ignore[union-attr]
        local_runtime = None
    else:
        mqtt_bridge.stop()


app = FastAPI(
    title="MiniFactoryTwin API",
    version="0.2.0",
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
    return {
        "status": "ok",
        "mqtt_connected": mqtt_bridge.connected,
        "local_simulation": local_mode,
    }


@app.get("/api/state", response_model=MachineState)
async def get_state() -> MachineState:
    return latest_state


@app.post("/api/commands", status_code=status.HTTP_202_ACCEPTED)
async def post_command(command: CommandMessage) -> dict[str, str]:
    if local_runtime is not None:
        await local_runtime.handle_command(command)  # type: ignore[union-attr]
        logger.info("Applied local machine command: %s", command.command.value)
        return {"status": "accepted", "command": command.command.value}
    if not mqtt_bridge.publish_command(command):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MQTT broker is not connected",
        )
    logger.info("Published machine command: %s", command.command.value)
    return {"status": "accepted", "command": command.command.value}


@app.get("/api/history/production", response_model=list[ProductionRecord])
def production_history(limit: int = Query(50, ge=1, le=500), start: datetime | None = None, end: datetime | None = None, result: ProductResult | None = None):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    return history.production(limit, start, end, result)


@app.get("/api/history/events", response_model=list[EventRecord])
def event_history(limit: int = Query(50, ge=1, le=500), start: datetime | None = None, end: datetime | None = None, severity: EventSeverity | None = None, event_type: str | None = Query(None, min_length=1, max_length=80)):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    return history.events(limit, start, end, severity.value if severity else None, event_type)


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary():
    return history.summary()


@app.get("/api/analytics/production", response_model=list[ProductionBucket])
def production_analytics(limit: int = Query(24, ge=1, le=168)):
    return history.buckets(limit)


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
