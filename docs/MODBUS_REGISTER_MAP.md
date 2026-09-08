# Modbus TCP Register Map v1

All addresses are zero-based PDU addresses, values are unsigned 16-bit words,
and the device unit ID defaults to 1. Multiword counters use big-endian word
order. The simulator listens only on the Compose network at TCP 5020; no host
port is published.

## Read-only coils

| Address | Meaning |
| ---: | --- |
| 0 | Power |
| 1 | Running |
| 2 | Emergency active |
| 3 | Conveyor running |
| 4 | Photo sensor 1 |
| 5 | Photo sensor 2 |
| 6 | Reject cylinder extended |

## Command coils

Writing true requests one command. The simulator consumes and clears the coil.
A successful application increments holding register 2.

| Address | Command |
| ---: | --- |
| 100 | Start |
| 101 | Stop |
| 102 | Reset |
| 103 | Emergency stop |
| 104 | Emergency reset |

## Holding registers

| Address | Meaning | Scale |
| ---: | --- | --- |
| 0 | Map version (1) | — |
| 1 | Heartbeat counter | increments each tick |
| 2 | Command acknowledgement | increments per consumed command |
| 3 | Conveyor speed | m/s × 1000 |
| 4–5 | Total count | uint32 |
| 6–7 | GOOD count | uint32 |
| 8–9 | REJECT count | uint32 |
| 10 | Rolling PPM | — |
| 11 | Active product count | max 16 |
| 100–163 | Product slots | four registers each |

Each product slot contains product ID, position × 100, result (1=GOOD,
2=REJECT), and active flag.

## Safety and replacement

The backend validates map version, register bounds, counter consistency,
heartbeat freshness, and command acknowledgement. A stale or disconnected
source rejects commands with HTTP 503. To replace the simulator with a PLC,
implement this map in the PLC, set MODBUS_HOST, MODBUS_PORT, and MODBUS_UNIT_ID,
and keep the port on a trusted private network. Vendor SDKs and automatic live
source switching are intentionally outside v0.3.
