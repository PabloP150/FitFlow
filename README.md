# FitFlow — Plataforma de Reservas de Clases Fitness

## Arquitectura

FitFlow es un sistema de microservicios construido con Python + FastAPI, que demuestra patrones de arquitectura moderna: service discovery dinámica con Consul, integración MCP con agentes de IA, y resiliencia distribuida.

```
┌──────────────────────────┐   ┌──────────────────────────────────┐
│  Claude Desktop          │   │  Usuario / dashboard :9000       │
│  "¿Qué clases hay?"      │   │  "Reserva yoga y avísame"        │
└────────────┬─────────────┘   └────────────┬─────────────────────┘
             │ MCP (stdio)                  │ HTTP
             │                              ↓
             │                   ┌──────────────────────┐
             │                   │ orchestrator-agent   │ ── Gemini (decide
             │                   │ :9000                │     qué skills usar)
             │                   └───────┬──────────────┘
             │                           │ A2A (descubre por Agent Card,
             │                           │      delega en secuencia)
             │              ┌────────────┴────────────┐
             │              ↓                         ↓
             │   ┌────────────────────┐  ┌──────────────────────┐
             │   │ booking-agent      │  │ notification-agent   │
             │   │ :9001              │  │ :9002                │
             │   └─────────┬──────────┘  └──────────┬───────────┘
             │             │ MCP (streamable-http)  │
             ↓             └───────────┬────────────┘
      ┌──────────────────────────────────────┐
      │           fitflow-mcp :8000          │  5 tools
      └────────────────────┬─────────────────┘
                           │ HTTP (vía Consul discovery)
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
   ┌─────────┐       ┌──────────┐       ┌──────────┐
   │users-svc│       │booking-  │       │notif-    │
   │:8003    │       │svc:8001  │       │svc:8002  │
   └────┬────┘       └────┬─────┘       └────┬─────┘
        │                 │                  │
   ┌────▼───┐        ┌────▼────┐        ┌────▼───┐
   │users_db│        │booking_ │        │notif_db│
   │  PG    │        │db  PG   │        │  PG    │
   └────────┘        └─────────┘        └────────┘

        ↓↑ Auto-registro & Discovery
   ┌────────────────────┐
   │      Consul        │   Los microservicios se auto-registran.
   │ Service Registry   │   Los agentes NO: se descubren entre sí
   │   :8500            │   por Agent Card (ver Task 5).
   └────────────────────┘
```

### Servicios

| Servicio | Puerto | Función | Base de datos |
|----------|--------|---------|---------------|
| users-svc | 8003 | Registro, login (JWT), perfil | users_db (PostgreSQL) |
| booking-svc | 8001 | Clases, reservas, cancelaciones | booking_db (PostgreSQL) |
| notif-svc | 8002 | Notificaciones, historial | notif_db (PostgreSQL) |
| fitflow-mcp | 8000 (+ stdio local) | MCP server (Claude Desktop vía stdio; agentes vía HTTP) | — |
| consul | 8500 | Service registry, discovery | — |
| orchestrator-agent | 9000 | Agente orquestador A2A + dashboard (Task 5) | — |
| booking-agent | 9001 | Agente especialista en reservas (Task 5) | — |
| notification-agent | 9002 | Agente especialista en notificaciones (Task 5) | — |

### Principios

- **Database per Service**: cada microservicio es dueño exclusivo de sus datos. Ninguna consulta cruzada de bases de datos.
- **Descubrimiento dinámico**: los servicios se registran automáticamente en Consul al iniciar y se deregistran al apagarse.
- **MCP integrado**: agents de IA (Claude Desktop) pueden operar FitFlow en lenguaje natural sin conocer detalles de API.
- **Resiliencia**: la llamada booking-svc → notif-svc tiene retries con backoff exponencial + jitter, circuit breaker, y un outbox durable — una reserva nunca falla por culpa de notif-svc.
- **Observabilidad**: logs estructurados en JSON en los 3 servicios, con un `x-correlation-id` propagado de punta a punta.
- **Seguridad**: JWT validado en todos los endpoints que exponen datos de usuario, con verificación de *ownership* (un usuario solo puede ver/cancelar sus propias reservas y notificaciones).
- **Agent-to-Agent**: tres agentes especializados se descubren por Agent Card y se delegan skills entre sí; cada uno ejecuta las acciones reales vía MCP. MCP es "un agente usa herramientas"; A2A es "un agente delega a otro agente".
- **Infraestructura como código**: el despliegue en AWS es un `terraform apply`, con los secretos en Parameter Store y nada sensible en el repo.

