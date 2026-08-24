# FitFlow — Quick Reference Guide

## 🔧 Comandos Útiles

### Iniciar / Detener el sistema

```bash
# Levantar TODO (con rebuild de imágenes Docker)
docker compose up --build

# Levantar TODO en background (sin ver logs)
docker compose up -d --build

# Detener TODO
docker compose down

# Detener TODO y eliminar volúmenes (borra datos)
docker compose down -v

# Ver estado de los containers
docker compose ps

# Ver logs en tiempo real de todos los servicios
docker compose logs -f

# Ver logs de UN servicio específico
docker compose logs -f booking-svc
docker compose logs -f users-svc
docker compose logs -f notif-svc

# Ver últimas 50 líneas de logs
docker compose logs --tail 50 booking-svc
```

### Probar endpoints (sin MCP)

```bash
# Health checks
curl http://localhost:8003/healthz   # users-svc
curl http://localhost:8001/healthz   # booking-svc
curl http://localhost:8002/healthz   # notif-svc

# Registrar usuario
curl -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "Pass123!",
    "full_name": "John Doe"
  }'

# Login (obtener JWT)
curl -X POST http://localhost:8003/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "Pass123!"
  }' | python3 -m json.tool

# Listar clases
curl http://localhost:8001/classes | python3 -m json.tool

# Crear reserva (requiere JWT)
TOKEN="eyJ..."  # pega el access_token del login anterior
curl -X POST http://localhost:8001/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"class_id": 1}'

# Ver notificaciones de un usuario
curl http://localhost:8002/notifications/user/1 | python3 -m json.tool

# Cancelar una reserva
curl -X POST http://localhost:8001/bookings/1/cancel \
  -H "Authorization: Bearer $TOKEN"
```

### Consul

```bash
# Abrir UI de Consul en navegador
open http://localhost:8500
# o
firefox http://localhost:8500
# o
curl http://localhost:8500/v1/status/leader

# Ver servicios registrados
curl http://localhost:8500/v1/catalog/services | python3 -m json.tool

# Ver detalles de un servicio
curl http://localhost:8500/v1/catalog/service/booking-svc | python3 -m json.tool
```

### Bases de datos (acceso directo, si necesitas debuggear)

```bash
# Conectar a users_db desde el container
docker compose exec users-db psql -U users_admin -d users_db

# Dentro del psql:
\dt                    # listar tablas
SELECT * FROM users;   # ver usuarios

# Salir
\q

# Similar para booking-db y notif-db
docker compose exec booking-db psql -U booking_admin -d booking_db
docker compose exec notif-db psql -U notif_admin -d notif_db
```

### MCP Server (fitflow-mcp)

```bash
# Instalar dependencias
cd fitflow-mcp
pip install -r requirements.txt

# Probar que el servidor inicia (en terminal, Ctrl+C para parar)
python app/server.py

# Ver si descubre Consul (con Consul corriendo)
python -c "
import sys
sys.path.insert(0, '.')
from app.discovery import get_service_url
print('booking-svc:', get_service_url('booking-svc'))
print('users-svc:', get_service_url('users-svc'))
print('notif-svc:', get_service_url('notif-svc'))
"
```

### Git

```bash
# Ver estado
git status

# Ver commits
git log --oneline

# Ver cambios
git diff

# Hacer un commit
git add .
git commit -m "Descripción del cambio"

# Ver qué hay en cada rama
git branch -v
```

### Verificación end-to-end

```bash
# Ejecutar el script de verificación
bash verify.sh

# O manualmente, paso a paso:
# 1. Ver que docker compose está corriendo
docker compose ps

# 2. Health checks
for port in 8003 8001 8002; do
  echo "Port $port:"
  curl -s http://localhost:$port/healthz
done

# 3. Verificar Consul
curl -s http://localhost:8500/v1/catalog/services | python3 -m json.tool
```

---

## 📊 State del Repositorio

### Estructura de carpetas

