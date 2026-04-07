# ── base: shared system deps ─────────────────────────────────────────────────
FROM python:3.12-alpine AS base
WORKDIR /app
RUN apk add --no-cache gcc musl-dev libffi-dev
RUN mkdir -p /app/models

# ── development: hot-reload, debug mode ──────────────────────────────────────
FROM base AS development
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
ENV FLASK_ENV=development FLASK_DEBUG=1
CMD ["python", "run.py"]

# ── production: gunicorn, no debug ───────────────────────────────────────────
FROM base AS production
COPY requirements.txt .
RUN apt-get update && apt-get install -y default-mysql-client && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
EXPOSE 5000
ENV FLASK_ENV=production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app()"]
