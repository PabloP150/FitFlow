# FitFlow — Roadmap de Tasks

Proyecto de Postgrado en Diseño y Desarrollo de Software, Universidad Galileo. Ver [`README.md`](./README.md) para arquitectura, setup y guías de uso detalladas.

## Tabla de progreso

| Task | Descripción | Estado | Verificación |
|------|-------------|--------|--------------|
| 1 | Microservicios (users-svc, booking-svc, notif-svc) + Docker Compose + Database per Service | ✅ Completado | `docker compose up --build` + health checks + flujo E2E manual |
| 2A | Service discovery dinámico con Consul (auto-registro + resolución en runtime) | ✅ Completado | Consul UI (`:8500`) muestra 3 servicios en verde; booking-svc resuelve notif-svc vía Consul |
| 2B | MCP Server (`fitflow-mcp`) + integración Claude Desktop (3 tools) | ✅ Completado | 3 tools visibles en Claude Desktop; conversaciones de ejemplo en `README.md` |
| 3 | Resiliencia (retry+backoff+jitter, circuit breaker, outbox pattern) + Observabilidad (logs JSON, `x-correlation-id`) | ✅ Completado | `./demo.sh`; ver detalle abajo |
| 4 | Seguridad (ownership checks, JWT endurecido) + README + demo automatizado | ✅ Completado | `./demo.sh`; ver detalle abajo |
| 5 | Agent-to-Agent (Orchestrator/Booking/Notification Agents, Agent Cards) | ⏳ Pendiente | — |
| Extra | Despliegue cloud (+15 pts) | ⏳ Pendiente | — |

---

## Task 3 — Resiliencia + Observabilidad

**Objetivo**: la llamada booking-svc → notif-svc debe sobrevivir fallos transitorios y caídas prolongadas de notif-svc sin afectar la creación de reservas, y todo el sistema debe ser rastreable vía logs estructurados.

**Entregables**:
- [x] `booking-svc/app/resilience.py` — retry con backoff exponencial + jitter (`tenacity`, 3 intentos) + circuit breaker (`circuitbreaker`, abre tras 3 fallos, `recovery_timeout=10s`)
- [x] `booking-svc/app/outbox.py` — worker en background (poll cada 10s) que reintenta notificaciones encoladas en `pending_notifications` hasta 10 intentos
- [x] `booking-svc/app/models.py` — tabla `PendingNotification` (outbox)
- [x] `booking-svc/app/notif_client.py` — reescrito para usar `resilience.py`, cae a outbox en fallo, nunca lanza excepción hacia el router
- [x] `booking-svc/app/main.py` — `lifespan` lanza el worker del outbox como `asyncio.create_task`, con shutdown coordinado por `asyncio.Event`
- [x] `{users,booking,notif}-svc/app/logging_config.py` — `structlog` + `logging.ProcessorFormatter`, logs 100% JSON (propios y de librerías como uvicorn)
- [x] `{users,booking,notif}-svc/app/middleware.py` — `CorrelationIdMiddleware`: genera/propaga `x-correlation-id`, lo enlaza a contextvars de structlog, lo devuelve en el response header, loguea `http.request` por cada request
- [x] `booking-svc/app/routers/bookings.py` — reenvía el correlation id a la llamada saliente a notif-svc

**Verificación realizada**:
1. Logs JSON confirmados en los 3 servicios (`docker compose logs <svc> | grep correlation_id`) — cada línea es un objeto JSON válido con `service`, `level`, `event`, `timestamp`, `correlation_id`.
2. Ciclo completo de resiliencia probado en vivo:
   - `docker compose stop notif-svc` → `POST /bookings` sigue devolviendo `201` (la reserva se crea igual); la notificación queda en `pending_notifications`.
   - `docker compose start notif-svc` → a los ~10-15s el outbox worker la entrega automáticamente (verificado con `GET /notifications/user/{id}` mostrando el conteo aumentado).
3. Retry + circuit breaker probados directamente contra el contenedor real (`docker compose exec booking-svc python -c "..."`, dentro de UN mismo proceso para que el estado del breaker persista, tal como corre en producción):
   - 3 llamadas fallidas consecutivas (con backoff visible en los logs de tenacity) → circuito se abre.
   - Llamada 4 falla en `<10ms` con `CircuitBreakerError` (sin tocar la red) — confirma que el circuito está abierto.
   - Tras esperar el `recovery_timeout` (10s), una llamada de sonda contra el notif-svc real (ya sano) tiene éxito → el circuito se cierra; la siguiente llamada vuelve a comportarse con normalidad.

