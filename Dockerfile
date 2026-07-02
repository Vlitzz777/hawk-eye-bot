# ---------- Build stage ----------
FROM python:3.11-slim AS builder

# Install build deps for pandas / numpy / aiosqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# ---------- Runtime stage ----------
FROM python:3.11-slim

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy app code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Default: expose dashboard port
EXPOSE 8000

# Healthcheck against the dashboard
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"

# Default command: run the API dashboard. The bot itself is started from
# the dashboard UI, OR set BOT_MODE=bot to run only the Telegram bot.
CMD ["sh", "-c", "if [ \"$BOT_MODE\" = \"bot\" ]; then python main.py; else python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
