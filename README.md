# Hawk Eye — Crypto Signal Bot

A deterministic, confluence-backed crypto trading-signal bot for Telegram,
with an optional FastAPI dashboard for remote control.

## Quick start (local)

```bash
cp .env.example .env       # then edit BOT_TOKEN from @BotFather
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Option A: run the dashboard (UI on http://localhost:8000)
python api.py

# Option B: run only the Telegram bot
python main.py

# Option C: dashboard + bot via Docker Compose
docker-compose --profile full up --build
```

## Deploy on a FREE cloud server

The project is container-ready and ships with blueprints for the three
most popular free-tier platforms. Pick one:

---

### Option 1 — Render (recommended, easiest)

1. Push this repo to GitHub.
2. Go to <https://render.com> → **New +** → **Blueprint**.
3. Pick your GitHub repo. Render auto-detects `render.yaml` and creates:
   - `hawk-eye-dashboard` — FastAPI web service (free tier)
   - `hawk-eye-bot` — Telegram long-polling worker (free tier)
4. In Render's dashboard, set the secret env vars:
   - `BOT_TOKEN` (from `@BotFather`) on both services.
5. Click **Apply**. Render builds the Dockerfile, deploys, and gives you a
   public URL like `https://hawk-eye-dashboard.onrender.com`.

> Render's free tier sleeps after 15 min of inactivity. The first request
> after sleep takes ~30 s to wake. The Telegram **worker** stays alive as
> long as it's polling.

---

### Option 2 — Fly.io

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
flyctl auth login

# Create a persistent volume for the SQLite DB
flyctl volumes create hawk_eye_data --size 1

# Deploy
flyctl deploy

# Set secrets
flyctl secrets set BOT_TOKEN=your_telegram_bot_token
```

App URL will be `https://hawk-eye.fly.dev`. Fly.io's free tier includes
3 shared-cpu-1x VMs with 256MB RAM — enough for the dashboard AND the bot
together (run them as separate processes if needed via a process group
in `fly.toml`).

---

### Option 3 — Koyeb

1. Go to <https://app.koyeb.com> → **Create Service** → **GitHub**.
2. Pick this repo. Koyeb auto-detects the Dockerfile.
3. Set env vars: `BOT_TOKEN`, `EXCHANGE=bybit`, etc.
4. Set port to `8000` and health path to `/healthz`.
5. Deploy. Free tier = 1 web service + 512MB RAM.

---

### Option 4 — Self-host with Docker

```bash
docker build -t hawk-eye .

# Dashboard only
docker run -d --name hawk-eye \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  hawk-eye

# Or both dashboard + bot via compose
docker-compose --profile full up -d --build
```

---

## Telegram commands

| Command | Action |
|---|---|
| `/start` | Welcome + onboarding |
| `/help` | Help message |
| `/analyze BTCUSDT` | Run multi-timeframe analysis |
| `/setpair ETHUSDT` | Set default pair |
| `/risk 1.5` | Set risk % per trade (0.1–5.0) |
| `/settings` | Show current preferences |

## Confluence engine

Each timeframe (1H=1, 4H=2, 1D=3 weight) is scored by summing six
sub-scores:

| Indicator | Long contribution | Short contribution |
|---|---|---|
| EMA stack (9/21/50/200) | +3 (full) / +1 (weak) | −3 / −1 |
| RSI(14) | oversold + turning up (+1) | overbought + turning down (−1) |
| MACD histogram | expanding positively (+1) | expanding negatively (−1) |
| Bollinger Bands | rejection at lower band (+1) | rejection at upper band (−1) |
| Volume | spike + bullish bar (+0.5) | spike + bearish bar (−0.5) |
| S/R pivot | bounce off support (+1) | rejection at resistance (−1) |

A signal fires when `|weighted_score| >= 5`. Confidence is mapped linearly
from `[5, 20]` → `[50%, 95%]`.

## API endpoints (dashboard)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard UI |
| GET | `/healthz` | Liveness probe (used by Render/Fly) |
| GET | `/status` | Bot status + last signal |
| GET | `/logs` | Last 50 log lines |
| POST | `/config` | Update `.env` settings |
| POST | `/start` | Launch bot subprocess |
| POST | `/stop` | Stop bot subprocess |

## Supported exchanges

Binance, Bybit, OKX, KuCoin, Coinbase, Kraken, Gate.io, MEXC — set via
the `EXCHANGE` env var. Note: **Binance** sometimes blocks cloud IPs;
**Bybit** works reliably from most data centers.

## Disclaimer

Signals are educational, not financial advice. Always do your own research.
