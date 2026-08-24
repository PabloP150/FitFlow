# Configuración de Claude Desktop para FitFlow MCP

Este documento explica cómo configurar Claude Desktop para que interactúe con FitFlow a través del MCP Server.

## Prerrequisitos

1. ✅ Tienes Claude Desktop instalado en esta máquina
2. ✅ Los servicios FitFlow están corriendo: `docker compose up --build` (o al menos Consul + booking-svc + users-svc)
3. ✅ Python 3.12+ disponible en la terminal (para ejecutar fitflow-mcp)

## Instalación del MCP Server local

El MCP Server de FitFlow se ejecuta como un proceso Python **local** (en tu máquina), no dentro de Docker. Esto permite que Claude Desktop se conecte vía stdio sin complejidad de networking.

### 1. Instalar dependencias de fitflow-mcp

```bash
cd /Users/pablopineda/Desktop/Proyecto/fitflow-mcp
pip install -r requirements.txt
```

O si prefieres usar un venv:

```bash
cd /Users/pablopineda/Desktop/Proyecto/fitflow-mcp
python3 -m venv venv
source venv/bin/activate  # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Verificar que el servidor MCP funciona (prueba manual)

Antes de configurar Claude Desktop, prueba que el servidor puede conectarse a Consul:

```bash
cd /Users/pablopineda/Desktop/Proyecto

# Desde otra terminal, verifica que Consul está up:
curl http://localhost:8500/v1/status/leader
# Debe devolver un JSON con el líder de Consul

# Ahora intenta ejecutar el servidor MCP en modo debug:
python -c "
import sys
sys.path.insert(0, '/Users/pablopineda/Desktop/Proyecto/fitflow-mcp')
from app.config import settings
from app.discovery import get_service_url

print('Settings:')
print(f'  CONSUL_HOST: {settings.CONSUL_HOST}')
print(f'  CONSUL_PORT: {settings.CONSUL_PORT}')
print(f'  MCP_RUN_MODE: {settings.MCP_RUN_MODE}')

try:
    url = get_service_url('booking-svc')
    print(f'✓ booking-svc discovered at: {url}')
except Exception as e:
    print(f'✗ Failed to discover booking-svc: {e}')
"
```

Si ves `✓ booking-svc discovered at: http://localhost:8001`, la configuración es correcta. Si hay errores, revisa que:
- Consul está corriendo: `docker compose up consul`
- booking-svc y users-svc están corriendo: `docker compose up booking-svc users-svc`
- Las env vars son correctas: `CONSUL_HOST=localhost`, `CONSUL_PORT=8500`, `MCP_RUN_MODE=local`

## 3. Configurar claude_desktop_config.json

Encuentra tu archivo de configuración según tu SO:

