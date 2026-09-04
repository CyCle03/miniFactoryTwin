# MiniFactoryTwin Development Roadmap

This document turns the high-level roadmap into versioned, testable delivery
milestones. It is intentionally ordered so that every release remains a usable
factory-cell demo while adding one new industrial integration concern at a time.

The roadmap describes planned scope, not fixed release dates. Priorities may
change as real hardware becomes available, but a version is considered complete
only when its acceptance criteria are met.

## Delivery principles

- Keep the React dashboard dependent on shared contracts, not on a specific
  simulator, PLC, camera, or robot implementation.
- Preserve a working end-to-end path in every release.
- Add protocols and infrastructure only when a feature needs them.
- Keep simulated and real-device modes explicit and observable.
- Prefer backward-compatible contract changes and documented migrations.
- Do not add ROS2 or mobile-robot code before the factory-cell foundations are
  stable.

## Version overview

| Version | Theme | Primary outcome | Status |
| --- | --- | --- | --- |
| v0.1 | Working digital twin | Live conveyor cell using MQTT, FastAPI, WebSocket, and React | Complete |
| v0.2 | History and analytics | Persistent production records, events, cycle time, and charts | Complete |
| v0.3 | PLC communication | Modbus TCP simulator, register map, and replaceable PLC adapter | Planned |
| v0.4 | Machine vision | Camera pipeline and YOLO-backed inspection results | Planned |
| v0.5 | Configuration | Configurable components, mappings, and simulated/real modes | Planned |
| v0.6 | Factory scale | Multiple cells and a factory-level layout | Planned |
| Future | Mobile robotics | ROS2/AMR integration after the production-cell platform matures | Deferred |

## v0.1 — Working digital twin

### Objective

Deliver a small but complete production cell that demonstrates a realistic
control and telemetry loop.

### Delivered

- Conveyor and animated product movement
- Photoelectric sensor state changes
- GOOD and REJECT product classification
- Pneumatic reject-cylinder behavior
- Start, stop, reset, emergency stop, and emergency reset controls
- Total, good, reject, yield, and rolling PPM indicators
- Python simulator publishing `MachineState` over MQTT
- FastAPI command API and WebSocket state delivery
- React and TypeScript HMI dashboard
- Local simulation mode for development without MQTT
- Development and production Docker Compose configurations
- OCI deployment behind Caddy at `factory.elcherlab.com`

## v0.2 — Production history and analytics

### Objective

Turn the live demonstration into an observable production system whose results
can be reviewed after a product or container has left the simulation.

### Planned work

- Add persistent SQLite storage backed by a Docker volume.
- Record one production-history row per completed product.
- Store product result, entry time, inspection time, completion time, and cycle
  time.
- Introduce typed machine events for start, stop, emergency, inspection, reject,
  and product completion transitions.
- Store alarm and event history with severity and contextual metadata.
- Add paginated and filterable FastAPI history endpoints.
- Calculate recent, average, minimum, and maximum cycle time.
- Add production volume, GOOD/REJECT, and cycle-time charts to the dashboard.
- Document database persistence, backup, and restore procedures.

### Explicitly out of scope

- User accounts and authorization
- PostgreSQL or a distributed event platform
- PLC, camera, or robot integrations
- Destructive history deletion from the operator dashboard

### Acceptance criteria

- A completed product is recorded exactly once.
- Emergency transitions create events without duplicates from repeated state
  publications.
- History survives application-container recreation and server restart.
- Query endpoints enforce default and maximum result limits.
- Empty or temporarily unavailable history does not break the live HMI.
- Existing MQTT, command, and WebSocket behavior remains compatible.
- Backend tests, simulator tests, frontend lint/type checks, and production build
  pass.

## v0.3 — Modbus TCP and PLC-ready architecture

### Objective

Prove that the UI and backend can operate from an industrial register protocol
without being coupled to the original Python simulator.

### Planned work

- Add a Modbus TCP device simulator for the conveyor cell.
- Define a versioned register and coil map.
- Model command acknowledgement, connection status, timeouts, and stale data.
- Add a Modbus adapter that translates registers into the shared
  `MachineState` contract.
- Add safe command write handling for start, stop, reset, and emergency actions.
- Provide MQTT and Modbus source selection through backend configuration.
- Document how a real PLC adapter can replace the simulator.
- Add integration tests for register decoding, reconnects, invalid values, and
  command writes.

### Explicitly out of scope

- Vendor-specific PLC SDKs
- Changes to a physical PLC program
- Unauthenticated public exposure of a Modbus port
- Automatic control-source switching while the machine is running

### Acceptance criteria

- The same dashboard operates in MQTT-simulator and Modbus-simulator modes.
- Loss of Modbus communication produces a clear stale/offline state rather than
  silently retaining live status.