### Estado del proyecto

| Task | Descripción | Estado |
|------|-------------|--------|
| 1 | Microservicios + Docker Compose + Database per Service | ✅ Completado |
| 2A | Service discovery dinámico con Consul | ✅ Completado |
| 2B | MCP Server + integración Claude Desktop | ✅ Completado |
| 3 | Resiliencia (retry/backoff/jitter, circuit breaker, outbox) + Observabilidad (logs JSON, correlation ID) | ✅ Completado |
| 4 | Seguridad (ownership checks, JWT endurecido) + README + demo automatizado | ✅ Completado |
| 5 | Agent-to-Agent (Orchestrator/Booking/Notification Agents, Agent Cards) | ✅ Completado |
| Extra | Despliegue cloud en AWS (EC2 + Terraform + Parameter Store) | ✅ Implementado |

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

### fitflow-mcp (stdio + HTTP)

**Transporte:**
- **stdio (Task 2B)**: para integración con Claude Desktop
  - Se ejecuta como proceso Python normal en la máquina del usuario
  - Claude Desktop se conecta vía stdio
  - Configurable en `claude_desktop_config.json`

- **streamable-http (Task 2B/5)**: dentro de docker-compose, puerto 8000, endpoint `/mcp`
  - Desde Task 5 arranca por defecto (antes estaba tras `profiles: ["http"]`)
  - Es el transporte que usan `booking-agent` y `notification-agent` como
    clientes MCP para ejecutar acciones reales

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

4. **send_notification(user_id, type, message, booking_id=None)** (Task 5) → `POST notif-svc/notifications`
   - Tráfico servicio-a-servicio, sin JWT
   - La usa `notification-agent`

5. **get_notification_history(user_id, email, password)** (Task 5) → secuencia:
   - Login en users-svc → obtiene JWT
   - `GET notif-svc/notifications/user/{user_id}` con el JWT (ownership-checked)

**Discovery de servicios en MCP Server:**
- Al iniciar, carga config desde env vars: `CONSUL_HOST`, `CONSUL_PORT`, `MCP_RUN_MODE`
- Si `MCP_RUN_MODE=local`: reescribe hostnames docker a `localhost` (resueltos en el host)
- Si `MCP_RUN_MODE=docker`: usa hostnames directos (para cuando el server corre dentro de docker-compose)
- Consulta a Consul: `consul.health.service("booking-svc", passing=True)` → obtiene URL actual
- Sin caché (volumen bajo)

---

## Agent-to-Agent (Task 5)

### MCP vs A2A — la diferencia

Son protocolos complementarios que resuelven preguntas distintas:

| | **MCP** (Task 2B) | **A2A** (Task 5) |
|---|---|---|
| Pregunta que responde | ¿Cómo un agente usa un **sistema externo**? | ¿Cómo un agente **delega trabajo a otro agente**? |
| Dirección | Vertical: agente → herramientas | Horizontal: agente → agente |
| Descubrimiento | El server declara sus `tools` | Cada agente publica un **Agent Card** |
| En FitFlow | `fitflow-mcp` expone 5 tools | 3 agentes que se delegan skills entre sí |

La analogía con el resto del sistema es directa: **Consul es a los microservicios lo que el Agent Card es a los agentes** — un mecanismo de descubrimiento, pero de capacidades en vez de endpoints.

### Arquitectura

```
Usuario: "Reserva yoga para el viernes y avísame por notificación"
   │ HTTP (dashboard o POST /instruct)
   ↓
┌──────────────────────────────────────┐
│  orchestrator-agent :9000            │
│  - Descubre agentes vía Agent Card   │
│  - Gemini decide qué skills invocar  │
│  - Delega en secuencia por A2A       │
└───────┬──────────────────────┬───────┘
        │ A2A (JSON-RPC)       │ A2A (JSON-RPC)
        ↓                      ↓
┌──────────────────┐   ┌────────────────────────┐
│ booking-agent    │   │ notification-agent     │
│ :9001            │   │ :9002                  │
│ list_classes     │   │ send_notification      │
│ create_booking   │   │ get_history            │
│ cancel_booking   │   │                        │
└────────┬─────────┘   └───────────┬────────────┘
         │ MCP (streamable-http)   │ MCP
         └───────────┬─────────────┘
                     ↓
            ┌──────────────────┐
            │  fitflow-mcp     │  :8000/mcp
            └────────┬─────────┘
                     │ HTTP (vía Consul discovery)
         ┌───────────┼───────────┐
         ↓           ↓           ↓
    booking-svc  users-svc  notif-svc
```

