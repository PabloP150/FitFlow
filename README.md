# FitFlow — Plataforma de Reservas de Clases Fitness

## Arquitectura

FitFlow es un sistema de microservicios construido con Python + FastAPI, que demuestra patrones de arquitectura moderna: service discovery dinámica con Consul, integración MCP con agentes de IA, y resiliencia distribuida.

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Desktop (MCP Client)               │
│              "¿Qué clases hay disponibles?"                 │
└────────────────┬────────────────────────────────────────────┘
                 │ MCP Protocol (stdio)
                 ↓
          ┌──────────────────┐
          │  fitflow-mcp     │  (puerto 8000 en docker)
          │  MCP Server      │
          │  3 tools:        │
          │ - get_available_classes
          │ - create_booking
          │ - cancel_booking
          └────────┬─────────┘
                   │ HTTP (via Consul discovery)
        ┌──────────┼──────────┐
        ↓          ↓          ↓
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │users-svc│ │booking- │ │notif-   │
   │:8003    │ │svc:8001 │ │svc:8002 │
   └────┬────┘ └────┬────┘ └────┬────┘
        │            │           │
   ┌────▼──┐   ┌─────▼──┐  ┌────▼──┐
   │users_ │   │booking_│  │notif_ │
   │db     │   │db      │  │db     │
   │PG     │   │PG      │  │PG     │
   └───────┘   └────────┘  └───────┘

        ↓↑ Auto-registro & Discovery
   
   ┌────────────────────┐
   │      Consul        │
   │ Service Registry   │
   │   :8500            │
   └────────────────────┘
```

### Servicios

| Servicio | Puerto | Función | Base de datos |
|----------|--------|---------|---------------|
| users-svc | 8003 | Registro, login (JWT), perfil | users_db (PostgreSQL) |
| booking-svc | 8001 | Clases, reservas, cancelaciones | booking_db (PostgreSQL) |
| notif-svc | 8002 | Notificaciones, historial | notif_db (PostgreSQL) |
| fitflow-mcp | stdio (local) | MCP server para Claude Desktop | — |
| consul | 8500 | Service registry, discovery | — |

### Principios

- **Database per Service**: cada microservicio es dueño exclusivo de sus datos. Ninguna consulta cruzada de bases de datos.
- **Descubrimiento dinámico**: los servicios se registran automáticamente en Consul al iniciar y se deregistran al apagarse.
- **MCP integrado**: agents de IA (Claude Desktop) pueden operar FitFlow en lenguaje natural sin conocer detalles de API.
- **Resiliencia**: la llamada booking-svc → notif-svc tiene retries con backoff exponencial + jitter, circuit breaker, y un outbox durable — una reserva nunca falla por culpa de notif-svc.
- **Observabilidad**: logs estructurados en JSON en los 3 servicios, con un `x-correlation-id` propagado de punta a punta.
- **Seguridad**: JWT validado en todos los endpoints que exponen datos de usuario, con verificación de *ownership* (un usuario solo puede ver/cancelar sus propias reservas y notificaciones).

### Estado del proyecto

| Task | Descripción | Estado |
|------|-------------|--------|
| 1 | Microservicios + Docker Compose + Database per Service | ✅ Completado |
| 2A | Service discovery dinámico con Consul | ✅ Completado |
| 2B | MCP Server + integración Claude Desktop | ✅ Completado |
| 3 | Resiliencia (retry/backoff/jitter, circuit breaker, outbox) + Observabilidad (logs JSON, correlation ID) | ✅ Completado |
| 4 | Seguridad (ownership checks, JWT endurecido) + README + demo automatizado | ✅ Completado |
| 5 | Agent-to-Agent (Orchestrator/Booking/Notification Agents, Agent Cards) | ⏳ Pendiente |
| Extra | Despliegue cloud | ⏳ Pendiente |

Ver [`TASKS_ROADMAP.md`](./TASKS_ROADMAP.md) para el detalle de cada task.

---

## Setup local

### Prerrequisitos

- Docker & Docker Compose (v5.0+)
- Python 3.12+ (para correr fitflow-mcp localmente vía Claude Desktop)
- Claude Desktop instalado (opcional, para demostración de Task 2B)

### Instrucciones

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd Proyecto

# 2. Copiar .env.example a .env y ajustar credenciales si es necesario
cp .env.example .env
# (Por defecto .env viene con credenciales de desarrollo seguros para local)

# 3. Construir y levantar los servicios (Tasks 1 & 2A)
docker compose up --build

# Esperado: 7 contenedores corriendo sin errores
# - users-db, booking-db, notif-db (PostgreSQL)
# - consul (Service Registry)
# - users-svc, booking-svc, notif-svc (aplicaciones)

# 4. Verificar que los servicios están listos
curl http://localhost:8003/healthz   # {"status":"ok"}
curl http://localhost:8001/healthz   # {"status":"ok"}
curl http://localhost:8002/healthz   # {"status":"ok"}

# 5. Abrir la UI de Consul en el navegador
# http://localhost:8500
# Deberías ver users-svc, booking-svc, notif-svc en verde (Passing)
```