```
/Users/pablopineda/Desktop/Proyecto/
│
├── .git/                           # Git repository
├── .gitignore
├── .env                            # Variables de dev (NO commitear)
├── .env.example                    # Template (SÍ commitear)
│
├── docker-compose.yml              # Orquestación de 7 contenedores
│
├── README.md                       # Documentación completa
├── CLAUDE_DESKTOP_SETUP.md         # Guía para integración MCP
├── COMPLETION_STATUS.md            # Status de completación
├── QUICK_REFERENCE.md              # Este archivo
├── verify.sh                       # Script de verificación e2e
│
├── users-svc/                      # Servicio de usuarios (8003)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app + lifespan
│       ├── config.py               # Pydantic Settings
│       ├── database.py             # SQLAlchemy engine
│       ├── models.py               # User model
│       ├── schemas.py              # Pydantic schemas
│       ├── security.py             # bcrypt + JWT
│       ├── consul_client.py        # Consul registration
│       └── routers/
│           ├── health.py           # /healthz, /readyz
│           └── users.py            # /users/*, endpoints
│
├── booking-svc/                    # Servicio de reservas (8001)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py               # FitnessClass, Booking
│       ├── schemas.py
│       ├── security.py             # JWT validation
│       ├── consul_client.py
│       ├── discovery.py            # Consul service resolution
│       ├── notif_client.py         # Calls notif-svc
│       ├── seed.py                 # Seed 4 fitness classes
│       └── routers/
│           ├── health.py
│           ├── classes.py          # GET /classes
│           └── bookings.py         # POST/GET/PATCH /bookings
│
├── notif-svc/                      # Servicio de notificaciones (8002)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py               # Notification model
│       ├── schemas.py
│       ├── consul_client.py
│       └── routers/
│           ├── health.py
│           └── notifications.py    # POST/GET endpoints
│
└── fitflow-mcp/                    # MCP Server para Claude Desktop (8000)
    ├── Dockerfile                  # Opcional (para perfil http)
    ├── requirements.txt            # mcp==1.8.0 + httpx + python-consul2
    └── app/
        ├── __init__.py
        ├── server.py               # MCP stdio transport (para Claude Desktop)
        ├── server_http.py          # MCP HTTP transport (futuro)
        ├── config.py               # Pydantic Settings
        ├── discovery.py            # Consul service resolution (local/docker)
        └── tools.py                # 3 tools MCP
```

### Docker Compose Services