Cada agente **usa MCP internamente** para ejecutar las acciones reales: no habla HTTP directo con los microservicios, sino que invoca tools del MCP Server, que a su vez resuelve los servicios vía Consul.

### Los 3 agentes

| Agente | Puerto | Skills | Agent Card |
|--------|--------|--------|------------|
| orchestrator-agent | 9000 | (cliente A2A, no publica card) | — |
| booking-agent | 9001 | `list_classes`, `create_booking`, `cancel_booking` | `http://localhost:9001/.well-known/agent.json` |
| notification-agent | 9002 | `send_notification`, `get_history` | `http://localhost:9002/.well-known/agent.json` |

### Agent Card (ejemplo real)

```bash
curl http://localhost:9001/.well-known/agent.json
```

```json
{
  "name": "FitFlow Booking Agent",
  "description": "Gestiona reservas de clases fitness en FitFlow",
  "supportedInterfaces": [
    { "url": "http://booking-agent:9001", "protocolBinding": "JSONRPC", "protocolVersion": "1.0" }
  ],
  "version": "1.0.0",
  "capabilities": { "streaming": true },
  "skills": [
    { "id": "list_classes", "name": "Listar clases", "description": "Devuelve las clases disponibles..." },
    { "id": "create_booking", "name": "Crear reserva", "description": "Reserva una clase de fitness..." },
    { "id": "cancel_booking", "name": "Cancelar reserva", "description": "Cancela una reserva existente..." }
  ]
}
```

Se usa el SDK oficial de Google (`a2a-sdk`, protocolo A2A v1.0). En v1.0 la URL del agente vive dentro de `supportedInterfaces` (junto con su binding de protocolo) en vez de ser un campo `url` plano. El card se sirve en **dos rutas equivalentes**: `/.well-known/agent.json` (la que especifica el enunciado) y `/.well-known/agent-card.json` (la ruta por defecto del SDK en v1.0).

### Cómo se descubren y delegan

1. El Orchestrator lee el Agent Card de cada agente (`A2ACardResolver`) y arma un índice `skill_id → agente`.
2. Pide la lista de clases al Booking Agent (`list_classes`) para poder aterrizar nombres ("yoga") en ids reales.
3. Le pasa a **Gemini** las skills descubiertas como *function declarations* y la instrucción del usuario. La ejecución automática de funciones va desactivada: Gemini solo **decide** qué skills invocar y en qué orden.
4. El Orchestrator delega cada decisión al agente correspondiente por A2A, enviando un sobre JSON `{"skill": ..., "args": {...}}`.
5. Los resultados se encadenan: el `user_id` y el `booking_id` que devuelve `create_booking` se inyectan automáticamente en el `send_notification` siguiente.

Las credenciales (`email`/`password`) nunca se le piden a Gemini: las inyecta el Orchestrator a partir del request.

### Consul vs Agent Cards — la demo del botón

Los 3 agentes **no se registran en Consul al arrancar**, a propósito: su descubrimiento es vía Agent Card, que es un mecanismo distinto. Para hacer esa diferencia visible, el dashboard del Orchestrator (`http://localhost:9000`) tiene un botón **"Descubrir agentes vía Agent Card"** que los descubre y *entonces* los publica en Consul.

```bash
# 1. Antes: los agentes NO estan en Consul
curl -s http://localhost:8500/v1/catalog/services | jq 'keys'
# ["booking-svc", "consul", "notif-svc", "users-svc"]

# 2. El boton (o su endpoint equivalente)
curl -X POST http://localhost:9000/agents/discover | jq '.discovered[].name'
# "FitFlow Booking Agent"
# "FitFlow Notification Agent"

# 3. Despues: aparecen en Consul, en verde
curl -s http://localhost:8500/v1/catalog/services | jq 'keys'
# ["booking-agent", "booking-svc", "consul", "notif-svc", "notification-agent", "users-svc"]
```

