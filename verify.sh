#!/bin/bash

# FitFlow Verification Script
# Verifica que Task 1 y Task 2 están funcionando correctamente

set -e

echo "======================================"
echo "FitFlow — Verification Script"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        if [ "$3" != "" ]; then
            echo "  Error: $3"
        fi
    fi
}

# ==================== TASK 1 VERIFICATION ====================
echo -e "${YELLOW}Task 1: Microservicios + Docker${NC}"
echo ""

echo "Verificando servicios en localhost..."
echo ""

# Check users-svc
echo -n "users-svc (8003): "
if curl -s http://localhost:8003/healthz | grep -q "ok"; then
    check_status 0 "Health check OK"
else
    check_status 1 "Health check FAILED"
fi

# Check booking-svc
echo -n "booking-svc (8001): "
if curl -s http://localhost:8001/healthz | grep -q "ok"; then
    check_status 0 "Health check OK"
else
    check_status 1 "Health check FAILED"
fi

# Check notif-svc
echo -n "notif-svc (8002): "
if curl -s http://localhost:8002/healthz | grep -q "ok"; then
    check_status 0 "Health check OK"
else
    check_status 1 "Health check FAILED"
fi

echo ""
echo "Verificando Consul (8500)..."
echo -n "Consul: "
if curl -s http://localhost:8500/v1/status/leader | grep -q "localhost"; then
    check_status 0 "Consul está running"
else
    check_status 1 "Consul check FAILED"
fi

echo ""
echo "Verificando registros en Consul..."

# Helper function para verificar servicio en Consul
check_consul_service() {
    local service_name=$1
    local port=$2
    echo -n "  $service_name: "

    result=$(curl -s "http://localhost:8500/v1/catalog/service/$service_name" | grep -o '"Status":"passing"')
    if [ ! -z "$result" ]; then
        check_status 0 "Registered (passing)"
    else
        check_status 1 "Not registered or not passing"
    fi
}

check_consul_service "users-svc" "8003"
check_consul_service "booking-svc" "8001"
check_consul_service "notif-svc" "8002"

echo ""
echo -e "${YELLOW}Task 1 End-to-End Test${NC}"
echo ""

# Test: Register user
echo -n "1. Registrar usuario... "
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8003/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "testpass123",
    "full_name": "Test User"
  }')

USER_ID=$(echo $REGISTER_RESPONSE | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
if [ ! -z "$USER_ID" ]; then
    check_status 0 "Usuario registrado (ID: $USER_ID)"
else
    check_status 1 "Registro fallido"
    echo "Response: $REGISTER_RESPONSE"
fi

echo ""

# Test: Login
echo -n "2. Login... "
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8003/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "testpass123"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
if [ ! -z "$TOKEN" ]; then
    check_status 0 "Login exitoso"
else
    check_status 1 "Login fallido"
    echo "Response: $LOGIN_RESPONSE"
fi

echo ""

# Test: Get classes
echo -n "3. Listar clases... "
CLASSES_RESPONSE=$(curl -s http://localhost:8001/classes)
CLASS_COUNT=$(echo $CLASSES_RESPONSE | grep -o '"id":[0-9]*' | wc -l)
if [ $CLASS_COUNT -gt 0 ]; then
    check_status 0 "$CLASS_COUNT clases disponibles"
else
    check_status 1 "No hay clases"
    echo "Response: $CLASSES_RESPONSE"
fi

echo ""

# Test: Create booking (requiere JWT)
echo -n "4. Crear reserva... "
if [ ! -z "$TOKEN" ]; then
    BOOKING_RESPONSE=$(curl -s -X POST http://localhost:8001/bookings \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"class_id": 1}')

    BOOKING_ID=$(echo $BOOKING_RESPONSE | grep -o '"id":[0-9]*' | grep -o '[0-9]*' | head -1)
    if [ ! -z "$BOOKING_ID" ]; then
        check_status 0 "Reserva creada (ID: $BOOKING_ID)"
    else
        check_status 1 "Reserva fallida"
        echo "Response: $BOOKING_RESPONSE"
    fi
else
    check_status 1 "No hay token JWT disponible (login fallido)"
fi

echo ""

# Test: Check notifications
echo -n "5. Verificar notificaciones... "
NOTIF_RESPONSE=$(curl -s http://localhost:8002/notifications/user/$USER_ID)
NOTIF_COUNT=$(echo $NOTIF_RESPONSE | grep -o '"id":[0-9]*' | wc -l)
if [ $NOTIF_COUNT -gt 0 ]; then
    check_status 0 "$NOTIF_COUNT notificaciones registradas"
else
    check_status 1 "No hay notificaciones"
    echo "Response: $NOTIF_RESPONSE"
fi

echo ""
echo "======================================"
echo -e "${GREEN}✓ Verificación completa${NC}"
echo "======================================"
echo ""
echo "Próximos pasos:"
echo "1. Revisar README.md para documentación completa"
echo "2. Para Task 2B (MCP + Claude Desktop):"
echo "   - Ver CLAUDE_DESKTOP_SETUP.md"
echo "   - Configurar claude_desktop_config.json"
echo "   - Reiniciar Claude Desktop"
echo ""