---

## Flujo de uso (sin MCP, vía curl)

### 1. Registrar un usuario

```bash
curl -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "secret123",
    "full_name": "Alice Wonderland"
  }'

# Respuesta:
# {
#   "id": 1,
#   "email": "alice@example.com",
#   "full_name": "Alice Wonderland",
#   "created_at": "2026-08-23T10:30:00"
# }
```

### 2. Hacer login y obtener JWT

```bash
curl -X POST http://localhost:8003/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "secret123"
  }'

# Respuesta (copiar token):
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer"
# }

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Listar clases disponibles

```bash
curl http://localhost:8001/classes

# Respuesta:
# [
#   {"id": 1, "name": "Yoga Matutino", "description": "...", "start_time": "...", "capacity": 20, "spots_taken": 0},
#   {"id": 2, "name": "Spinning", "description": "...", "start_time": "...", "capacity": 15, "spots_taken": 0},
#   ...
# ]
```

### 4. Crear una reserva (requiere JWT)

```bash
curl -X POST http://localhost:8001/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"class_id": 1}'

# Respuesta:
# {
#   "id": 1,
#   "user_id": 1,
#   "class_id": 1,
#   "status": "confirmed",
#   "created_at": "2026-08-23T10:35:00"
# }
```

### 5. Verificar notificación registrada

Desde Task 4, este endpoint requiere JWT (solo el propio usuario puede ver su historial):

```bash
curl http://localhost:8002/notifications/user/1 \
  -H "Authorization: Bearer $TOKEN"

# Respuesta:
# [
#   {
#     "id": 1,
#     "user_id": 1,
#     "type": "booking_confirmation",
#     "message": "Tu reserva en Yoga Matutino fue confirmada",
#     "booking_id": 1,
#     "created_at": "2026-08-23T10:35:00"
#   }
# ]

# Sin token -> 401. Con el token de OTRO usuario -> 403.
```

### 6. Ver el `x-correlation-id` de la reserva

Toda respuesta trae un header `x-correlation-id` (generado si el caller no mandó uno). El mismo id se propaga a la llamada saliente booking-svc → notif-svc y aparece en los logs JSON de ambos servicios — útil para rastrear una operación de punta a punta:

```bash
curl -i -X POST http://localhost:8001/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"class_id": 1}' | grep -i x-correlation-id

# x-correlation-id: 2382b2a6-633c-499b-b927-5f2a54584394

docker compose logs booking-svc | grep "2382b2a6-633c-499b-b927-5f2a54584394"
```

---

## Flujo de uso (con MCP + Claude Desktop) — Task 2B

### 1. Configurar claude_desktop_config.json

Encuentra tu archivo de configuración:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Agrega el servidor MCP (reemplaza `/path/to` con la ruta real de tu repo):

```json
{
  "mcpServers": {
    "fitflow": {
      "command": "python",
      "args": [
        "/path/to/Proyecto/fitflow-mcp/app/server.py"
      ],
      "env": {
        "CONSUL_HOST": "localhost",
        "CONSUL_PORT": "8500",
        "MCP_RUN_MODE": "local"
      }
    }
  }
}
```

### 2. Reiniciar Claude Desktop

Cierra y vuelve a abrir Claude Desktop. En la ventana de chat, deberías ver un icono de "hammer" (herramientas) — abre el panel para confirmar que las 3 tools de FitFlow aparecen:
- `get_available_classes`
- `create_booking`
- `cancel_booking`

### 3. Usar el sistema en lenguaje natural

**Ejemplo 1: Listar clases**
```
Claude Desktop: "¿Qué clases hay disponibles?"

