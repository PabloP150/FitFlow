#!/usr/bin/env bash
#
# demo_a2a.sh — Demo end-to-end de la red de agentes A2A (Task 5)
#
# Demuestra, en orden:
#   1. Health checks de los 3 agentes
#   2. Agent Cards publicados en /.well-known/agent.json
#   3. Consul ANTES: los agentes NO estan registrados
#   4. El boton del dashboard: descubrimiento via Agent Card -> publicacion en Consul
#   5. Consul DESPUES: los agentes aparecen, en verde (passing)
#   6. Instruccion en lenguaje natural -> Gemini decide -> delegacion A2A
#   7. Verificacion independiente: la reserva y la notificacion existen de
#      verdad en booking-svc / notif-svc (los agentes no inventaron nada)
#   8. Logs de comunicacion A2A entre agentes
#
# Uso:
#   ./demo_a2a.sh
#
# Requiere: docker compose ya levantado (`docker compose up -d --build`),
# curl, jq, y una GEMINI_API_KEY real en .env para el paso 6.

set -uo pipefail

USERS_URL="http://localhost:8003"
BOOKING_URL="http://localhost:8001"
NOTIF_URL="http://localhost:8002"
CONSUL_URL="http://localhost:8500"
ORCH_URL="http://localhost:9000"
BOOKING_AGENT_URL="http://localhost:9001"
NOTIF_AGENT_URL="http://localhost:9002"

EMAIL="a2a-demo@example.com"
PASSWORD="secret123"

PASS='\033[0;32m'
FAIL='\033[0;31m'
INFO='\033[0;34m'
WARN='\033[0;33m'
NC='\033[0m'

step()  { echo -e "\n${INFO}==> $1${NC}"; }
ok()    { echo -e "${PASS}[OK]${NC} $1"; }
bad()   { echo -e "${FAIL}[FAIL]${NC} $1"; }
warn()  { echo -e "${WARN}[WARN]${NC} $1"; }

fail_count=0
check() {
  if [ "$2" -eq 0 ]; then
    ok "$1"
  else
    bad "$1"
    fail_count=$((fail_count + 1))
  fi
}

# ---------------------------------------------------------------- 1. health
step "1. Health checks de los agentes"
for pair in "orchestrator-agent:$ORCH_URL" "booking-agent:$BOOKING_AGENT_URL" "notification-agent:$NOTIF_AGENT_URL"; do
  name="${pair%%:*}"; url="${pair#*:}"
  status=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$url/healthz")
  [ "$status" = "200" ]; check "$name responde /healthz (HTTP $status)" $?
done

# ----------------------------------------------------------- 2. agent cards
step "2. Agent Cards en /.well-known/agent.json"
booking_skills=$(curl -s -m 5 "$BOOKING_AGENT_URL/.well-known/agent.json" | jq -r '[.skills[].id] | join(", ")')
notif_skills=$(curl -s -m 5 "$NOTIF_AGENT_URL/.well-known/agent.json" | jq -r '[.skills[].id] | join(", ")')
echo "    Booking Agent      -> $booking_skills"
echo "    Notification Agent -> $notif_skills"
echo "$booking_skills" | grep -q "create_booking"; check "Booking Agent publica create_booking" $?
echo "$notif_skills" | grep -q "send_notification"; check "Notification Agent publica send_notification" $?

# El SDK sirve tambien su ruta por defecto (A2A v1.0)
alt=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$BOOKING_AGENT_URL/.well-known/agent-card.json")
[ "$alt" = "200" ]; check "Tambien disponible en /.well-known/agent-card.json (default del SDK)" $?

# --------------------------------------------------------- 3. consul ANTES
step "3. Consul ANTES del descubrimiento"
# Estado limpio, para que la demo sea repetible: si una corrida anterior ya
# publico los agentes, se dan de baja antes de empezar.
curl -s -m 15 -X POST "$ORCH_URL/agents/reset" > /dev/null
sleep 1
before=$(curl -s -m 5 "$CONSUL_URL/v1/catalog/services" | jq -r 'keys | join(", ")')
echo "    Servicios en Consul: $before"
if echo "$before" | grep -q "booking-agent"; then
  bad "Los agentes NO deberian estar en Consul todavia"
  fail_count=$((fail_count + 1))
else
  ok "Los agentes NO estan en Consul (se descubren por Agent Card, no por auto-registro)"
fi

# ------------------------------------------------------- 4. boton discovery
step "4. Descubrimiento via Agent Card (el boton del dashboard)"
echo "    POST $ORCH_URL/agents/discover"
discover=$(curl -s -m 30 -X POST "$ORCH_URL/agents/discover")
n_found=$(echo "$discover" | jq '.discovered | length')
echo "$discover" | jq -r '.discovered[] | "    descubierto: \(.name) [\([.skills[].id] | join(", "))]"'
[ "$n_found" -ge 2 ]; check "Se descubrieron $n_found agentes leyendo su Agent Card" $?

# -------------------------------------------------------- 5. consul DESPUES
step "5. Consul DESPUES del descubrimiento"
sleep 12   # dar tiempo a que el health check de Consul pase a 'passing'
after=$(curl -s -m 5 "$CONSUL_URL/v1/catalog/services" | jq -r 'keys | join(", ")')
echo "    Servicios en Consul: $after"
for agent in booking-agent notification-agent; do
  passing=$(curl -s -m 5 "$CONSUL_URL/v1/health/service/$agent?passing=true" | jq 'length')
  [ "$passing" -ge 1 ]; check "$agent registrado y en verde (passing) en Consul" $?