**Decisiones de diseño documentadas en el código** (`resilience.py`, `outbox.py`):
- `circuitbreaker==2.1.3` es async-aware (detecta `iscoroutinefunction` automáticamente) — se usa siempre como decorador, nunca invocando `call_async()` manualmente.
- Orden de decoradores importa: `@circuit` envuelve a `@retry` (no al revés), así el circuit breaker cuenta como "un fallo" el resultado FINAL de una llamada (tras agotar los reintentos), no cada intento individual.
- Se distinguen `NotifServiceError` (red/timeout/5xx — reintentable, cuenta contra el breaker) de `NotifServiceClientError` (4xx — "nuestra culpa", sin retry, no cuenta contra el breaker).
- El outbox worker reintenta pasando por el MISMO `call_notif_service` (retry + breaker incluidos) — así sus llamadas también actúan como sonda para detectar la recuperación de notif-svc.

---

## Task 4 — Seguridad + README + Demo

**Objetivo**: endurecer la validación de JWT, agregar verificación de ownership en los endpoints que exponen datos de usuario, y documentar/automatizar la demo end-to-end.

**Entregables**:
- [x] `booking-svc/app/security.py` — `decode_token` captura `pydantic.ValidationError` además de `jwt.InvalidTokenError` (antes: un JWT válido pero con payload incompleto producía un `500`, no un `401`)
- [x] `booking-svc/app/routers/bookings.py` — ownership checks: `GET /bookings/{id}` ahora requiere JWT; `GET` y `POST /bookings/{id}/cancel` devuelven `403` si `booking.user_id != user_id` del token
- [x] `notif-svc/app/config.py` — agrega `JWT_SECRET_KEY`, `JWT_ALGORITHM`
- [x] `notif-svc/app/security.py` (nuevo) — espejo de `booking-svc/app/security.py`
- [x] `notif-svc/app/routers/notifications.py` — `GET /notifications/user/{user_id}` ahora requiere JWT + ownership (`403` si el token es de otro usuario)
- [x] `README.md` — secciones nuevas de Resiliencia, Observabilidad, Seguridad, Demo automatizado; tabla de progreso; endpoints/ejemplos actualizados con los nuevos requisitos de auth
- [x] `demo.sh` (nuevo) — automatiza el flujo completo (health checks → registro/login → clases → reserva + correlation-id → notificaciones con JWT → ownership con un segundo usuario → ciclo completo de resiliencia) con verificación `[OK]`/`[FAIL]` por paso

**Verificación realizada** (todas con `./demo.sh`, 0 fallos):
- `GET /bookings/{id}` con JWT de otro usuario → `403`.
- `GET /notifications/user/{id}` con JWT de otro usuario → `403`.
- `GET /notifications/user/{id}` sin JWT → `401`.
- Token con payload incompleto (firma válida, sin `user_id`) → `401` consistente (verificado directamente vía `curl`, confirmando que ya no es un `500`).

**Nota sobre gestión de secretos**: `JWT_SECRET_KEY` y credenciales de BD viven en `.env` (gitignored), cargadas vía `env_file` en `docker-compose.yml`. `.env.example` documenta las variables sin exponer secretos reales. Para producción, `JWT_SECRET_KEY` debe rotarse y gestionarse con un secret manager real (no vive en texto plano en ningún repo).

---

## Task 5 — Agent-to-Agent (A2A) [pendiente]

- Introducir Orchestrator Agent, Booking Agent, Notification Agent.
- Cada agente publica un Agent Card en `/.well-known/agent.json`.
- Agentes se descubren entre sí vía Agent Cards (análogo a Consul, pero para agentes).
- Demostración: Claude Desktop → Orchestrator Agent → Booking/Notification Agents → servicios reales.

## Punto extra — Despliegue cloud [pendiente]

- Railway, Render, o Fly.io (recomendado para simplicidad), o AWS (ECS Fargate + RDS) / Google Cloud (Cloud Run + Cloud SQL).
- Secretos manejados con el servicio de secrets del proveedor, no `.env`.