Claude internamente:
1. Llama a get_available_classes (tool) vía MCP
2. get_available_classes consulta a booking-svc vía Consul discovery
3. booking-svc responde con la lista
4. Claude muestra la lista en forma legible al usuario
```

**Ejemplo 2: Crear una reserva**
```
Claude Desktop: "Quiero reservar Yoga Matutino. Mi email es alice@example.com y contraseña es secret123"

Claude internamente:
1. Llama a create_booking(class_id=1, email="alice@example.com", password="secret123")
2. fitflow-mcp hace login en users-svc, obtiene el JWT
3. fitflow-mcp llama a booking-svc con el JWT, crea la reserva
4. booking-svc notifica a notif-svc automáticamente
5. Claude confirma la reserva al usuario
```

---

## Arquitectura detallada por servicio

### users-svc (8003)

**Endpoints:**
- `POST /users/register` — Registrar usuario nuevo
- `POST /users/login` — Login, devuelve JWT con `user_id`
- `GET /users/{user_id}` — Obtener perfil
- `GET /healthz` — Health check simple
- `GET /readyz` — Health check + verificación de conexión a BD

**Autenticación:**
- Passwords hasheados con `bcrypt` (ver `app/security.py`)
- JWT emitido en login, válido por `JWT_EXPIRE_MINUTES` (default 60 min)
- Algoritmo: HS256, secret en `JWT_SECRET_KEY` (env var)

**Base de datos (users_db):**
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  hashed_password VARCHAR NOT NULL,
  full_name VARCHAR NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

### booking-svc (8001)

**Endpoints:**
- `GET /classes` — Listar clases disponibles con cupo
- `POST /bookings` — Crear reserva (requiere JWT)
- `GET /bookings/{id}` — Obtener detalles de una reserva (requiere JWT, solo el dueño)
- `POST /bookings/{id}/cancel` — Cancelar reserva (soft-cancel, requiere JWT, solo el dueño)
- `GET /healthz`, `GET /readyz`

**Autenticación (Task 4):**
- Valida JWT en todos los endpoints de `bookings` (`GET`, `POST`, `POST .../cancel`)
- Extrae `user_id` del payload del JWT
- Si token inválido/expirado/malformado → 401 Unauthorized (incluye tokens con firma válida pero payload incompleto — `security.py` captura tanto `jwt.InvalidTokenError` como `pydantic.ValidationError`)
- **Ownership**: si `booking.user_id != user_id` del token → 403 Forbidden (un usuario no puede ver ni cancelar la reserva de otro)

**Base de datos (booking_db):**
```sql
CREATE TABLE classes (
  id SERIAL PRIMARY KEY,
  name VARCHAR NOT NULL,
  description VARCHAR,
  start_time TIMESTAMP NOT NULL,
  capacity INTEGER NOT NULL
);

CREATE TABLE bookings (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,  -- sin FK, valor de referencia solo
  class_id INTEGER NOT NULL,  -- FK a classes
  status VARCHAR DEFAULT 'confirmed',  -- confirmed | cancelled
  created_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (class_id) REFERENCES classes(id)
);

-- Task 3: outbox de notificaciones (ver seccion "Resiliencia")
CREATE TABLE pending_notifications (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  type VARCHAR NOT NULL,
  message VARCHAR NOT NULL,
  booking_id INTEGER,
  correlation_id VARCHAR,
  attempts INTEGER DEFAULT 0,
  status VARCHAR DEFAULT 'pending',  -- pending | sent | failed
  created_at TIMESTAMP DEFAULT NOW(),
  last_attempt_at TIMESTAMP
);
```

**Integración con notif-svc:**
- Al crear/cancelar una reserva, booking-svc llama internamente a `POST notif-svc/notifications`
- En Task 1: la URL de notif-svc está **hardcodeada** como `http://notif-svc:8002` (nombre lógico docker-compose)
- En Task 2A: se reemplaza por **Consul discovery** vía `discovery.py`
- Desde Task 3: la llamada es resiliente (ver sección "Resiliencia" más abajo) — una reserva **nunca** falla por culpa de notif-svc, aunque esté caído

**Seed de clases:**
Al iniciar, si no hay clases en la BD, se insertan 4 automáticamente:
- Yoga Matutino — mañana 09:00, capacity 20
- Spinning — mañana 10:00, capacity 15
- CrossFit — mañana 11:00, capacity 18
- Pilates — mañana 14:00, capacity 16

