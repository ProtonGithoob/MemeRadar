FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/worker/src:/app/packages/application/src:/app/packages/domain/src:/app/packages/persistence/src:/app/packages/telemetry/src

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.lock

COPY apps/worker/src ./apps/worker/src
COPY packages/application/src ./packages/application/src
COPY packages/domain/src ./packages/domain/src
COPY packages/persistence/src ./packages/persistence/src
COPY packages/telemetry/src ./packages/telemetry/src

CMD ["python", "-m", "memeradar_worker"]
