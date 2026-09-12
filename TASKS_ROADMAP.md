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
| 5 | Agent-to-Agent (Orchestrator/Booking/Notification Agents, Agent Cards) | ✅ Completado | `./demo_a2a.sh`; ver detalle abajo |
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

## Task 5 — Agent-to-Agent (A2A)

**Objetivo**: reemplazar la interacción directa usuario → MCP por una red de agentes especializados que se descubren vía Agent Card y se delegan trabajo vía el protocolo A2A.

**Entregables**:
- [x] `booking-agent/` (:9001) — servidor A2A con skills `list_classes`, `create_booking`, `cancel_booking`
- [x] `notification-agent/` (:9002) — servidor A2A con skills `send_notification`, `get_history`
- [x] `orchestrator-agent/` (:9000) — cliente A2A: descubre agentes, consulta a Gemini, delega en secuencia
- [x] Agent Cards servidos en `/.well-known/agent.json` (ruta del enunciado) **y** `/.well-known/agent-card.json` (default del SDK en A2A v1.0)
- [x] `{booking,notification}-agent/app/executor.py` — `AgentExecutor` que traduce cada skill en llamadas a tools del MCP Server
- [x] `{booking,notification}-agent/app/mcp_client.py` — cliente MCP streamable-http contra `fitflow-mcp`, con retry `tenacity`
- [x] `orchestrator-agent/app/nlu_gemini.py` — construye function declarations de Gemini a partir de las skills **descubiertas**, con automatic function calling desactivado
- [x] `orchestrator-agent/app/a2a_dispatch.py` — delegación A2A + logs de comunicación entre agentes
- [x] `orchestrator-agent/app/consul_publish.py` + `static/index.html` — dashboard con el botón "Descubrir agentes vía Agent Card" que los publica en Consul (y "Reiniciar demo" que los da de baja)
- [x] `fitflow-mcp/app/tools.py` — 2 tools nuevas (`send_notification`, `get_notification_history`), registradas en ambos transportes
- [x] `docker-compose.yml` — 3 contenedores nuevos; `fitflow-mcp` deja de estar tras `profiles: ["http"]`
- [x] `demo_a2a.sh` — demo automatizada de toda la task
- [x] `README.md` — sección "Agent-to-Agent" explicando MCP vs A2A

**Verificación realizada**:
1. Los 3 agentes corren como contenedores y responden `/healthz` (11 contenedores en total con `docker compose up`).
2. Agent Cards servidos correctamente en ambas rutas; `skills[].id` coincide con lo esperado.
3. Contraste Consul: antes del botón, `catalog/services` lista solo los 4 servicios de infraestructura; tras `POST /agents/discover`, aparecen `booking-agent` y `notification-agent` con tag `a2a-agent`, y a los ~10s pasan a `passing` (verde).
4. Cadena A2A → MCP → microservicio probada en vivo: `list_classes` delegada al Booking Agent devolvió las 4 clases reales de booking-svc.
5. Encadenamiento secuencial probado: `create_booking` → el `user_id`/`booking_id` del resultado se inyectan en `send_notification`. Verificado independientemente que la reserva existe en booking-svc y la notificación en notif-svc.
6. Logs JSON con eventos `a2a.delegate.send` / `a2a.delegate.result` / `a2a.task_received` / `a2a.task_completed`, con `correlation_id` propagado.
7. Flujo completo del enunciado verificado con Gemini real: `"Reserva yoga para el viernes y avisame por notificacion"` → Gemini emite 2 function calls (`create_booking` con el `class_id` correcto de Yoga Matutino, luego `send_notification`) → ambas delegadas a sus agentes → `./demo_a2a.sh` termina con 0 fallos.

**Decisiones de diseño**:
- **SDK oficial** `a2a-sdk==1.1.2` (protocolo A2A v1.0), no una implementación propia. En v1.0 el `AgentCard` no tiene campo `url` plano: la URL vive en `supported_interfaces` junto al binding de protocolo. El card se sirve en dos rutas para cumplir tanto con el enunciado como con el default del SDK.
- **Los agentes usan MCP de verdad**, como clientes streamable-http contra `fitflow-mcp`, en vez de importar `tools.py` en proceso — que es lo que pide literalmente el enunciado ("internamente usa el MCP Server de FitFlow").
- **Los agentes NO se auto-registran en Consul**: el descubrimiento entre agentes es por Agent Card. El botón del dashboard hace *third-party registration* en Consul después de descubrirlos, para que la diferencia entre ambos mecanismos sea visible en la demo. (La UI de Consul es una SPA compilada dentro de su imagen y no admite botones propios; de ahí el dashboard propio.)
- **Gemini solo decide, no ejecuta**: automatic function calling va desactivado; la ejecución real la hace el dispatch A2A contra el agente remoto. Las credenciales y los ids derivados nunca se le piden a Gemini — los inyecta el Orchestrator.
- El `AgentSkill` de A2A no declara esquema de argumentos, así que el Orchestrator aporta uno por skill para Gemini. El descubrimiento de qué agentes y skills existen sigue siendo 100% dinámico.
- Se añadió la skill `list_classes` (no pedida explícitamente) porque sin ella Gemini no puede mapear "yoga" a un `class_id` real sin inventárselo.

**Robustez del NLU**:
- El system instruction tuvo que ser explicito en que `create_booking` NO notifica por si sola: sin esa aclaracion, Gemini asumia que la reserva ya avisaba al usuario y emitia una sola function call en vez de dos.
- Las llamadas a Gemini se reintentan con backoff (`tenacity`, 4 intentos) ante errores transitorios (`503 UNAVAILABLE` por sobrecarga del modelo, `429`), que aparecen de forma intermitente y si no tumbarian la demo.

**Bugs encontrados y corregidos en el camino**:
- `fitflow-mcp/Dockerfile` ejecutaba `app.server` (stdio) en vez de `app.server_http`: el perfil HTTP nunca había servido HTTP realmente.
- FastMCP devuelve una lista como *un bloque de contenido por elemento*, no como un array JSON: la primera versión del parser devolvía solo la primera clase de cuatro.
- Los data parts de A2A viajan como `protobuf.Value`, que representa todo número como `double` — los ids llegan como `1.0` y hay que coercionarlos a `int` antes de pasarlos a las tools MCP, o los servicios responden 422.

**Requisito de entorno**: `GEMINI_API_KEY` en `.env` (gitignored) para el paso de lenguaje natural. El resto del flujo — Agent Cards, descubrimiento, publicacion en Consul y delegacion A2A — corre sin ella.

## Punto extra — Despliegue cloud [pendiente]

- Railway, Render, o Fly.io (recomendado para simplicidad), o AWS (ECS Fargate + RDS) / Google Cloud (Cloud Run + Cloud SQL).
- Secretos manejados con el servicio de secrets del proveedor, no `.env`.
