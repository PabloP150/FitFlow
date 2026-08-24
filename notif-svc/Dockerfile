FROM python:3.12-slim

# Sin esto, los print() quedan bufferizados y no aparecen en `docker logs`
# hasta que el buffer se llena (stdout no es un TTY dentro del contenedor).
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