```
┌─ docker-compose.yml ─────────────────────────────────────┐
│                                                            │
│  DATABASES:                                                │
│  ├─ users-db (postgres:16-alpine) → 5433                 │
│  ├─ booking-db (postgres:16-alpine) → 5434               │
│  └─ notif-db (postgres:16-alpine) → 5435                 │
│                                                            │
│  INFRASTRUCTURE:                                           │
│  └─ consul (hashicorp/consul:1.17) → 8500                │
│                                                            │
│  SERVICES:                                                 │
│  ├─ users-svc (python:3.12-slim) → 8003                  │
│  ├─ booking-svc (python:3.12-slim) → 8001                │
│  └─ notif-svc (python:3.12-slim) → 8002                  │
│                                                            │
│  OPTIONAL:                                                 │
│  └─ fitflow-mcp (python:3.12-slim) → 8000 [profile: http]│
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Estado de cada servicio

| Servicio | Puerto | Estado | Verificado | Notas |
|----------|--------|--------|-----------|-------|
| users-svc | 8003 | ✅ Running | ✓ E2E | Registro, login JWT, perfil |
| booking-svc | 8001 | ✅ Running | ✓ E2E | Clases, reservas, Consul discovery |
| notif-svc | 8002 | ✅ Running | ✓ E2E | Notificaciones, historial |
| consul | 8500 | ✅ Running | ✓ UI | 4 servicios registrados |
| users-db | 5433 | ✅ Healthy | ✓ Connect | PostgreSQL con users_db |
| booking-db | 5434 | ✅ Healthy | ✓ Connect | PostgreSQL con booking_db |
| notif-db | 5435 | ✅ Healthy | ✓ Connect | PostgreSQL con notif_db |
| fitflow-mcp | stdio | ✅ Ready | ⏳ Pendiente | Listo para Claude Desktop |

### Git History

```
* e4be22e (HEAD -> main) Add completion status documentation for Task 1 + 2A
* b4ca9e3 Bootstrap + Task 1 + Task 2A: microservicios, Docker, Consul
```

### Ambiente de desarrollo

```
Python:              3.12 (en docker python:3.12-slim)
FastAPI:             0.115.6
SQLAlchemy:          2.0.36
PostgreSQL:          16-alpine
Docker Compose:      v5.1.0
JWT:                 HS256 (PyJWT 2.10.1)
Password hashing:    bcrypt 4.2.1
Consul:              1.17
MCP SDK:             1.8.0
```

### Secrets & Configuration

```
.env (NO se commitea):
├── USERS_DB_USER = "users_admin"
├── USERS_DB_PASSWORD = "dev_password_users"
├── BOOKING_DB_USER = "booking_admin"
├── BOOKING_DB_PASSWORD = "dev_password_booking"
├── NOTIF_DB_USER = "notif_admin"
├── NOTIF_DB_PASSWORD = "dev_password_notif"
├── JWT_SECRET_KEY = "your-super-secret-key..."
├── JWT_ALGORITHM = "HS256"
├── JWT_EXPIRE_MINUTES = 60
├── CONSUL_HOST = "consul"
├── CONSUL_PORT = 8500
└── MCP_RUN_MODE = "local"

.env.example (SÍ se commitea):
└── Same pero con valores dummy/documentados
```

---

## 🔐 Por qué usamos integración con Claude Desktop?

### La pregunta clave: ¿Para qué sirve?

**Sin Claude Desktop (actual):**
```
Tú escribes curl                       Respuesta JSON
curl /users/login          ─────────→  {"access_token": "..."}
                           ←─────────  (tienes que parsear manualmente)
```

**Con Claude Desktop (MCP):**
```
Tú hablas en lenguaje natural          Claude entiende
"Registra un usuario y reserva yoga"  ─────────→  Ejecuta calls en tu nombre
                                       ←─────────  Interpreta resultados y responde
```

### ¿Qué es el MCP Server?

Es un **traductor entre lenguaje natural y APIs REST**:

- **Cliente (tú)**: Hablas con Claude Desktop en español
- **Claude Desktop**: Recibe tu mensaje, lo analiza, decide qué acción tomar
- **MCP Server (fitflow-mcp)**: Traduce las acciones a llamadas HTTP reales
- **FitFlow APIs**: Ejecutan la acción, devuelven datos
- **Claude Desktop**: Interpreta los datos y te responde en lenguaje natural

### Ejemplo práctico

#### Sin MCP (lo que haces ahora):

```bash
# 1. Registrar usuario
curl -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@test.com", "password": "secret", "full_name": "Alice"}'
# {"id": 1, ...}

# 2. Login manualmente
curl -X POST http://localhost:8003/users/login ...
# {"access_token": "eyJ..."}

# 3. Guardar el token en una variable
TOKEN="eyJ..."

# 4. Crear reserva
curl -X POST http://localhost:8001/bookings \
  -H "Authorization: Bearer $TOKEN" ...
# {"id": 1, "status": "confirmed"}

# Resultado: JSON crudo que tienes que interpretar
```

#### Con MCP (lo que hará después):

```
Tú: "Registra alice@test.com con contraseña secret, luego réservala en Yoga"

Claude Desktop internamente:
1. Llama tool create_booking(class_id=1, email="alice@test.com", password="secret")
2. fitflow-mcp hace login → obtiene JWT
3. fitflow-mcp crea reserva
4. Claude interpreta: "Éxito! Alice está registrada y reservada en Yoga Matutino"

