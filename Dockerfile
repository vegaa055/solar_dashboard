FROM python:3.12-slim AS base

# Install mysql client for schema loading + build tools for any C extensions
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/models

# ── Development stage ──────────────────────────────────────────
FROM base AS development
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