`POST /agents/reset` (botón "Reiniciar demo") los da de baja, para poder repetir la demostración.

> La UI de Consul no se puede extender con botones propios — es una SPA compilada dentro de la imagen `hashicorp/consul:1.17` — por eso el botón vive en el dashboard del Orchestrator y Consul se actualiza como consecuencia.

### Uso

```bash
# Dashboard (botón de descubrimiento + formulario de instrucción)
open http://localhost:9000

# O por API:
curl -X POST http://localhost:9000/instruct \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Reserva yoga para el viernes y avísame por notificación",
    "email": "alice@example.com",
    "password": "secret123"
  }' | jq
```

```jsonc
{
  "instruction": "Reserva yoga para el viernes y avísame por notificación",
  "correlation_id": "…",
  "steps": [
    { "skill": "create_booking",    "agent": "FitFlow Booking Agent",      "ok": true, "result": { "id": 1, "status": "confirmed", … } },
    { "skill": "send_notification", "agent": "FitFlow Notification Agent", "ok": true, "result": { "id": 2, … } }
  ],
  "summary": "2/2 skills ejecutadas correctamente."
}
```

Ver los logs de comunicación A2A entre agentes:

```bash
docker compose logs -f orchestrator-agent booking-agent notification-agent | grep '"event": "a2a\.'
```

### Requisitos