### macOS
```bash
~/.config/Claude/claude_desktop_config.json  # o
~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Windows
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Linux
```bash
~/.config/Claude/claude_desktop_config.json
```

### Contenido de claude_desktop_config.json

Si no existe el archivo, créalo. Si existe, agrega la sección `mcpServers`:

```json
{
  "mcpServers": {
    "fitflow": {
      "command": "python",
      "args": [
        "/Users/pablopineda/Desktop/Proyecto/fitflow-mcp/app/server.py"
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

**Notas importantes:**
- Reemplaza `/Users/pablopineda/Desktop/Proyecto/` con la ruta real si es diferente
- `CONSUL_HOST` debe ser `localhost` (NO `consul` — eso solo funciona dentro de docker-compose)
- `CONSUL_PORT` es `8500` (puerto de Consul en el host, expuesto por docker-compose)
- `MCP_RUN_MODE` debe ser `local` (para ejecutarse en el host)

### Formato completo de claude_desktop_config.json (ejemplo con comentarios)

```json
{
  "mcpServers": {
    "fitflow": {
      "command": "python",
      "args": [
        "/Users/pablopineda/Desktop/Proyecto/fitflow-mcp/app/server.py"
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

Si ya tienes otros servidores MCP, simplemente agrega la sección `"fitflow"` al objeto `mcpServers` existente.

## 4. Reiniciar Claude Desktop

**Importante**: Claude Desktop carga la configuración una sola vez al iniciar. Debes cerrar y reabrirlo completamente.

1. Cierra Claude Desktop (Cmd+Q en macOS, Alt+F4 en Windows, etc.)
2. Espera 2 segundos
3. Reabre Claude Desktop
4. Aguarda a que cargue (puedes ver en la consola del desenvolvedor si el MCP server se conectó)

## 5. Verificar que las tools aparecen

Una vez que Claude Desktop haya reiniciado:

1. Abre una nueva conversación
2. Busca el icono de "hammer" (herramientas) en el panel derecho
3. Expande "fitflow" y verifica que ves:
   - `get_available_classes` — lista clases disponibles
   - `create_booking` — crea una reserva (requiere email/password)
   - `cancel_booking` — cancela una reserva (requiere email/password)

Si no ves las tools:
- Revisa la consola/logs de Claude Desktop para errores de conexión
- Verifica que `app/server.py` existe y es ejecutable
- Prueba manualmente: `python /Users/pablopineda/Desktop/Proyecto/fitflow-mcp/app/server.py` (debe estar escuchando en stdin sin errores)

## 6. Usar las tools en conversación

### Ejemplo 1: Listar clases

**Tú:**
> "¿Qué clases fitness hay disponibles en FitFlow?"

**Claude internamente:**
1. Llama `get_available_classes` tool vía MCP
2. fitflow-mcp consulta a booking-svc (vía Consul discovery en localhost:8001)
3. booking-svc devuelve la lista de clases
4. Claude formatea la respuesta para el usuario

**Respuesta esperada:**
> Hay 4 clases disponibles:
> 1. Yoga Matutino (20 cupos) — mañana 09:00
> 2. Spinning (15 cupos) — mañana 10:00
> 3. CrossFit (18 cupos) — mañana 11:00
> 4. Pilates (16 cupos) — mañana 14:00

### Ejemplo 2: Crear una reserva

**Tú:**
> "Quiero registrar a alice@example.com con contraseña secret123, y reservarla en Yoga Matutino"

**Claude internamente:**
1. Llama `create_booking` con class_id=1, email=alice@example.com, password=secret123
2. fitflow-mcp hace login en users-svc (obtiene JWT)
3. fitflow-mcp crea la reserva en booking-svc
4. booking-svc notifica a notif-svc automáticamente
5. Claude confirma la reserva

**Respuesta esperada:**
> ✓ Reserva creada exitosamente! Alice está inscrita en Yoga Matutino (ID: 1)

### Ejemplo 3: Cancelar una reserva

**Tú:**
> "Cancela la reserva ID 1 para alice@example.com (contraseña secret123)"

**Claude internamente:**
1. Llama `cancel_booking` con booking_id=1, email=alice@example.com, password=secret123
2. fitflow-mcp hace login, obtiene JWT
3. fitflow-mcp cancela la reserva en booking-svc
4. booking-svc notifica la cancelación a notif-svc
5. Claude confirma

**Respuesta esperada:**
> ✓ Reserva 1 cancelada exitosamente. Alice fue notificada.

## Troubleshooting

### Error: "Connection refused" al conectar con Consul

**Causa**: Consul no está corriendo o no está accesible en localhost:8500

**Solución**:
```bash
docker compose up consul
# Verifica que está up:
curl http://localhost:8500/v1/status/leader
```

### Error: "Service not found" al resolver booking-svc

**Causa**: booking-svc no se registró en Consul (no está corriendo o falló al registrarse)

**Solución**:
```bash
docker compose logs booking-svc | tail
# Busca línea: "[booking-svc] Registered in Consul"
# Si no está, el servicio probablemente crasheó al iniciar
```

### Error: "Invalid token" en login

**Causa**: Las credenciales son incorrectas o el usuario no existe

**Solución**:
1. Registra un usuario primero (si no existe):
```bash
curl -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "secret123",
    "full_name": "Alice Wonderland"
  }'
```

2. Verifica que las credenciales en Claude Desktop coinciden exactamente

### Error: "Module not found" al ejecutar server.py

**Causa**: Las dependencias no están instaladas o Python no encuentra el módulo

**Solución**:
```bash
cd /Users/pablopineda/Desktop/Proyecto/fitflow-mcp
pip install -r requirements.txt

# Verifica que se puede importar:
python -c "import mcp; print(mcp.__version__)"
```

### Claude Desktop muestra el icono de herramientas pero sin tools

**Causa**: El servidor MCP conectó pero no expuso las tools correctamente

**Solución**:
1. Revisa los logs de Claude Desktop (Cmd+Option+I en macOS)
2. Busca errores como "AttributeError" o "ImportError"
3. Verifica que `app/server.py` tiene decoradores `@mcp.tool()` correctamente

## Próximos pasos

Una vez que las tools funcionen:

1. **Prueba casos de uso**:
   - Listar clases
   - Crear reserva
   - Cancelar reserva
   - Múltiples usuarios

2. **Integración futura** (Tasks 3-5):
   - Task 3: Agregar resiliencia + logs con correlation-id
   - Task 4: Endurecimiento de seguridad + video demo
   - Task 5: Agent-to-Agent (A2A) para orquestación compleja

3. **Alternativa HTTP** (futuro):
   - Si quieres correr el MCP server dentro de docker-compose (perfil `http`):
   ```bash
   docker compose --profile http up
   # Luego conectar Claude Desktop a http://localhost:8000
   ```
   - Esto requiere configuración diferente en `claude_desktop_config.json` (usar Custom Connector)
   - Por ahora, **usa stdio local** (más simple y confiable)

---

**¿Problemas?** Revisa:
1. Que Consul está up: `curl http://localhost:8500/ui/`
2. Que los servicios están up: `docker compose ps`
3. Que fitflow-mcp puede iniciar: `python /Users/pablopineda/Desktop/Proyecto/fitflow-mcp/app/server.py` (Ctrl+C para parar)
4. Que claude_desktop_config.json es válido JSON: `python -m json.tool ~/.config/Claude/claude_desktop_config.json`
