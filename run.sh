#!/usr/bin/env bash
# Convenience launcher: start API + dashboard. Bot is started from the UI.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "⚠️  .env not found. Copying from .env.example — edit it before running."
    cp .env.example .env
fi

if [ ! -d .venv ]; then
    echo "📦 Creating virtualenv…"
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "📥 Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "🚀 Starting dashboard on http://localhost:8000"
exec python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
