FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api/src:/app/packages/application/src:/app/packages/domain/src:/app/packages/persistence/src:/app/packages/providers/src:/app/packages/telemetry/src

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.lock

COPY apps/api/src ./apps/api/src
COPY packages/application/src ./packages/application/src
COPY packages/domain/src ./packages/domain/src
COPY packages/persistence/src ./packages/persistence/src
COPY packages/providers/src ./packages/providers/src
COPY packages/telemetry/src ./packages/telemetry/src

EXPOSE 8000

CMD ["uvicorn", "memeradar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
