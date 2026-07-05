# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

# Pin the package installation so the container is reproducible.
WORKDIR /app

# Copy only what is needed to install dependencies first (layer caching).
COPY pyproject.toml README.md ./
COPY src/assure_kernel/ ./src/assure_kernel/

# Install the kernel package with service extras, no dev dependencies.
RUN pip install --no-cache-dir -e ".[service]"

# Create a non-root user to run the service.
RUN useradd -m -u 1000 assure && chown -R assure:assure /app
USER assure

# Expose the service port and declare the ASGI app.
EXPOSE 8000
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

# Health check against the deterministic /v1/health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health')" || exit 1

CMD ["uvicorn", "assure_kernel.main:app", "--host", "0.0.0.0", "--port", "8000"]
