# Configuración de Claude Desktop para FitFlow MCP (Task 2B)

Cómo conectar Claude Desktop al MCP Server de FitFlow para poder operar el
sistema en lenguaje natural. Esto es lo que demuestra el criterio *"MCP Server
funciona: Claude puede crear una reserva"* (20 pts).

## Prerrequisitos

1. Claude Desktop instalado — https://claude.ai/download
2. El stack corriendo: `docker compose up -d --build`
3. Python 3.10+ en la máquina

> El MCP Server se ejecuta como proceso **local** (no dentro de Docker):
> Claude Desktop se conecta por stdio, sin complicaciones de networking.
> El contenedor `fitflow-mcp` del compose es el transporte HTTP, que es el que
> consumen los agentes A2A de Task 5 — son dos transportes del mismo server.

---

## 1. Instalar las dependencias del MCP Server

Desde la raíz del repo:

```bash
cd fitflow-mcp
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

**Si `pip` falla compilando `pydantic-core`**: tu Python es más nuevo que los
pins de `requirements.txt` (pasa con Python 3.13+, porque `pydantic==2.10.3`
no publica wheels para esas versiones). Instalá las dependencias sin el pin
estricto — el MCP Server no necesita esa versión exacta:

```bash
./.venv/bin/pip install "mcp==1.8.0" "httpx==0.28.1" "python-consul2==0.1.5" \
  "pydantic>=2.12" "pydantic-settings>=2.6"
```

(Los pins de `requirements.txt` siguen siendo los correctos para la imagen
Docker, que usa Python 3.12.)

---

## 2. Probar que el server arranca y descubre los servicios

```bash
# Con el stack levantado, desde fitflow-mcp/
CONSUL_HOST=localhost CONSUL_PORT=8500 MCP_RUN_MODE=local \
  ./.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
from app.discovery import get_service_url
for svc in ('booking-svc', 'users-svc', 'notif-svc'):
    print(f'{svc}: {get_service_url(svc)}')
"
```

Esperado:

```
booking-svc: http://localhost:8001
users-svc: http://localhost:8003
notif-svc: http://localhost:8002
```

Si falla, revisá que Consul esté arriba (`curl http://localhost:8500/v1/status/leader`)
y que las variables sean `CONSUL_HOST=localhost` y `MCP_RUN_MODE=local`
(el hostname `consul` solo resuelve *dentro* de docker-compose).

---

## 3. Configurar `claude_desktop_config.json`

Ubicación según el sistema:

| SO | Ruta |
|---|---|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Si el archivo no existe, creálo. **Usá rutas absolutas** — Claude Desktop no
hereda tu shell ni tu directorio actual:

```json
{
  "mcpServers": {
    "fitflow": {
      "command": "/RUTA/ABSOLUTA/AL/REPO/fitflow-mcp/.venv/bin/python",
      "args": ["/RUTA/ABSOLUTA/AL/REPO/fitflow-mcp/app/server.py"],
      "env": {
        "CONSUL_HOST": "localhost",
        "CONSUL_PORT": "8500",
        "MCP_RUN_MODE": "local"
      }
    }
  }
}
```

Para generar el archivo ya con las rutas correctas de tu máquina:

```bash
# Desde la raíz del repo
mkdir -p ~/.config/Claude
REPO="$(pwd)"
cat > ~/.config/Claude/claude_desktop_config.json <<EOF
{
  "mcpServers": {
    "fitflow": {
      "command": "$REPO/fitflow-mcp/.venv/bin/python",
      "args": ["$REPO/fitflow-mcp/app/server.py"],
      "env": {
        "CONSUL_HOST": "localhost",
        "CONSUL_PORT": "8500",
        "MCP_RUN_MODE": "local"
      }
    }
  }
}
EOF
python3 -m json.tool ~/.config/Claude/claude_desktop_config.json   # validar
```

Si ya tenés otros MCP servers configurados, agregá solo la clave `"fitflow"`
dentro de `mcpServers`.

---

## 4. Reiniciar Claude Desktop

La configuración se lee **una sola vez al arrancar**: hay que cerrarlo por
completo (no solo la ventana) y volver a abrirlo.

---

## 5. Verificar que aparecen las tools

En una conversación nueva, abrí el panel de herramientas (ícono de
herramientas / "search and tools"). Bajo `fitflow` deberías ver **5 tools**:

| Tool | Qué hace |
|---|---|
| `get_available_classes_tool` | Lista las clases con cupo |
| `create_booking_tool` | Crea una reserva (login + POST) |
| `cancel_booking_tool` | Cancela una reserva |
| `send_notification_tool` | Envía una notificación (Task 5) |
| `get_notification_history_tool` | Historial de notificaciones (Task 5) |

---

## 6. Usarlo en lenguaje natural

Registrá primero un usuario (si no existe):

```bash
curl -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"secret123","full_name":"Alice"}'
```

Ejemplos de conversación:

> **"¿Qué clases de fitness hay disponibles?"**
> Claude llama `get_available_classes_tool` → muestra las 4 clases con cupo.

> **"Reserva Yoga Matutino para alice@example.com, contraseña secret123"**
> Claude llama `create_booking_tool` → hace login, crea la reserva, y
> booking-svc notifica a notif-svc automáticamente.

> **"Cancela la reserva 1 de alice@example.com (contraseña secret123)"**
> Claude llama `cancel_booking_tool`.

Verificar en la base que la reserva existe de verdad:

```bash
docker compose exec booking-db psql -U booking_admin -d booking_db \
  -c "SELECT id, user_id, class_id, status FROM bookings ORDER BY id DESC LIMIT 5;"
```

---

## Troubleshooting

### No aparece `fitflow` en el panel de herramientas

- Validá el JSON: `python3 -m json.tool ~/.config/Claude/claude_desktop_config.json`
- Verificá que las rutas sean absolutas y existan:
  `ls -l /RUTA/AL/REPO/fitflow-mcp/.venv/bin/python`
- Probá el comando a mano — debe quedarse esperando en stdin sin errores
  (Ctrl+C para salir):
  ```bash
  CONSUL_HOST=localhost MCP_RUN_MODE=local \
    ./fitflow-mcp/.venv/bin/python ./fitflow-mcp/app/server.py
  ```
- Cerrá Claude Desktop **completamente** y reabrilo.

### "Connection refused" contra Consul

```bash
docker compose ps consul
curl http://localhost:8500/v1/status/leader
```

### "Service not found" al resolver booking-svc

```bash
docker compose logs booking-svc | tail
# Debe aparecer el evento consul.registered
```

### "Invalid token" / login falla

El usuario no existe o las credenciales no coinciden. Registralo con el `curl`
del paso 6.

### `ModuleNotFoundError` al arrancar el server

Las dependencias no están en el intérprete que apunta `command`. Verificá que
sea el Python del venv (`.venv/bin/python`) y no el del sistema:

```bash
./fitflow-mcp/.venv/bin/python -c "import mcp; print('ok')"
```

---

## Relación con el resto del proyecto

- **Task 2B (esto)**: Claude Desktop → MCP (stdio) → microservicios.
- **Task 5**: los agentes A2A usan el **mismo** MCP Server por transporte HTTP
  (`http://fitflow-mcp:8000/mcp`) dentro de docker-compose. Ver la sección
  "Agent-to-Agent" del [`README.md`](./README.md).
