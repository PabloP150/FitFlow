#!/usr/bin/env bash
#
# Bootstrap de la instancia de FitFlow.
# Se ejecuta una sola vez, como root, en el primer arranque.
#
# Log: /var/log/cloud-init-output.log  (y /var/log/fitflow-bootstrap.log)
set -euxo pipefail

exec > >(tee -a /var/log/fitflow-bootstrap.log) 2>&1

APP_DIR=/opt/fitflow
REGION="${aws_region}"
SSM_PREFIX="${ssm_prefix}"

echo "=== 1. Paquetes base ==="
dnf update -y
dnf install -y docker git jq

echo "=== 2. Swap ==="
# t3.micro tiene 1 GB de RAM y aca corren 11 contenedores (3 de ellos
# PostgreSQL). Sin swap el kernel empieza a matar procesos por OOM.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Con swap disponible conviene que el kernel lo use antes de llegar al limite.
sysctl -w vm.swappiness=60
echo 'vm.swappiness=60' > /etc/sysctl.d/99-fitflow.conf

echo "=== 3. Docker + Compose ==="
systemctl enable --now docker
usermod -aG docker ec2-user

# Amazon Linux 2023 no trae el plugin de Compose v2 en sus repos.
COMPOSE_VERSION=v2.32.4
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version

echo "=== 4. Codigo ==="
if [ ! -d "$${APP_DIR}/.git" ]; then
  git clone --branch "${repo_branch}" --depth 1 "${repo_url}" "$${APP_DIR}"
else
  git -C "$${APP_DIR}" fetch --depth 1 origin "${repo_branch}"
  git -C "$${APP_DIR}" reset --hard "origin/${repo_branch}"
fi

echo "=== 5. Secretos desde Parameter Store -> .env ==="
# La logica vive en refresh-env.sh (viene en el repo) para que rotar secretos
# sea `systemctl restart fitflow` y no haya que duplicarla aca.
chmod +x "$${APP_DIR}/infra/aws/refresh-env.sh"
APP_DIR="$${APP_DIR}" SSM_PREFIX="$${SSM_PREFIX}" AWS_REGION="$${REGION}" \
  "$${APP_DIR}/infra/aws/refresh-env.sh"

echo "=== 6. Arranque ==="
cd "$${APP_DIR}"
docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build

echo "=== 7. Refresco de secretos en cada boot ==="
# Si la instancia se reinicia, se vuelven a leer los secretos y a levantar todo.
cat > /etc/systemd/system/fitflow.service <<'UNITEOF'
[Unit]
Description=FitFlow (docker compose)
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/fitflow
ExecStart=/usr/bin/bash -c '/opt/fitflow/infra/aws/refresh-env.sh && /usr/bin/docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d'
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.cloud.yml stop

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable fitflow.service

echo "=== Bootstrap completo ==="
docker compose ps