- `GEMINI_API_KEY` en `.env` (obtener en https://aistudio.google.com/apikey). Sin ella, el descubrimiento y la delegación funcionan igual, pero `/instruct` devuelve un error explicando que falta la key.
- `demo_a2a.sh` automatiza toda la verificación de esta sección.

La API de Gemini devuelve `503 UNAVAILABLE` ("high demand") de forma intermitente; las llamadas se reintentan automáticamente con backoff (`tenacity`, 4 intentos) para que eso no tumbe la demo.

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

### `demo_a2a.sh` (Task 5)

`demo_a2a.sh` es el equivalente para la red de agentes: health checks de los 3 agentes, Agent Cards publicados, el contraste Consul antes/después del botón de descubrimiento, una instrucción en lenguaje natural delegada vía A2A, verificación independiente de que la reserva y la notificación existen de verdad, y los logs de comunicación A2A.

```bash
docker compose up -d --build
./demo_a2a.sh
```

El paso de lenguaje natural requiere una `GEMINI_API_KEY` real en `.env`; el resto de pasos corre sin ella.

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
├── demo_a2a.sh               # demo de la red de agentes A2A (Task 5)
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
├── fitflow-mcp/
│   ├── Dockerfile            # corre server_http.py (transporte streamable-http)
│   ├── requirements.txt
│   └── app/
│       ├── server.py         # FastMCP + tools, transporte stdio (Claude Desktop)
│       ├── server_http.py    # FastMCP + tools, transporte HTTP (agentes Task 5)
│       ├── config.py
│       ├── discovery.py      # resolución Consul (similar a booking-svc)
│       └── tools.py          # 5 tools: classes, booking, cancel, notify, history
│
│   # --- Agentes A2A (Task 5) ---
│
├── booking-agent/            # servidor A2A, skills de reservas
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI + rutas A2A + Agent Card en 2 paths
│       ├── config.py
│       ├── agent_card.py     # AgentCard + AgentSkill
│       ├── executor.py       # AgentExecutor: skill -> tool MCP
│       ├── mcp_client.py     # cliente MCP streamable-http (con retry)
│       ├── logging_config.py
│       └── middleware.py
│
├── notification-agent/       # idéntico, skills de notificaciones
│   └── ...
│
└── orchestrator-agent/       # cliente A2A + NLU Gemini + dashboard
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py           # /instruct, /agents/discover, /agents/reset, dashboard
        ├── config.py
        ├── agent_registry.py # descubrimiento vía Agent Card
        ├── nlu_gemini.py     # skills -> function declarations -> decisión
        ├── a2a_dispatch.py   # delegación A2A + logs de comunicación
        ├── consul_publish.py # publica/da de baja agentes en Consul (el botón)
        ├── static/index.html # dashboard
        ├── logging_config.py
        └── middleware.py
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
- `MCP_SERVER_URL` — endpoint MCP que consumen los agentes (default `http://fitflow-mcp:8000/mcp`)

**Gemini y agentes A2A (Task 5):**
- `GEMINI_API_KEY` — API key de Gemini para el NLU del Orchestrator (obtener en https://aistudio.google.com/apikey)
- `GEMINI_MODEL` — modelo a usar (default `gemini-2.5-flash`)
- `BOOKING_AGENT_URL`, `NOTIFICATION_AGENT_URL` — URLs donde el Orchestrator busca los Agent Cards

---

## Despliegue en AWS (punto extra)

Todo el sistema corre en la nube sobre una instancia EC2, provisionada con Terraform, con los secretos en **AWS Systems Manager Parameter Store** en vez de un `.env` versionado.

### Despliegue actual

| Componente | URL pública |
|---|---|
| Dashboard A2A | http://3.209.94.238:9000 |
| Consul UI | http://3.209.94.238:8500/ui |
| users-svc | http://3.209.94.238:8003 |
| booking-svc | http://3.209.94.238:8001 |
| notif-svc | http://3.209.94.238:8002 |
| MCP Server | http://3.209.94.238:8000/mcp |
| Booking Agent Card | http://3.209.94.238:9001/.well-known/agent.json |
| Notification Agent Card | http://3.209.94.238:9002/.well-known/agent.json |

Verificado en la nube con `HOST=3.209.94.238 ./demo_a2a.sh` — 14/14 checks, incluyendo el flujo completo *"Reserva yoga para el viernes y avísame por notificación"* delegado a los dos agentes. Las bases de datos **no** son accesibles desde internet (puertos 5433-5435 cerrados).

> Esta IP existe mientras la infraestructura esté levantada. Tras `terraform destroy` deja de responder; un nuevo `apply` genera otra IP (`terraform output urls`).

### Por qué EC2 + Docker Compose y no ECS Fargate

El enunciado permite ambas ("*Los servicios como contenedores en ECS Fargate **o en una instancia EC2 con Docker Compose***"). Se eligió EC2 porque:

- Son **11 contenedores**, 3 de ellos PostgreSQL. En RDS serían 3 instancias gestionadas — muy por encima de la capa gratuita (la free tier cubre *una* instancia RDS).
- El `docker-compose.yml` local funciona **tal cual**: mismo networking interno, mismo Consul, mismos Agent Cards. En Fargate habría que rehacer el service discovery (Cloud Map) y montar EFS para las bases.
- Entra en la capa gratuita: `t3.micro` (750 h/mes) + EBS gp3 20 GB (free tier: 30 GB) + Parameter Store estándar (gratis) + Elastic IP (gratis mientras esté asociada a una instancia encendida). **Costo objetivo: ~$0.**

### Arquitectura desplegada

```
Internet
   │
   ▼  (Security Group: 8000-8003, 8500, 9000-9002)
┌──────────────────────────────────────────────┐
│  EC2 t3.micro — Amazon Linux 2023            │
│  Elastic IP estable                          │
│                                              │
│  docker compose -f docker-compose.yml \      │
│                 -f docker-compose.cloud.yml  │
│                                              │
│  11 contenedores (idénticos a local)         │
│  + 2 GB de swap                              │
└───────────────────┬──────────────────────────┘
                    │ rol IAM (sin credenciales en disco)
                    ▼
        SSM Parameter Store (SecureString)
        /fitflow/JWT_SECRET_KEY
        /fitflow/USERS_DB_PASSWORD
        /fitflow/BOOKING_DB_PASSWORD
        /fitflow/NOTIF_DB_PASSWORD
        /fitflow/GEMINI_API_KEY
```

### Desplegar paso a paso

**Prerrequisitos**: Terraform ≥ 1.5, AWS CLI configurado (`aws sts get-caller-identity` debe responder).

```bash
cd infra/aws

# 1. Inicializar
terraform init

# 2. Revisar qué se va a crear (26 recursos, todos destruibles)
terraform plan

# 3. Desplegar
terraform apply
```

Terraform crea: una VPC propia con subnet pública e Internet Gateway (la cuenta puede no tener VPC por defecto), el security group, un rol IAM que **solo** puede leer `/fitflow/*` de Parameter Store, los secretos (contraseñas generadas aleatoriamente — nadie las escribe ni viajan por el repo), la instancia y la Elastic IP.

```bash
# 4. Setear la API key de Gemini fuera del state de Terraform
aws ssm put-parameter --name /fitflow/GEMINI_API_KEY \
  --value 'TU_KEY' --type SecureString --overwrite --region us-east-1

# 5. Conectarse a la instancia (sin SSH: Session Manager, puerto 22 cerrado)
aws ssm start-session --target $(terraform output -raw instance_id)

# Dentro de la instancia: seguir el bootstrap (~4-6 min) y aplicar la key
sudo tail -f /var/log/fitflow-bootstrap.log
sudo systemctl restart fitflow
```

```bash
# 6. Verificar desde tu máquina
IP=$(terraform output -raw public_ip)
curl http://$IP:8003/healthz
curl http://$IP:9001/.well-known/agent.json | jq '.skills[].id'
open http://$IP:9000        # dashboard A2A
open http://$IP:8500/ui     # Consul
```

`terraform output urls` imprime la lista completa de URLs públicas.

```bash
# 7. Verificar el sistema completo contra el despliegue (mismo script que en local)
cd .. && HOST=$IP ./demo_a2a.sh
```

**Nota sobre memoria**: medido en la instancia con los 11 contenedores corriendo, el uso es ~574 MB de los 916 MB de RAM **más ~367 MB de swap**. Sin el swap que configura `user_data.sh` el kernel mataría procesos por OOM. Si se quiere margen, `instance_type = "t3.small"` (2 GB, ya fuera de la capa gratuita).

### Gestión de secretos (sin `.env` en el repo)

- Las contraseñas de BD y el `JWT_SECRET_KEY` los **genera Terraform** (`random_password`) y los guarda como `SecureString` en Parameter Store. Nunca existen en texto plano en el repo.
- La instancia los lee **en cada arranque** con su rol IAM ([`infra/aws/refresh-env.sh`](./infra/aws/refresh-env.sh)) y escribe un `.env` con permisos `600`. No hay credenciales de AWS guardadas en disco.
- El rol IAM está acotado: solo `ssm:GetParameter*` sobre `/fitflow/*` y `kms:Decrypt` restringido a `kms:ViaService = ssm`.
- **Rotar un secreto** sin downtime del resto del sistema:

  ```bash
  aws ssm put-parameter --name /fitflow/JWT_SECRET_KEY \
    --value "$(openssl rand -hex 32)" --type SecureString --overwrite
  aws ssm start-session --target $(terraform output -raw instance_id)
  sudo systemctl restart fitflow    # relee SSM y recrea el .env
  ```

  (Rotar el JWT invalida los tokens ya emitidos; los usuarios vuelven a hacer login. Para rotar una contraseña de BD hay que cambiarla también en PostgreSQL con `ALTER USER`.)

> Se usa Parameter Store y no Secrets Manager porque los parámetros estándar son **gratuitos** y Secrets Manager cobra ~$0.40 por secreto/mes. Ambos son el servicio de secretos gestionado de AWS; migrar sería directo si hiciera falta rotación automática.

### Local vs cloud

El mismo repo corre en los dos entornos; solo cambia de dónde salen los secretos y un override de compose:

| | Local | AWS |
|---|---|---|
| Arranque | `docker compose up -d --build` | `docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d` |
| Secretos | `.env` (gitignored, desde `.env.example`) | Parameter Store → `.env` generado en cada boot |
| Puertos de BD | 5433-5435 publicados (para `psql` desde el host) | **no** publicados (no exponer PostgreSQL a internet) |
| Reinicios | manual | `restart: unless-stopped` + servicio systemd |
| PostgreSQL | defaults | `shared_buffers=32MB` (1 GB de RAM, 3 bases) |

[`docker-compose.cloud.yml`](./docker-compose.cloud.yml) es el único archivo específico de la nube.

### Apagar todo

```bash
cd infra/aws && terraform destroy
```

> ⚠️ Una Elastic IP es gratuita **mientras esté asociada a una instancia encendida**. Si se apaga la instancia sin liberar la EIP, AWS cobra por ella (~$3.60/mes). Para pausar sin gastar, `terraform destroy` y volver a `apply` cuando haga falta (el bootstrap es automático, ~5 min).

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
**Status**: Tasks 1, 2A, 2B, 3, 4 y 5 completadas y verificadas end-to-end, + despliegue cloud en AWS (🚀 Ready for demo)
**Roadmap**: 110/110 puntos base + punto extra implementado — ver [`TASKS_ROADMAP.md`](./TASKS_ROADMAP.md)
