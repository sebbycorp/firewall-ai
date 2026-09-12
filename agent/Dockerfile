FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY panos.py main.py ./

ENV PYTHONUNBUFFERED=1 \
    HEARTBEAT_INTERVAL_SEC=30 \
    FW_VERIFY_TLS=false

CMD ["python", "-u", "main.py"]
