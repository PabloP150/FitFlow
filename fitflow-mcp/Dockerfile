FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Nota: este Dockerfile corre el transporte streamable-http (server_http.py),
# que es como booking-agent y notification-agent consumen MCP (Task 5).
# Escucha en 0.0.0.0:8000, endpoint MCP en /mcp.
# Para Claude Desktop, fitflow-mcp se ejecuta localmente vía
# `python app/server.py` (transporte stdio) desde la máquina del usuario,
# fuera de docker-compose.
CMD ["python", "-m", "app.server_http"]