---

### notif-svc (8002)

**Endpoints:**
- `POST /notifications` — Registrar una notificación (llamado internamente por booking-svc, sin auth de usuario final — es tráfico servicio-a-servicio)
- `GET /notifications/user/{user_id}` — Obtener historial de notificaciones de un usuario (requiere JWT, Task 4; ownership: solo el propio usuario puede ver su historial → 403 si el token es de otro usuario)
- `GET /healthz`, `GET /readyz`

**Campos de notificación:**
- `user_id`: a quién va la notificación
- `type`: tipo (ej. "booking_confirmation", "booking_cancelled", "generic")
- `message`: cuerpo del mensaje
- `booking_id` (opcional): si se trata de una notificación relacionada a una reserva

**Base de datos (notif_db):**
```sql
CREATE TABLE notifications (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  type VARCHAR NOT NULL,
  message VARCHAR NOT NULL,
  booking_id INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Por ahora:**
- Las notificaciones se guardan en la BD (no se envía email ni SMS real)
- Pueden consultarse después con la API (con JWT propio)
- En un sistema real podría integrarse con Twilio, SendGrid, etc.

---

### fitflow-mcp (stdio, perfil docker opcional)

**Transporte:**
- **Primario (Task 2B)**: stdio local, para integración con Claude Desktop
  - Se ejecuta como proceso Python normal en la máquina del usuario
  - Claude Desktop se conecta vía stdio
  - Configurable en `claude_desktop_config.json`
  
- **Alternativo (futuro)**: HTTP dentro de docker-compose (perfil `profiles: ["http"]`)
  - Permite que otros clientes MCP remotos se conecten (ej. otros agentes)
  - Se corre como `docker compose --profile http up`
  - Puerto 8000

**Herramientas (tools):**

1. **get_available_classes()** → `GET booking-svc/classes`
   - Llamadas a Booking Agent (Task 5) o directamente a booking-svc vía MCP
   - Devuelve lista de clases con cupo disponible

2. **create_booking(class_id: int, email: str, password: str)** → secuencia:
   - Login en users-svc con email/password → obtiene JWT
   - `POST booking-svc/bookings` con el JWT
   - booking-svc notifica a notif-svc automáticamente
   - Devuelve los detalles de la reserva creada

3. **cancel_booking(booking_id: int, email: str, password: str)** → secuencia:
   - Login en users-svc con email/password → obtiene JWT
   - `POST booking-svc/bookings/{id}/cancel` con el JWT
   - Devuelve la reserva cancelada

**Discovery de servicios en MCP Server:**
- Al iniciar, carga config desde env vars: `CONSUL_HOST`, `CONSUL_PORT`, `MCP_RUN_MODE`
- Si `MCP_RUN_MODE=local`: reescribe hostnames docker a `localhost` (resueltos en el host)
- Si `MCP_RUN_MODE=docker`: usa hostnames directos (para cuando el server corre dentro de docker-compose)
- Consulta a Consul: `consul.health.service("booking-svc", passing=True)` → obtiene URL actual
- Sin caché (volumen bajo)

---

## Consul: cómo funciona el registro y descubrimiento

### Auto-registro (Task 2A)

Cada servicio (users-svc, booking-svc, notif-svc) ejecuta al startup:

```python
def register_service():
    consul = consul_lib.Consul(host="consul", port=8500)
    consul.agent.service.register(
        name="booking-svc",           # nombre único del servicio
        service_id="booking-svc-1",   # id único de esta instancia
        address="booking-svc",        # hostname docker-compose
        port=8001,
        check=consul_lib.Check.http(
            url="http://booking-svc:8001/healthz",  # Consul poll cada 10s
            interval="10s",
            timeout="5s",
            deregister="30s",  # si falla 30s, se deregistra solo
        ),
    )
```

### Descubrimiento (Task 2A, usado en booking-svc → notif-svc)

```python
def get_service_url(service_name: str) -> str:
    consul = consul_lib.Consul(host="consul", port=8500)
    _, services = consul.health.service(service_name, passing=True)
    if not services:
        raise ServiceUnavailable(service_name)
    entry = services[0]["Service"]
    return f"http://{entry['Address']}:{entry['Port']}"