done
echo "    Abrir $CONSUL_URL/ui/dc1/services para verlos en la UI"

# --------------------------------------------------- 6. instruccion natural
step "6. Instruccion en lenguaje natural -> Gemini -> delegacion A2A"
curl -s -m 10 -X POST "$USERS_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"A2A Demo\"}" > /dev/null
TOKEN=$(curl -s -m 10 -X POST "$USERS_URL/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

INSTRUCTION="Reserva yoga para el viernes y avisame por notificacion"
echo "    \"$INSTRUCTION\""
resp=$(curl -s -m 120 -X POST "$ORCH_URL/instruct" \
  -H "Content-Type: application/json" \
  -d "{\"instruction\":\"$INSTRUCTION\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

if echo "$resp" | jq -e '.error' > /dev/null 2>&1; then
  err_msg=$(echo "$resp" | jq -r '.error')
  warn "El Orchestrator devolvio un error:"
  echo "$err_msg" | sed 's/^/      /'
  if echo "$err_msg" | grep -qi "GEMINI_API_KEY\|API key not valid\|API_KEY_INVALID"; then
    warn "Poné una GEMINI_API_KEY real en .env y reinicia:"
    warn "  docker compose up -d --build orchestrator-agent"
  elif echo "$err_msg" | grep -qi "UNAVAILABLE\|high demand\|RESOURCE_EXHAUSTED"; then
    warn "Gemini esta sobrecargado temporalmente (ya se reintento con backoff)."
    warn "Volvé a correr el script en un momento."
  fi
  fail_count=$((fail_count + 1))
else
  echo "$resp" | jq -r '.steps[] | "    \(.skill) via \(.agent): ok=\(.ok)"'
  echo "    resumen: $(echo "$resp" | jq -r '.summary')"
  ran_booking=$(echo "$resp" | jq '[.steps[] | select(.skill=="create_booking" and .ok)] | length')
  ran_notif=$(echo "$resp" | jq '[.steps[] | select(.skill=="send_notification" and .ok)] | length')
  [ "$ran_booking" -ge 1 ]; check "Gemini delego create_booking al Booking Agent" $?
  [ "$ran_notif" -ge 1 ]; check "Gemini delego send_notification al Notification Agent" $?
  # Los ids reales los devuelve el propio resultado de la delegacion.
  USER_ID=$(echo "$resp" | jq -r '[.steps[] | select(.skill=="create_booking") | .result.user_id] | first // empty' | cut -d. -f1)
  BOOKING_ID=$(echo "$resp" | jq -r '[.steps[] | select(.skill=="create_booking") | .result.id] | first // empty' | cut -d. -f1)
fi

# ------------------------------------------- 7. verificacion independiente
step "7. Verificacion independiente (los agentes operaron servicios reales)"
if [ -n "${BOOKING_ID:-}" ]; then
  got=$(curl -s -m 10 "$BOOKING_URL/bookings/$BOOKING_ID" -H "Authorization: Bearer $TOKEN")
  echo "$got" | jq -e '.id' > /dev/null 2>&1
  check "booking-svc tiene la reserva $BOOKING_ID creada por el Booking Agent" $?
  echo "$got" | jq -r '"    reserva: id=\(.id) class_id=\(.class_id) status=\(.status)"'
else
  warn "Sin BOOKING_ID (el paso 6 no completo); se omite la verificacion de la reserva"
fi

if [ -n "${USER_ID:-}" ]; then
  notifs=$(curl -s -m 10 "$NOTIF_URL/notifications/user/$USER_ID" -H "Authorization: Bearer $TOKEN")
  n=$(echo "$notifs" | jq 'length' 2>/dev/null || echo 0)
  [ "$n" -ge 1 ]; check "notif-svc tiene $n notificacion(es) para el usuario $USER_ID" $?
  echo "$notifs" | jq -r '.[] | "    id=\(.id) type=\(.type) \(.message)"' | head -5
else
  warn "Sin USER_ID (el paso 6 no completo); se omite la verificacion de notificaciones"
fi

# ------------------------------------------------------------- 8. logs A2A
step "8. Logs de comunicacion A2A entre agentes"
echo "    (ultimas lineas con eventos a2a.*)"
a2a_logs=$(docker compose logs --tail 400 orchestrator-agent booking-agent notification-agent 2>/dev/null \
  | grep '"event": "a2a\.' | tail -8)
if [ -n "$a2a_logs" ]; then
  echo "$a2a_logs" | sed 's/^/    /'
else
  warn "No se encontraron logs a2a.* (docker compose accesible? se ejecuto el paso 6?)"
fi
echo ""
echo "    Para ver el flujo completo en vivo:"
echo "      docker compose logs -f orchestrator-agent booking-agent notification-agent"

# ---------------------------------------------------------------- resumen
echo ""
if [ "$fail_count" -eq 0 ]; then
  echo -e "${PASS}=== Demo A2A completada sin fallos ===${NC}"
else
  echo -e "${FAIL}=== Demo A2A completada con $fail_count fallo(s) ===${NC}"
fi
echo "Dashboard: $ORCH_URL"
echo "Consul UI: $CONSUL_URL/ui/dc1/services"
exit "$fail_count"
