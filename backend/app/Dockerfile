FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

# Set work directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY app/requirements.txt /workspace/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /workspace/

# Default command: migrate to head, then serve on ${PORT:-8000} (scripts/start-api.sh).
# docker-compose.yml overrides it for the worker and adds --reload for the dev API.
# Any worker service on this image must set its own command (sh scripts/start-worker.sh);
# start-api.sh refuses to run when SERVICE_ROLE / RAILWAY_SERVICE_NAME say it is a worker.
CMD ["sh", "scripts/start-api.sh"]