# Uso:
url = get_service_url("notif-svc")  # → "http://notif-svc:8002"
httpx.post(f"{url}/notifications", json=...)
```

### UI de Consul

Abre `http://localhost:8500` en el navegador:
- Panel izquierdo: "Services" → lista todos los servicios registrados
- Cada servicio muestra su estado: "Passing" (verde), "Warning" (amarillo), "Critical" (rojo)
- Detalles de cada instancia: hostname, puerto, checks activos

---

## Resiliencia (Task 3)

La llamada booking-svc → notif-svc combina tres mecanismos complementarios, implementados en `booking-svc/app/resilience.py` y `booking-svc/app/outbox.py`:

### 1. Retry con backoff exponencial + jitter (`tenacity`)

Cada llamada HTTP a notif-svc se reintenta hasta 3 veces si falla por timeout, error de red, o respuesta 5xx, esperando cada vez un poco más (con aleatoriedad/jitter para que varios requests no reintenten todos al mismo instante):

```python
@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4),
    retry=retry_if_exception_type(NotifServiceError),
)
async def call_notif_service(url, payload, headers): ...
```

### 2. Circuit breaker (`circuitbreaker`)

Si las llamadas siguen fallando después de agotar los reintentos, el circuito se **abre**: las siguientes llamadas fallan de inmediato (sin tocar la red) durante `recovery_timeout` (10s), dándole tiempo a notif-svc para recuperarse sin recibir más carga. Pasado ese tiempo, la siguiente llamada actúa como sonda — si tiene éxito, el circuito se cierra de nuevo.

```python
@circuit(failure_threshold=3, recovery_timeout=10, expected_exception=NotifServiceError)
@retry(...)
async def call_notif_service(url, payload, headers): ...
```

Se distinguen dos tipos de error: `NotifServiceError` (red/timeout/5xx — reintentable, cuenta contra el breaker) y `NotifServiceClientError` (4xx — "nuestra culpa", no se reintenta ni cuenta contra el breaker).

Verificado directamente contra el contenedor real (ver `docker compose exec booking-svc python -c "..."` en el historial de desarrollo): 3 fallos consecutivos abren el circuito, las siguientes llamadas retornan `CircuitBreakerError` en <10ms, y una llamada exitosa después del `recovery_timeout` cierra el circuito de nuevo.

### 3. Outbox pattern (`app/outbox.py`)

Si la llamada falla incluso después de reintentos y/o el circuito está abierto, la notificación **no se pierde**: se guarda como fila `pending` en la tabla `pending_notifications` (booking_db). Un worker en background (lanzado desde el `lifespan` de `main.py`, un `asyncio.create_task`) revisa esa tabla cada 10 segundos y reintenta la entrega usando el mismo `call_notif_service` (retry + circuit breaker incluidos), hasta un máximo de 10 intentos por notificación.

Esto garantiza: **una reserva nunca falla por culpa de notif-svc**, y una notificación tampoco se descarta silenciosamente cuando notif-svc está caído — se entrega en cuanto vuelve a estar sano.

```bash
# Simular una caída y observar la recuperación automática
docker compose stop notif-svc
curl -X POST http://localhost:8001/bookings -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id": 1}'
# -> sigue devolviendo 201; la notificación queda en pending_notifications

docker compose start notif-svc
sleep 15   # el outbox worker hace poll cada 10s
curl http://localhost:8002/notifications/user/1 -H "Authorization: Bearer $TOKEN"
# -> la notificación ya aparece, entregada por el worker sin intervención manual
```

`demo.sh` automatiza este flujo completo (ver sección "Demo automatizado").

---

## Observabilidad (Task 3)

### Logs estructurados en JSON

Los 3 servicios (`users-svc`, `booking-svc`, `notif-svc`) configuran `structlog` + el módulo estándar `logging` (`app/logging_config.py`, idéntico en los 3) para que **toda** línea de log del proceso salga como un objeto JSON en stdout — tanto los logs propios como los de librerías (uvicorn, sqlalchemy):

```json
{"method": "POST", "path": "/bookings", "status_code": 201, "duration_ms": 29.15, "event": "http.request", "correlation_id": "2382b2a6-...", "service": "booking-svc", "level": "info", "logger": "http", "timestamp": "2026-09-06T20:34:38.709230Z"}
```

Se usa `structlog.stdlib.ProcessorFormatter` (no `JSONRenderer` aplicado directo en `structlog.configure`) para poder formatear consistentemente tanto los logs de structlog como los que emite uvicorn/sqlalchemy vía el módulo `logging`.

