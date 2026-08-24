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

```bash
curl http://localhost:8002/notifications/user/1

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
- `GET /bookings/{id}` — Obtener detalles de una reserva
- `POST /bookings/{id}/cancel` — Cancelar reserva (soft-cancel, requiere JWT)
- `GET /healthz`, `GET /readyz`

**Autenticación:**
- Valida JWT en endpoints protegidos (`POST /bookings`, `POST /bookings/{id}/cancel`)
- Extrae `user_id` del payload del JWT
- Si token inválido/expirado → 401 Unauthorized

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
```

**Integración con notif-svc:**
- Al crear una reserva exitosa, booking-svc llama internamente a `POST notif-svc/notifications`
- En Task 1: la URL de notif-svc está **hardcodeada** como `http://notif-svc:8002` (nombre lógico docker-compose)
- En Task 2A: se reemplaza por **Consul discovery** vía `discovery.py`
- Si notif-svc no responde: se loguea el error pero la reserva se crea igualmente (resiliencia robusta es Task 3)

**Seed de clases:**
Al iniciar, si no hay clases en la BD, se insertan 4 automáticamente:
- Yoga Matutino — mañana 09:00, capacity 20
- Spinning — mañana 10:00, capacity 15
- CrossFit — mañana 11:00, capacity 18
- Pilates — mañana 14:00, capacity 16

---

### notif-svc (8002)

**Endpoints:**
- `POST /notifications` — Registrar una notificación
- `GET /notifications/user/{user_id}` — Obtener historial de notificaciones de un usuario
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
- Pueden consultarse después con la API
- En Task 3 se añadirá resiliencia; en un sistema real podría integrarse con Twilio, SendGrid, etc.

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

---

## Estructura de carpetas

```
Proyecto/
├── .git/
├── .gitignore
├── .env                      # desarrollo local (no se commitea)
├── .env.example              # template (sí se commitea)
├── README.md                 # este archivo
├── docker-compose.yml        # orquestación de servicios
│
├── users-svc/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py           # FastAPI app + lifespan (register Consul)
│       ├── config.py          # pydantic-settings
│       ├── database.py        # engine, SessionLocal
│       ├── models.py          # SQLAlchemy models
│       ├── schemas.py         # Pydantic schemas
│       ├── security.py        # bcrypt + JWT
│       ├── consul_client.py   # registro en Consul
│       └── routers/
│           ├── users.py       # POST/GET endpoints
│           └── health.py      # /healthz, /readyz
│
├── booking-svc/              # estructura similar
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── security.py        # JWT validation
│       ├── consul_client.py
│       ├── discovery.py       # resolución Consul
│       ├── notif_client.py    # llamadas a notif-svc
│       ├── seed.py            # data seed de clases
│       └── routers/
│           ├── classes.py
│           ├── bookings.py
│           └── health.py
│
├── notif-svc/                # estructura similar
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── consul_client.py
│       └── routers/
│           ├── notifications.py
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

## Siguientes pasos (Tasks 3-5, futuro)

### Task 3 — Resiliencia + Observabilidad
- Implementar timeout/retry/backoff/jitter (librería `tenacity`) en la llamada booking-svc→notif-svc
- Implementar circuit breaker con `pybreaker`
- Adoptar logs estructurados (JSON) con `structlog`
- Propagar `x-correlation-id` entre servicios para rastrabilidad

### Task 4 — Seguridad + README + Demo
- Endurecimiento de validación JWT (401 consistente, chequeo de ownership)
- Documentación completa de secretos y rotación de credenciales
- Video de demostración (5-8 min) mostrando Tasks 1-3

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

**Última actualización**: Agosto 2026  
**Status**: Task 1 & 2 funcionales (🚀 Ready for demo)  
**Roadmap**: Tasks 3, 4, 5 en construcción...
