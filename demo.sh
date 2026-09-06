#!/usr/bin/env bash
#
# demo.sh — Flujo end-to-end automatizado de FitFlow (Tasks 1-4)
#
# Demuestra, en orden:
#   1. Health checks de los 3 servicios
#   2. Registro + login (JWT)
#   3. Listar clases
#   4. Crear una reserva -> verifica el header `x-correlation-id`
#   5. Consultar el historial de notificaciones (requiere JWT — Task 4)
#   6. Seguridad: ownership check (otro usuario NO puede ver la reserva/notificaciones)
#   7. Resiliencia: se detiene notif-svc, se crea una reserva -> se agota el
#      retry+backoff, el circuit breaker se abre, la notificacion se
#      encola en el outbox. Se reinicia notif-svc y se espera a que el
#      worker del outbox la entregue solo.
#   8. Logs JSON estructurados (muestra unas lineas crudas con correlation_id)
#
# Uso:
#   ./demo.sh
#
# Requiere: docker compose ya levantado (`docker compose up -d --build`),
# curl, jq.

set -uo pipefail

USERS_URL="http://localhost:8003"
BOOKING_URL="http://localhost:8001"
NOTIF_URL="http://localhost:8002"

PASS='\033[0;32m'
FAIL='\033[0;31m'
INFO='\033[0;34m'
NC='\033[0m'

step()  { echo -e "\n${INFO}==> $1${NC}"; }
ok()    { echo -e "${PASS}[OK]${NC} $1"; }
bad()   { echo -e "${FAIL}[FAIL]${NC} $1"; }

fail_count=0
check() {
  # check "descripcion" "condicion (0=ok)"
  if [ "$2" -eq 0 ]; then
    ok "$1"
  else
    bad "$1"
    fail_count=$((fail_count + 1))
  fi
}

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta el comando '$1'. Instalalo y vuelve a correr el script."; exit 1; }
}
require curl
require jq
require docker

# ------------------------------------------------------------------
step "1/8 — Health checks"
# ------------------------------------------------------------------
for svc in "users-svc:$USERS_URL" "booking-svc:$BOOKING_URL" "notif-svc:$NOTIF_URL"; do
  name="${svc%%:*}"
  url="${svc#*:}"
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url/healthz")
  check "$name /healthz -> $status" $([ "$status" = "200" ] && echo 0 || echo 1)
done

# ------------------------------------------------------------------
step "2/8 — Registro + login"
# ------------------------------------------------------------------
EMAIL="demo_$(date +%s)@fitflow.test"
PASSWORD="secret123"

REGISTER_RESP=$(curl -s -o /tmp/fitflow_register.json -w "%{http_code}" -X POST "$USERS_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"Demo User\"}")
check "POST /users/register -> $REGISTER_RESP" $([ "$REGISTER_RESP" = "201" ] && echo 0 || echo 1)
USER_ID=$(jq -r '.id' /tmp/fitflow_register.json)
echo "  user_id=$USER_ID email=$EMAIL"