### Correlation ID (`x-correlation-id`)

`app/middleware.py` (idéntico en los 3 servicios) define `CorrelationIdMiddleware`:

- Reusa el `x-correlation-id` del caller si viene en el request, o genera un UUID4 nuevo.
- Lo enlaza a los contextvars de `structlog` (`bind_contextvars`) — así **todo** log emitido durante ese request lo incluye automáticamente, sin pasarlo a mano por cada función.
- Lo guarda en `request.state.correlation_id` para que los routers lo reenvíen en llamadas salientes (p.ej. booking-svc → notif-svc).
- Lo devuelve en el header de la respuesta.
- Emite una línea de log JSON por request (`http.request`: método, path, status, duración).

Esto permite rastrear una misma operación de punta a punta a través de los logs de distintos servicios:

```bash
docker compose logs booking-svc notif-svc | grep "2382b2a6-633c-499b-b927-5f2a54584394"
```

---

## Seguridad (Task 4)

- **JWT endurecido** (`booking-svc/app/security.py`, `notif-svc/app/security.py`): `decode_token` captura tanto `jwt.InvalidTokenError` (firma inválida, token expirado/malformado) como `pydantic.ValidationError` (token válido pero con payload incompleto, p.ej. sin `user_id`). Antes de este fix, un token con payload incompleto producía un `500 Internal Server Error` en vez de un `401` consistente.
- **Ownership checks**:
  - `GET /bookings/{id}` y `POST /bookings/{id}/cancel` en booking-svc: si `booking.user_id` no coincide con el `user_id` del JWT → `403 Forbidden`.
  - `GET /notifications/user/{user_id}` en notif-svc: ahora requiere JWT; si el `user_id` del JWT no coincide con el `{user_id}` de la URL → `403 Forbidden`.
- **Gestión de secretos**: `JWT_SECRET_KEY`, credenciales de base de datos, etc. viven en `.env` (gitignored) y se cargan vía `env_file` en `docker-compose.yml`. `.env.example` documenta las variables requeridas sin exponer secretos reales. Para producción, `JWT_SECRET_KEY` debe rotarse y gestionarse con un secret manager real (AWS Secrets Manager, Vault, etc.), nunca committearse.

---

## Demo automatizado (`demo.sh`)

`demo.sh` corre el flujo end-to-end completo de forma automática y verifica cada paso (health checks, registro/login, listar clases, crear reserva + `x-correlation-id`, historial de notificaciones con JWT, ownership checks con un segundo usuario, y el ciclo completo de resiliencia: detener notif-svc → reintentos/circuit breaker → outbox → reinicio → entrega automática):

```bash
docker compose up -d --build
./demo.sh
```

Imprime `[OK]`/`[FAIL]` por cada verificación y un resumen final. Requiere `curl` y `jq`.

---

## Flujo end-to-end demostrado

### Task 1 (Microservicios + Docker)

Verificación:
```bash
docker compose up --build

# Los 3 servicios responden en sus puertos
curl http://localhost:8003/healthz  # ✓
curl http://localhost:8001/healthz  # ✓
curl http://localhost:8002/healthz  # ✓

# Flujo manual end-to-end:
# 1. Registrar usuario en users-svc
# 2. Login, obtener JWT
# 3. GET /classes desde booking-svc
# 4. POST /bookings con JWT → crea reserva
# 5. GET /notifications/user/{id} en notif-svc → confirma notificación registrada
```

### Task 2A (Consul Service Discovery)

Verificación:
```bash
# UI de Consul muestra los 3 servicios en verde
open http://localhost:8500

# booking-svc ya resuelve notif-svc vía Consul, no hardcoded
# Mismo flujo end-to-end que Task 1, pero la URL de notif-svc viene de Consul
```

### Task 2B (MCP Server + Claude Desktop)

Verificación:
```bash
# Abrir Claude Desktop
# Ver las 3 tools en el panel de herramientas

# Conversaciones de ejemplo:
# "¿Qué clases hay disponibles?"
# → Claude llama get_available_classes → muestra lista

# "Registra alice@example.com con contraseña secret123, luego reserva Yoga Matutino"
# → Claude llama create_booking → crea la reserva, notif-svc se notifica automáticamente

# "Cancela mi última reserva (email alice@example.com, password secret123)"
# → Claude llama cancel_booking → marca como cancelled
```

