# Security and Network Exposure

This document records the security controls currently used by the deployed
MiniFactoryTwin v0.3 application. It describes the repository configuration and
the headers observed at https://factory.elcherlab.com on 2026-09-04.

## Network boundary

The production Compose stack publishes only the frontend through
127.0.0.1:3800. Caddy is the public HTTPS reverse proxy.

The FastAPI backend (TCP 8000), Mosquitto (TCP 1883), and Modbus TCP simulator
(TCP 5020) are private to the Docker network and have no host port. Do not add
public mappings for these services. A real PLC should be reached through a
trusted private network or VPN. Modbus itself supplies neither authentication
nor encryption.

## Active HTTP response headers

Caddy imports the shared security_headers snippet and applies an
application-specific Content-Security-Policy. Deployed HTML and API responses
currently include:

| Header | Current policy |
| --- | --- |
| Strict-Transport-Security | max-age=31536000; includeSubDomains |
| X-Content-Type-Options | nosniff |
| X-Frame-Options | SAMEORIGIN |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | Disables unused browser capabilities |
| Content-Security-Policy | Deny by default with narrow application exceptions |

The CSP disables object embedding and form submission, prevents base URL
rewriting, limits framing to the same origin, and upgrades insecure requests.
The canonical site configuration is
[ops/Caddyfile.factory](../ops/Caddyfile.factory).

## Deferred CSP tightening

The current CSP contains style-src 'unsafe-inline'. The React HMI currently
needs it for computed product positions and chart heights.

Removing this exception is intentionally deferred. First migrate dynamic
presentation to nonce/hash-compatible styles, CSS custom properties, or
predefined classes, then verify conveyor animation and charts on desktop and
mobile. Removing it before that migration would break live visualization.

The CSP also permits the Cloudflare browser-insight origins used in production.
Remove those origins if that feature is disabled.

## Application controls

- Pydantic validates state, commands, events, and API response models.
- History APIs enforce bounded limits and typed filters.
- SQLite uses transactions, WAL, a busy timeout, and a persistent named volume.
- Stable event and session/product identifiers prevent duplicate history rows.
- Modbus commands are rejected when the source is disconnected or stale.
- Command writes require an acknowledgement counter change.
- Unknown Modbus register-map versions are rejected.
- Source switching is explicit and requires service recreation.

RESET clears live simulation state but never deletes SQLite history. No
history-deletion endpoint exists.

## Verification

Run after Caddy or deployment changes:

    curl -sSI https://factory.elcherlab.com
    curl -sSI https://factory.elcherlab.com/api/state
    docker compose -f docker-compose.prod.yml ps
    docker compose -f docker-compose.prod.yml config --quiet

Confirm that the listed headers remain present and only 127.0.0.1:3800 is
host-published by the application stack.

## Deferred security work

- Remove style-src 'unsafe-inline' after the dynamic-style refactor.
- Add authenticated, encrypted MQTT before allowing untrusted clients.
- Use a private routed network or VPN for a physical PLC.
- Add user authentication only in a separately scoped release; it is not part
  of v0.3.