LOGIN_RESP=$(curl -s -o /tmp/fitflow_login.json -w "%{http_code}" -X POST "$USERS_URL/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
check "POST /users/login -> $LOGIN_RESP" $([ "$LOGIN_RESP" = "200" ] && echo 0 || echo 1)
TOKEN=$(jq -r '.access_token' /tmp/fitflow_login.json)
echo "  token=${TOKEN:0:20}..."

# Segundo usuario, para probar ownership (Task 4)
EMAIL2="demo2_$(date +%s)@fitflow.test"
curl -s -o /tmp/fitflow_register2.json -X POST "$USERS_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\",\"full_name\":\"Demo User 2\"}" >/dev/null
TOKEN2=$(curl -s -X POST "$USERS_URL/users/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\"}" | jq -r '.access_token')

# ------------------------------------------------------------------
step "3/8 — Listar clases"
# ------------------------------------------------------------------
CLASSES_RESP=$(curl -s -o /tmp/fitflow_classes.json -w "%{http_code}" "$BOOKING_URL/classes")
check "GET /classes -> $CLASSES_RESP" $([ "$CLASSES_RESP" = "200" ] && echo 0 || echo 1)
CLASS_ID=$(jq -r '.[0].id' /tmp/fitflow_classes.json)
CLASS_NAME=$(jq -r '.[0].name' /tmp/fitflow_classes.json)
echo "  Reservando class_id=$CLASS_ID ($CLASS_NAME)"

# ------------------------------------------------------------------
step "4/8 — Crear reserva + verificar x-correlation-id"
# ------------------------------------------------------------------
BOOKING_HEADERS=$(mktemp)
BOOKING_BODY=$(mktemp)
BOOKING_STATUS=$(curl -s -D "$BOOKING_HEADERS" -o "$BOOKING_BODY" -w "%{http_code}" -X POST "$BOOKING_URL/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"class_id\": $CLASS_ID}")
check "POST /bookings -> $BOOKING_STATUS" $([ "$BOOKING_STATUS" = "201" ] && echo 0 || echo 1)
BOOKING_ID=$(jq -r '.id' "$BOOKING_BODY")
CORR_ID=$(grep -i '^x-correlation-id:' "$BOOKING_HEADERS" | awk '{print $2}' | tr -d '\r')
check "Response trae header x-correlation-id ($CORR_ID)" $([ -n "$CORR_ID" ] && echo 0 || echo 1)
echo "  booking_id=$BOOKING_ID"

# ------------------------------------------------------------------
step "5/8 — Historial de notificaciones (requiere JWT — Task 4)"
# ------------------------------------------------------------------
sleep 1  # dar tiempo a que la notificacion se procese
NOTIF_STATUS=$(curl -s -o /tmp/fitflow_notifs.json -w "%{http_code}" "$NOTIF_URL/notifications/user/$USER_ID" \
  -H "Authorization: Bearer $TOKEN")
check "GET /notifications/user/$USER_ID (con JWT propio) -> $NOTIF_STATUS" $([ "$NOTIF_STATUS" = "200" ] && echo 0 || echo 1)
NOTIF_COUNT=$(jq 'length' /tmp/fitflow_notifs.json)
echo "  notificaciones encontradas: $NOTIF_COUNT"

NO_AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$NOTIF_URL/notifications/user/$USER_ID")
check "GET /notifications/user/$USER_ID SIN JWT -> $NO_AUTH_STATUS (esperado 401)" $([ "$NO_AUTH_STATUS" = "401" ] && echo 0 || echo 1)

# ------------------------------------------------------------------
step "6/8 — Ownership checks (Task 4)"
# ------------------------------------------------------------------
OTHER_GET_BOOKING=$(curl -s -o /dev/null -w "%{http_code}" "$BOOKING_URL/bookings/$BOOKING_ID" \
  -H "Authorization: Bearer $TOKEN2")
check "GET /bookings/$BOOKING_ID con JWT de OTRO usuario -> $OTHER_GET_BOOKING (esperado 403)" $([ "$OTHER_GET_BOOKING" = "403" ] && echo 0 || echo 1)

OTHER_NOTIFS=$(curl -s -o /dev/null -w "%{http_code}" "$NOTIF_URL/notifications/user/$USER_ID" \
  -H "Authorization: Bearer $TOKEN2")
check "GET /notifications/user/$USER_ID con JWT de OTRO usuario -> $OTHER_NOTIFS (esperado 403)" $([ "$OTHER_NOTIFS" = "403" ] && echo 0 || echo 1)

# ------------------------------------------------------------------
step "7/8 — Resiliencia: retry + circuit breaker + outbox"
# ------------------------------------------------------------------
echo "  Deteniendo notif-svc para simular una caida..."
docker compose stop notif-svc >/dev/null 2>&1

echo "  Creando una reserva con notif-svc caido (esto tarda unos segundos: son los reintentos con backoff)..."
START=$(date +%s)
DOWN_BOOKING=$(curl -s -o /tmp/fitflow_down_booking.json -w "%{http_code}" -X POST "$BOOKING_URL/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"class_id\": $CLASS_ID}")
END=$(date +%s)
check "POST /bookings sigue devolviendo 201 aunque notif-svc este caido -> $DOWN_BOOKING (tardo $((END-START))s por los reintentos)" \
  $([ "$DOWN_BOOKING" = "201" ] && echo 0 || echo 1)
DOWN_BOOKING_ID=$(jq -r '.id' /tmp/fitflow_down_booking.json)

echo "  Creando una segunda reserva (el circuit breaker ya deberia estar abierto -> falla rapido, sin reintentos)..."
START2=$(date +%s)
DOWN_BOOKING2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BOOKING_URL/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"class_id\": $CLASS_ID}")
END2=$(date +%s)
check "POST /bookings con circuito abierto -> $DOWN_BOOKING2 (tardo $((END2-START2))s, deberia ser << la anterior)" \
  $([ "$DOWN_BOOKING2" = "201" ] && echo 0 || echo 1)

echo "  Ambas reservas se crearon igual (booking-svc nunca depende de notif-svc para responder)."
echo "  Las notificaciones deberian estar encoladas en pending_notifications (outbox)."

echo "  Reiniciando notif-svc..."
docker compose start notif-svc >/dev/null 2>&1
echo "  Esperando ~20s a que notif-svc este sano y el outbox worker (poll cada 10s) entregue lo pendiente..."
sleep 20

FINAL_NOTIF_STATUS=$(curl -s -o /tmp/fitflow_notifs_final.json -w "%{http_code}" "$NOTIF_URL/notifications/user/$USER_ID" \
  -H "Authorization: Bearer $TOKEN")
FINAL_NOTIF_COUNT=$(jq 'length' /tmp/fitflow_notifs_final.json 2>/dev/null || echo 0)
check "Las notificaciones encoladas se entregaron via outbox (antes: $NOTIF_COUNT, ahora: $FINAL_NOTIF_COUNT)" \
  $([ "$FINAL_NOTIF_COUNT" -gt "$NOTIF_COUNT" ] && echo 0 || echo 1)

# ------------------------------------------------------------------
step "8/8 — Logs JSON estructurados con correlation_id"
# ------------------------------------------------------------------
echo "  Ultimas lineas de booking-svc relacionadas al correlation_id de la reserva creada en el paso 4 ($CORR_ID):"
docker compose logs booking-svc 2>/dev/null | grep "$CORR_ID" | tail -5 || echo "  (no se encontraron lineas — revisa 'docker compose logs booking-svc')"

echo -e "\n  Ejemplo de linea de log cruda (deberia ser un objeto JSON valido):"
docker compose logs booking-svc 2>/dev/null | grep '"event"' | tail -1

# ------------------------------------------------------------------
step "Resumen"
# ------------------------------------------------------------------
if [ "$fail_count" -eq 0 ]; then
  echo -e "${PASS}Todos los checks pasaron (0 fallos).${NC}"
  exit 0
else
  echo -e "${FAIL}$fail_count check(s) fallaron. Revisa el detalle arriba.${NC}"
  exit 1
fi