Resultado: Respuesta clara en lenguaje natural
```

### ¿Por qué es útil?

| Aspecto | Sin MCP | Con MCP |
|---------|---------|---------|
| **User Experience** | Terminal + curl | Chat natural |
| **Errores** | JSON crudo incomprensible | Explicación clara en español |
| **Automatización** | Scripts bash complicados | Instrucciones en inglés al agente |
| **No-code access** | Solo para devs | Para cualquiera |
| **Debugging** | Logs y JSON | Claude explica qué pasó |

### Casos de uso reales

1. **Gerente de fitness**: "¿Cuánta gente está inscrita en Yoga?"
   - Sin MCP: tendría que conectarse a la BD directamente
   - Con MCP: pregunta a Claude, Claude llama las tools, obtiene la respuesta

2. **Automación**: "Crea 5 usuarios de prueba"
   - Sin MCP: script bash manual
   - Con MCP: "Claude, crea estos 5 usuarios" → Claude llama create_booking 5 veces

3. **Support**: "Un usuario reporta que no puede cancelar su reserva"
   - Sin MCP: support tiene que contactar a dev
   - Con MCP: support habla con Claude, Claude cancela la reserva directamente

### Arquitectura completa

```
┌─ Claude Desktop (tu máquina) ─────────────────┐
│                                                │
│  Tú escribes:                                 │
│  "¿Qué clases hay disponibles?"               │
│                                                │
│  Claude ve las 3 tools disponibles:           │
│  - get_available_classes                      │
│  - create_booking                             │
│  - cancel_booking                             │
│                                                │
│  Claude decide: "Necesito get_available..."   │
│  y llama la tool via stdio                    │
│                                                │
└──────────────┬──────────────────────────────────┘
               │ MCP Protocol (stdio)
               ↓
┌─ fitflow-mcp (server.py) ──────────────────────┐
│                                                │
│  Recibe: get_available_classes()              │
│  Consulta a Consul: "¿dónde está booking-svc?"│
│  Llama: GET http://localhost:8001/classes    │
│  Responde a Claude: [lista de clases]        │
│                                                │
└──────────────┬──────────────────────────────────┘
               │ HTTP
               ↓
┌─ booking-svc (dentro de docker-compose) ──────┐
│                                                │
│  GET /classes                                 │
│  Calcula spots_taken con COUNT(*)            │
│  Responde: [Yoga 20/20, Spinning 15/15, ...] │
│                                                │
└──────────────┬──────────────────────────────────┘
               │
               ↓ respuesta llega a Claude
               
Claude Desktop muestra al usuario:
"Hay 4 clases disponibles:
 1. Yoga Matutino - 20 cupos
 2. Spinning - 15 cupos
 ..."
```

### Ventaja pedagógica (para el curso)

El MCP Server demuestra que **FitFlow no es solo una API**, sino un **sistema completo**:

- **Tier 1 (APIs)**: REST endpoints directos (GET /classes, POST /bookings)
- **Tier 2 (Service Registry)**: Consul descubre servicios dinámicamente
- **Tier 3 (AI Agent)**: MCP server integra el sistema completo con IA

Es decir: **la arquitectura es lo suficientemente robusta para que un agente de IA pueda operarla sin entender JSON o detalles técnicos.**

---

## 🎯 Resumen rápido

**¿Para qué sirve Claude Desktop MCP?**
- Acceso sin código a FitFlow
- Operaciones en lenguaje natural
- Automatización inteligente
- No necesita saber curl, JSON, ni tokens JWT

**¿Cuándo lo usarías en producción?**
- Chatbot de customer support ("¿Puedo cancelar mi reserva?")
- Automatización interna ("Crea 100 usuarios de prueba")
- Dashboard conversacional ("¿Cuántos ingresos tuve esta semana?")
- Integración con Slack/Teams ("@fitflow reserva yoga para el lunes")

---

**¿Quieres probar ahora?** → Ve a CLAUDE_DESKTOP_SETUP.md