- Register mappings are documented and covered by automated tests.
- Industrial protocol ports remain private to the trusted network.

## v0.4 — Machine-vision inspection

### Objective

Replace randomized inspection with a reproducible vision pipeline while keeping
the simulator usable when no camera is available.

### Planned work

- Add an OpenCV image-ingestion and preprocessing pipeline.
- Support a sample-image or recorded-stream mode for repeatable development.
- Add a YOLO inference adapter with configurable model path and thresholds.
- Publish typed inspection results containing product ID, class, confidence,
  timing, and optional defect metadata.
- Correlate an inspection result with the correct product at Sensor 2.
- Drive GOOD/REJECT routing from vision output when vision mode is enabled.
- Add an inspection panel with result, confidence, latency, and a safely sized
  preview.
- Store inspection metadata alongside v0.2 production history.
- Add deterministic tests using fixed fixtures and a mock inference adapter.

### Explicitly out of scope

- Training a production-grade custom model
- Uploading arbitrary camera feeds to a public endpoint
- Using face recognition or personally identifiable imagery
- Removing the non-vision simulation mode

### Acceptance criteria

- Fixed test images produce reproducible inspection outcomes.
- Missing, late, or low-confidence results follow a documented fail-safe policy.
- The application still runs without a GPU or physical camera.
- Inspection processing does not block machine-state delivery.

## v0.5 — Component configuration and device modes

### Objective

Move cell-specific constants and I/O mappings into validated configuration so
the project can represent different equipment without code changes.

### Planned work

- Define a versioned cell-configuration schema.
- Configure sensor positions, cylinder position, conveyor speed, timing, and
  product-generation parameters.
- Configure MQTT topics and Modbus register mappings.
- Add explicit `SIMULATED` and `REAL` device modes.
- Validate configuration before starting equipment adapters.
- Display active data source, device mode, and configuration version in the HMI.
- Add import/export support for non-secret configuration.
- Add audit events for configuration changes.
- Provide example configurations for MQTT simulation, Modbus simulation, and a
  real-PLC template.

### Explicitly out of scope

- Storing credentials in exported configuration
- Hot-swapping control sources while machinery is running
- A general-purpose PLC programming environment

### Acceptance criteria

- Invalid or incomplete configuration prevents unsafe startup with a useful
  error message.
- Switching between supported modes requires no source-code change.
- Secrets remain outside version-controlled configuration.
- Existing v0.1 defaults remain available as the reference cell profile.

## v0.6 — Multiple cells and factory layout

### Objective

Scale the single-cell model into a small factory view without weakening cell
isolation or operator clarity.

### Planned work

- Add stable factory, line, cell, and equipment identifiers.
- Support multiple independently updating cell instances.
- Namespace MQTT topics and history records by cell.
- Add a factory layout and cell-level navigation.
- Show aggregate production, alarm, availability, and throughput indicators.
- Isolate commands so an operator action targets exactly one cell.
- Add per-cell health, connection, and stale-data status.
- Add load and integration tests for concurrent state streams.

### Explicitly out of scope

- Full MES, ERP, scheduling, or inventory-management functionality
- Multi-tenant SaaS operation
- Autonomous mobile-robot traffic control

### Acceptance criteria

- At least two simulated cells run concurrently with isolated state and
  commands.
- Factory totals reconcile with their underlying cell totals.
- A failing cell does not interrupt updates from healthy cells.
- The layout remains usable at desktop and tablet widths.

## Future — ROS2, AMR, and TurtleBot digital twin

ROS2 and mobile-robot work begins only after the production-cell contracts,
history model, device configuration, and multi-cell identity model are stable.

Potential work includes:

- ROS2 bridge isolated behind a source adapter
- AMR pose, path, battery, mission, and fault state
- TurtleBot-based development profile
- Factory-map coordinate system and live robot visualization
- Material-transfer events between AMRs and production cells
- Mission dispatch and acknowledgement with explicit safety boundaries

This phase will not place ROS2-specific messages directly in the React UI. ROS2
data will be translated into stable application contracts in the same way that
MQTT and Modbus sources are normalized.

## Definition of done for every version

A version is complete only when all applicable items below are satisfied:

- Scope is implemented without leaving the primary path as placeholder code.
- Automated unit and integration tests cover the new behavior and failure modes.
- Frontend lint, type check, and production build pass.
- Python syntax, imports, tests, and runtime startup checks pass.
- Docker Compose configuration validates on the deployment architecture.
- Existing features pass regression smoke tests.
- Persistent data has documented migration, backup, and rollback considerations.
- Network services use the minimum necessary exposure.
- README and architecture documentation match the shipped implementation.
- The public deployment is healthy after release, or a tested local deployment
  procedure is provided when the feature is not yet intended for production.