### Task 3 (Resiliencia + Observabilidad)

Verificación:
```bash
# Logs JSON con correlation_id
docker compose logs booking-svc | grep '"correlation_id"' | tail -3   # ✓ lineas JSON validas

# Resiliencia: reserva se crea igual aunque notif-svc este caido
docker compose stop notif-svc
curl -X POST http://localhost:8001/bookings -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id": 1}'   # ✓ 201, aunque tarde unos segundos (retries)

docker compose start notif-svc
sleep 15
curl http://localhost:8002/notifications/user/1 -H "Authorization: Bearer $TOKEN"  # ✓ la notificacion aparece (outbox)

# O simplemente:
./demo.sh   # corre todo esto automaticamente y verifica cada paso
```

### Task 4 (Seguridad + README + Demo)

Verificación:
```bash
# Ownership: otro usuario no puede ver/cancelar mi reserva
curl -o /dev/null -w "%{http_code}\n" http://localhost:8001/bookings/1 -H "Authorization: Bearer $OTHER_USER_TOKEN"  # ✓ 403

# Ownership: otro usuario no puede ver mi historial de notificaciones
curl -o /dev/null -w "%{http_code}\n" http://localhost:8002/notifications/user/1 -H "Authorization: Bearer $OTHER_USER_TOKEN"  # ✓ 403

# Sin token -> 401 consistente (no 500)
curl -o /dev/null -w "%{http_code}\n" http://localhost:8002/notifications/user/1  # ✓ 401
```

---

## Estructura de carpetas

```
Proyecto/
├── .git/
├── .gitignore
├── .env                      # desarrollo local (no se commitea)
├── .env.example              # template (sí se commitea)
├── README.md                 # este archivo
├── TASKS_ROADMAP.md          # detalle y estado de cada task (1-5 + extra)
├── docker-compose.yml        # orquestación de servicios
├── demo.sh                   # demo end-to-end automatizada (Task 4)
│
├── users-svc/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py            # FastAPI app + lifespan (register Consul, logging)
│       ├── config.py          # pydantic-settings
│       ├── database.py        # engine, SessionLocal
│       ├── models.py          # SQLAlchemy models
│       ├── schemas.py         # Pydantic schemas
│       ├── security.py        # bcrypt + JWT
│       ├── consul_client.py   # registro en Consul
│       ├── logging_config.py  # logs JSON (Task 3)
│       ├── middleware.py      # CorrelationIdMiddleware (Task 3)
│       └── routers/
│           ├── users.py       # POST/GET endpoints
│           └── health.py      # /healthz, /readyz
│
├── booking-svc/              # estructura similar + resiliencia (Task 3)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # + outbox worker en el lifespan
│       ├── config.py
│       ├── database.py
│       ├── models.py          # + PendingNotification (outbox)
│       ├── schemas.py
│       ├── security.py        # JWT validation (+ catch ValidationError, Task 4)
│       ├── consul_client.py
│       ├── discovery.py       # resolución Consul
│       ├── notif_client.py    # llamadas a notif-svc, resiliente
│       ├── resilience.py      # retry (tenacity) + circuit breaker (Task 3)
│       ├── outbox.py          # worker en background del outbox (Task 3)
│       ├── logging_config.py  # logs JSON (Task 3)
│       ├── middleware.py      # CorrelationIdMiddleware (Task 3)
│       ├── seed.py            # data seed de clases
│       └── routers/
│           ├── classes.py
│           ├── bookings.py    # + ownership checks (Task 4)
│           └── health.py
│
├── notif-svc/                # estructura similar
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py          # + JWT_* (Task 4)
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── security.py        # JWT validation (Task 4)
│       ├── consul_client.py
│       ├── logging_config.py  # logs JSON (Task 3)
│       ├── middleware.py      # CorrelationIdMiddleware (Task 3)
│       └── routers/
│           ├── notifications.py  # GET protegido con JWT + ownership (Task 4)
│           └── health.py
│
└── fitflow-mcp/
    ├── Dockerfile            # solo para perfil http
    ├── requirements.txt
    └── app/
        ├── server.py         # FastMCP + tools, transporte stdio
        ├── server_http.py    # alternativo: transporte HTTP (futuro)
        ├── config.py
        ├── discovery.py      # resolución Consul (similar a booking-svc)
        └── tools.py          # get_available_classes, create_booking, cancel_booking
```

---

## Variables de entorno (`.env.example`)

