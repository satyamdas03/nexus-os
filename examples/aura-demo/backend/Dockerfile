# syntax=docker/dockerfile:1
# ASSURE aura-demo backend — FastAPI service with assure-kernel mounted as a local package.
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install the assure-kernel package first so the backend requirements can resolve it.
COPY packages/assure-kernel /packages/assure-kernel
RUN pip install --no-cache-dir -e "/packages/assure-kernel[service]"

# Install backend Python dependencies.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code.
COPY backend /app

# Ensure the data directory exists for the persistent SQLite book.
RUN mkdir -p /app/data

# Create a non-root user for runtime security.
RUN useradd -m -u 1000 assure && chown -R assure:assure /app
USER assure

# Voice agent is run with python -m agents.livekit_assistant; ensure /packages is writable for logs if needed.
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

ENV PORTFOLIOS_DB=/app/data/portfolios.db
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
