#!/usr/bin/env bash
#
# demo_circuit_breaker.sh — muestra el circuit breaker abriendose y cerrandose
# (Task 3, checkpoint del video: "mostrar circuit breaker abierto").
#
# POR QUE ESTE SCRIPT EXISTE
#
# `demo.sh` demuestra la resiliencia de cara al usuario: se detiene notif-svc,
# las reservas siguen devolviendo 201, y el outbox entrega las notificaciones
# cuando el servicio vuelve. Pero en ESE camino el circuit breaker no llega a
# abrirse: al detener el contenedor, Consul deja de reportar a notif-svc como
# "passing", `get_service_url()` falla primero, y la notificacion va derecho al
# outbox sin tocar la capa de retry/breaker.
#
# Para VER el breaker hay que simular un notif-svc que si es alcanzable pero
# falla (que es el escenario para el que existe el patron). Eso hace este
# script: corre dentro de booking-svc, en UN solo proceso — necesario porque el
# estado del breaker vive en memoria del proceso — y ejercita directamente
# `app.resilience.call_notif_service`.
#
# Uso:
#   ./demo_circuit_breaker.sh
#
# Requiere: docker compose levantado.

set -uo pipefail

PASS='\033[0;32m'; FAIL='\033[0;31m'; INFO='\033[0;34m'; NC='\033[0m'
step() { echo -e "\n${INFO}==> $1${NC}"; }

step "Ejecutando la prueba dentro del contenedor booking-svc"
echo "    (el estado del circuit breaker vive en memoria del proceso,"
echo "     por eso todo corre en una sola invocacion de Python)"
echo ""

docker compose exec -T booking-svc python - <<'PYEOF'
import asyncio, time
from circuitbreaker import CircuitBreakerError
from app.resilience import (
    call_notif_service, NotifServiceError,
    CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_RECOVERY_TIMEOUT_SECONDS, RETRY_ATTEMPTS,
)
from app.discovery import get_service_url

GREEN, RED, BLUE, DIM, NC = "\033[0;32m", "\033[0;31m", "\033[0;34m", "\033[2m", "\033[0m"
def ok(m):   print(f"  {GREEN}[OK]{NC} {m}")
def info(m): print(f"  {BLUE}-->{NC} {m}")

# notif-svc alcanzable pero roto: puerto donde no escucha nadie.
DEAD = "http://notif-svc:9999/notifications"
PAYLOAD = {"user_id": 1, "type": "demo", "message": "circuit breaker demo"}

async def main():
    print(f"  Config: umbral={CIRCUIT_FAILURE_THRESHOLD} fallos, "
          f"reintentos={RETRY_ATTEMPTS}/llamada, "
          f"recovery_timeout={CIRCUIT_RECOVERY_TIMEOUT_SECONDS}s\n")

    # --- Fase 1: fallos hasta abrir el circuito -----------------------------
    print(f"{BLUE}FASE 1 — llamadas fallidas contra un notif-svc que no responde{NC}")
    for i in range(1, CIRCUIT_FAILURE_THRESHOLD + 1):
        t0 = time.perf_counter()
        try:
            await call_notif_service(DEAD, PAYLOAD, {})
        except NotifServiceError:
            dt = (time.perf_counter() - t0) * 1000
            info(f"llamada {i}: fallo tras agotar {RETRY_ATTEMPTS} reintentos "
                 f"({dt:.0f} ms — el tiempo es el backoff exponencial)")
        except CircuitBreakerError:
            dt = (time.perf_counter() - t0) * 1000
            info(f"llamada {i}: CircuitBreakerError ({dt:.1f} ms)")

    # --- Fase 2: circuito abierto ------------------------------------------
    print(f"\n{BLUE}FASE 2 — el circuito deberia estar ABIERTO{NC}")
    t0 = time.perf_counter()
    try:
        await call_notif_service(DEAD, PAYLOAD, {})
        print(f"  {RED}[FAIL]{NC} se esperaba CircuitBreakerError")
        return 1
    except CircuitBreakerError:
        dt = (time.perf_counter() - t0) * 1000
        ok(f"CIRCUITO ABIERTO: falla en {dt:.2f} ms, sin tocar la red")
        print(f"       {DIM}(compara con los ~1500 ms de la fase 1: ahora ni lo intenta){NC}")
    except NotifServiceError:
        print(f"  {RED}[FAIL]{NC} el circuito NO se abrio")
        return 1

    # --- Fase 3: recuperacion ----------------------------------------------
    print(f"\n{BLUE}FASE 3 — esperando el recovery_timeout "
          f"({CIRCUIT_RECOVERY_TIMEOUT_SECONDS}s){NC}")
    for s in range(CIRCUIT_RECOVERY_TIMEOUT_SECONDS, 0, -1):
        print(f"    {s}s...", end="\r", flush=True)
        await asyncio.sleep(1)
    print(" " * 20, end="\r")

    # La siguiente llamada actua como sonda (half-open). Se hace contra el
    # notif-svc REAL, que esta sano.
    real = f"{get_service_url('notif-svc')}/notifications"
    info(f"llamada de sonda contra el notif-svc real: {real}")
    t0 = time.perf_counter()
    try:
        await call_notif_service(real, PAYLOAD, {})
        dt = (time.perf_counter() - t0) * 1000
        ok(f"sonda exitosa en {dt:.0f} ms -> CIRCUITO CERRADO de nuevo")
    except Exception as e:
        print(f"  {RED}[FAIL]{NC} la sonda fallo: {type(e).__name__}: {e}")
        return 1

    # Confirmar que volvio a la normalidad.
    try:
        await call_notif_service(real, PAYLOAD, {})
        ok("llamada normal posterior: OK (el circuito quedo cerrado)")
    except Exception as e:
        print(f"  {RED}[FAIL]{NC} {type(e).__name__}: {e}")
        return 1

    print(f"\n{GREEN}=== Ciclo completo demostrado: "
          f"cerrado -> abierto -> half-open -> cerrado ==={NC}")
    return 0

raise SystemExit(asyncio.run(main()))
PYEOF

rc=$?
echo ""
if [ "$rc" -eq 0 ]; then
  echo -e "${PASS}Circuit breaker demostrado correctamente.${NC}"
else
  echo -e "${FAIL}La demostracion fallo (codigo $rc).${NC}"
fi
exit "$rc"
