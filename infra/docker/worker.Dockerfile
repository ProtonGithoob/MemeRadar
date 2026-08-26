FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/worker/src:/app/packages/application/src:/app/packages/domain/src

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.lock

COPY apps/worker/src ./apps/worker/src
COPY packages/application/src ./packages/application/src
COPY packages/domain/src ./packages/domain/src

CMD ["python", "-m", "memeradar_worker"]
