FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Nota: este Dockerfile se usa solo para el perfil "http" opcional
# (server_http.py, transporte streamable-http dentro de docker-compose).
# Para Claude Desktop, fitflow-mcp se ejecuta localmente vía
# `python app/server.py` (transporte stdio) desde la máquina del usuario,
# fuera de docker-compose.
CMD ["python", "-m", "app.server"]