Todas las env vars se cargan automáticamente al iniciar los servicios vía `docker-compose.yml`.

**Bases de datos:**
- `USERS_DB_USER`, `USERS_DB_PASSWORD`, `USERS_DB_NAME`, `USERS_DB_PORT`
- `BOOKING_DB_USER`, `BOOKING_DB_PASSWORD`, `BOOKING_DB_NAME`, `BOOKING_DB_PORT`
- `NOTIF_DB_USER`, `NOTIF_DB_PASSWORD`, `NOTIF_DB_NAME`, `NOTIF_DB_PORT`

**JWT:**
- `JWT_SECRET_KEY` — clave secreta para firmar JWTs (⚠️ cambiar en producción)
- `JWT_ALGORITHM` — algoritmo de firma (default HS256)
- `JWT_EXPIRE_MINUTES` — tiempo de vida del token (default 60 min)

**Consul:**
- `CONSUL_HOST` — hostname del servicio Consul (default: "consul" en docker-compose)
- `CONSUL_PORT` — puerto de Consul API (default: 8500)

**MCP:**
- `MCP_RUN_MODE` — "local" (host) o "docker" (dentro de docker-compose)

---

## Siguientes pasos (Task 5 + extra, futuro)

Tasks 1, 2A, 2B, 3 y 4 están completadas (ver tabla de estado al inicio del README y [`TASKS_ROADMAP.md`](./TASKS_ROADMAP.md)). Lo que queda:

### Task 5 — Agent-to-Agent (A2A)
- Introducir Orchestrator Agent, Booking Agent, Notification Agent
- Cada agente publica un Agent Card en `/.well-known/agent.json`
- Agentes se descubren entre sí vía Agent Cards (análogo a Consul, pero para agentes)
- Demostración: Claude Desktop → Orchestrator Agent → Booking/Notification Agents → servicios reales

### Punto extra — Despliegue cloud (+15 pts)
- Railway, Render, o Fly.io (recomendado para simplicidad)
- AWS (ECS Fargate + RDS) o Google Cloud (Cloud Run + Cloud SQL)
- Secretos manejados con el servicio de secrets del proveedor, no `.env`

---

## Troubleshooting

### Los servicios no se conectan a la BD

```bash
# Verificar que Postgres está corriendo y listo
docker compose logs booking-db | tail

# Buscar mensajes de healthcheck
docker compose ps

# Si un servicio tiene status "unhealthy", revisar los logs de ese servicio
docker compose logs booking-svc
```

### Consul muestra un servicio en "Critical" (rojo)

```bash
# Verificar el healthcheck
docker compose logs booking-svc

# Si el mensaje es "connection refused" en http://booking-svc:8001/healthz,
# es probable que el servicio tardó más de 5s en responder.
# El container puede haber iniciado pero la app aún no está lista.
# Dar más tiempo y revisar que el lifespan se ejecutó correctamente.
```

### MCP Server no se conecta a Consul desde Claude Desktop

```bash
# Verificar que Consul está corriendo
curl http://localhost:8500/v1/status/leader

# Verificar que CONSUL_HOST=localhost y CONSUL_PORT=8500 en claude_desktop_config.json
# (No usar "consul" como hostname — eso solo funciona dentro de docker-compose)

# Revisar logs del proceso MCP
# (Python stderr debería imprimirse en la consola de Claude Desktop)
```

### JWT inválido / 401 Unauthorized en booking-svc

```bash
# Verificar que JWT_SECRET_KEY en .env es la misma en users-svc y booking-svc
# (en docker-compose ambos leen del mismo .env, debe ser coherente)

# Verificar que el token no está expirado
# (default 60 min vía JWT_EXPIRE_MINUTES)

# Revisar logs del servicio
docker compose logs booking-svc | grep "401\|unauthorized"
```

---

## Contacto y contribuciones

Este es un proyecto de Postgrado en Diseño y Desarrollo de Software, Universidad Galileo. Para consultas sobre el enunciado o sugerencias, contactar al instructor.

---

**Última actualización**: Septiembre 2026
**Status**: Tasks 1, 2A, 2B, 3 y 4 completadas y verificadas end-to-end (🚀 Ready for demo)
**Roadmap**: Task 5 (Agent-to-Agent) y despliegue cloud pendientes — ver [`TASKS_ROADMAP.md`](./TASKS_ROADMAP.md)
