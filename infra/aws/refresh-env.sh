#!/usr/bin/env bash
#
# Regenera /opt/fitflow/.env leyendo los secretos de AWS Systems Manager
# Parameter Store.
#
# Los secretos nunca viven en el repo ni en una imagen: se leen en cada
# arranque usando el rol IAM de la instancia, asi que no hay credenciales
# guardadas en disco. Rotar un secreto es:
#
#   aws ssm put-parameter --name /fitflow/JWT_SECRET_KEY \
#     --value 'nuevo' --type SecureString --overwrite
#   sudo systemctl restart fitflow
#
# Uso: refresh-env.sh [ruta-al-.env]
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fitflow}"
ENV_FILE="${1:-$APP_DIR/.env}"
SSM_PREFIX="${SSM_PREFIX:-/fitflow}"

# Region: la de la variable de entorno, o la de la propia instancia (IMDSv2).
if [ -z "${AWS_REGION:-}" ]; then
  TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || echo "")
  AWS_REGION=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-east-1")
fi

umask 077
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

# --- Configuracion no secreta (equivalente a .env.example) -------------------
cat > "$TMP" <<'ENVEOF'
USERS_DB_USER=users_admin
USERS_DB_NAME=users_db
USERS_DB_PORT=5433
BOOKING_DB_USER=booking_admin
BOOKING_DB_NAME=booking_db
BOOKING_DB_PORT=5434
NOTIF_DB_USER=notif_admin
NOTIF_DB_NAME=notif_db
NOTIF_DB_PORT=5435
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CONSUL_HOST=consul
CONSUL_PORT=8500
MCP_RUN_MODE=docker
GEMINI_MODEL=gemini-2.5-flash
BOOKING_AGENT_URL=http://booking-agent:9001
NOTIFICATION_AGENT_URL=http://notification-agent:9002
MCP_SERVER_URL=http://fitflow-mcp:8000/mcp
ENVEOF

# --- Secretos (SecureString, descifrados con el rol de la instancia) ---------
aws ssm get-parameters-by-path \
  --path "$SSM_PREFIX" \
  --with-decryption \
  --region "$AWS_REGION" \
  --query 'Parameters[].{name:Name,value:Value}' \
  --output json \
| jq -r '.[] | "\(.name | split("/") | last)=\(.value)"' >> "$TMP"

# Verificacion minima: si SSM fallo, mejor enterarse aca que con los
# contenedores arrancando a medias.
for required in JWT_SECRET_KEY USERS_DB_PASSWORD BOOKING_DB_PASSWORD NOTIF_DB_PASSWORD; do
  if ! grep -q "^$required=" "$TMP"; then
    echo "ERROR: falta $required en $SSM_PREFIX (Parameter Store)" >&2
    exit 1
  fi
done

install -m 600 "$TMP" "$ENV_FILE"
echo "Escrito $ENV_FILE con $(grep -c . "$ENV_FILE") variables desde $SSM_PREFIX"
