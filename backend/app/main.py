import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .history import HistoryRepository
from .models import (
    AnalyticsSummary, CommandMessage, EventRecord, EventSeverity, MachineEvent,
    MachineState, ProductResult, ProductionBucket, ProductionRecord,
    SourceStatus, empty_machine_state,
)
from .modbus_adapter import ModbusAdapter
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
data_source = os.getenv("DATA_SOURCE", "mqtt").lower()
local_mode = os.getenv("LOCAL_SIMULATION", "false").lower() in {"1", "true", "yes"}
source_connected = False
source_stale = True
source_error: str | None = None
local_runtime: object | None = None
inspection_image_directory = Path(
    os.getenv("VISION_IMAGE_DIR", "/app/inspection-images")
).resolve()


async def receive_state(state: MachineState) -> None:
    global latest_state, source_connected, source_stale, source_error
    latest_state = state
    if data_source in {"mqtt", "local"}:
        source_connected, source_stale, source_error = True, False, None
    await manager.broadcast(state)


async def receive_event(event: MachineEvent) -> None:
    history.record_event(event)


async def receive_modbus_status(connected: bool, stale: bool, error: str | None) -> None:
    global source_connected, source_stale, source_error
    was_failed = not source_connected or source_stale
    source_connected, source_stale, source_error = connected, stale, error
    if (not connected or stale) and not was_failed:
        await receive_event(MachineEvent(
            event_id=str(uuid.uuid4()), session_id="backend",
            timestamp=datetime.now(timezone.utc), event_type="modbus_connection_error",
            severity=EventSeverity.ERROR,
            message=error or "Modbus data is stale",
        ))


mqtt_bridge = MqttBridge(
    host=os.getenv("MQTT_HOST", "localhost"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    state_topic=os.getenv("MQTT_STATE_TOPIC", "factory/machine/state"),
    command_topic=os.getenv("MQTT_COMMAND_TOPIC", "factory/machine/command"),
    event_topic=os.getenv("MQTT_EVENT_TOPIC", "factory/machine/event"),
    state_handler=receive_state,
    event_handler=receive_event,
    accept_state=data_source == "mqtt",
)
modbus_adapter = ModbusAdapter(
    host=os.getenv("MODBUS_HOST", "modbus-simulator"),
    port=int(os.getenv("MODBUS_PORT", "5020")),
    unit_id=int(os.getenv("MODBUS_UNIT_ID", "1")),
    poll_interval=float(os.getenv("MODBUS_POLL_INTERVAL", "0.1")),
    stale_timeout=float(os.getenv("MODBUS_STALE_TIMEOUT", "2.0")),
    command_timeout=float(os.getenv("MODBUS_COMMAND_TIMEOUT", "2.0")),
    state_handler=receive_state,
    status_handler=receive_modbus_status,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global local_runtime, data_source, source_connected, source_stale
    del app
    if local_mode:
        from .local_simulator import LocalSimulatorRuntime
        data_source = "local"
        local_runtime = LocalSimulatorRuntime(receive_state, receive_event)
        await local_runtime.start()
        logger.info("Local simulator mode enabled")
    elif data_source == "modbus":
        mqtt_bridge.start(asyncio.get_running_loop())
        await modbus_adapter.start()
        logger.info("Modbus source enabled")
    elif data_source == "mqtt":
        mqtt_bridge.start(asyncio.get_running_loop())
    else:
        raise RuntimeError(f"Unsupported DATA_SOURCE: {data_source}")
    yield
    if local_runtime is not None:
        await local_runtime.stop()  # type: ignore[union-attr]
        local_runtime = None
    elif data_source == "modbus":
        await modbus_adapter.stop()
        mqtt_bridge.stop()
    else:
        mqtt_bridge.stop()
    source_connected, source_stale = False, True


app = FastAPI(
    title="MiniFactoryTwin API", version="0.4.0",
    description="Source-neutral MQTT/Modbus backend for MiniFactoryTwin.",
    lifespan=lifespan,
)
cors_origins = [value.strip() for value in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=cors_origins, allow_credentials=True,
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)


def current_source_status() -> SourceStatus:
    if data_source == "mqtt":
        age = (datetime.now(timezone.utc) - latest_state.timestamp).total_seconds()
        connected = mqtt_bridge.connected
        return SourceStatus(source="mqtt", connected=connected,
                            stale=not connected or age > 3, error=None)
    if data_source == "local":
        return SourceStatus(source="local", connected=source_connected,
                            stale=source_stale, error=source_error)
    return SourceStatus(source="modbus", connected=source_connected,
                        stale=source_stale, error=source_error)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    source = current_source_status()
    return {
        "status": "ok", "data_source": source.source,
        "source_connected": source.connected, "source_stale": source.stale,
        "local_simulation": local_mode,
    }


@app.get("/api/source", response_model=SourceStatus)
async def get_source() -> SourceStatus:
    return current_source_status()


@app.get("/api/state", response_model=MachineState)
async def get_state() -> MachineState:
    return latest_state


@app.post("/api/commands", status_code=status.HTTP_202_ACCEPTED)
async def post_command(command: CommandMessage) -> dict[str, str]:
    if local_runtime is not None:
        await local_runtime.handle_command(command)  # type: ignore[union-attr]
    elif data_source == "modbus":
        if not await modbus_adapter.command(command.command.value):
            raise HTTPException(status_code=503, detail="Modbus command was not acknowledged")
    elif not mqtt_bridge.publish_command(command):
        raise HTTPException(status_code=503, detail="MQTT broker is not connected")
    logger.info("Applied %s command through %s", command.command.value, data_source)
    return {"status": "accepted", "command": command.command.value, "source": data_source}


@app.get("/api/history/production", response_model=list[ProductionRecord])
def production_history(limit: int = Query(50, ge=1, le=500), start: datetime | None = None,
                       end: datetime | None = None, result: ProductResult | None = None):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    return history.production(limit, start, end, result)


@app.get("/api/history/events", response_model=list[EventRecord])
def event_history(limit: int = Query(50, ge=1, le=500), start: datetime | None = None,
                  end: datetime | None = None, severity: EventSeverity | None = None,
                  event_type: str | None = Query(None, min_length=1, max_length=80)):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    return history.events(limit, start, end, severity.value if severity else None, event_type)


@app.get("/api/inspection-images/{image_name}", response_class=FileResponse)
async def inspection_image(image_name: str) -> FileResponse:
    """Serve only a named image from the configured read-only inspection directory."""
    if Path(image_name).name != image_name:
        raise HTTPException(status_code=404, detail="Inspection image not found")
    image_path = (inspection_image_directory / image_name).resolve()
    if (
        image_path.parent != inspection_image_directory
        or image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        or not image_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Inspection image not found")
    return FileResponse(image_path, headers={"Cache-Control": "private, max-age=60"})


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
