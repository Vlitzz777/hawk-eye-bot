import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Crypto Signal Bot Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ENV_PATH = Path(__file__).parent / ".env"
UI_DIR = Path(__file__).parent / "ui"
bot_process: Optional[subprocess.Popen] = None
log_buffer: list[str] = []
_log_lock = asyncio.Lock()


class ConfigUpdate(BaseModel):
    BOT_TOKEN: str = ""
    EXCHANGE: str = "binance"
    RISK_DEFAULT_PERCENT: float = 1.0
    PREFERRED_PAIR: str = "BTCUSDT"
    CACHE_TTL_SECONDS: int = 300
    LOG_LEVEL: str = "INFO"


@app.on_event("startup")
async def _load_env():
    load_dotenv(ENV_PATH)


# --- Dashboard UI ----------------------------------------------------------

@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")


# Mount static UI assets (style.css, script.js)
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")


# --- Config endpoint -------------------------------------------------------

@app.post("/config")
async def update_config(cfg: ConfigUpdate):
    # Persist every key to .env
    for key, val in cfg.model_dump().items():
        if val is None or val == "":
            continue
        set_key(str(ENV_PATH), key, str(val))
    # Mirror into os.environ so the API server sees it without restart
    for key, val in cfg.model_dump().items():
        if val is None or val == "":
            continue
        os.environ[key] = str(val)
    return {"status": "success", "message": "Configuration saved to .env"}


# --- Bot lifecycle ---------------------------------------------------------

async def _stream_logs(process: subprocess.Popen):
    """Stream subprocess stdout into the in-memory log buffer.

    Fixed: original used blocking `process.stdout.readline` inside an async
    function, which blocks the entire event loop. Now uses asyncio.to_thread.
    """
    loop = asyncio.get_event_loop()

    def _read_lines():
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            # Synchronously append — list.append is atomic under GIL
            log_buffer.append(line)
            if len(log_buffer) > 200:
                del log_buffer[: len(log_buffer) - 200]

    try:
        await asyncio.to_thread(_read_lines)
    except Exception:
        logger.exception("Log streamer stopped unexpectedly.")


@app.post("/start")
async def start_bot():
    global bot_process
    if bot_process and bot_process.poll() is None:
        raise HTTPException(400, "Bot is already running")

    main_script = str(Path(__file__).parent / "main.py")
    python_exe = os.sys.executable  # use the same python that runs the API
    process = subprocess.Popen(
        [python_exe, main_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(Path(__file__).parent),
    )
    bot_process = process
    asyncio.create_task(_stream_logs(process))
    return {"status": "started", "pid": process.pid}


@app.post("/stop")
async def stop_bot():
    global bot_process
    if not bot_process or bot_process.poll() is not None:
        raise HTTPException(400, "Bot is not running")

    bot_process.terminate()
    try:
        bot_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        bot_process.kill()
    bot_process = None
    return {"status": "stopped"}


# --- Status & logs ---------------------------------------------------------

@app.get("/status")
async def get_status():
    is_running = bool(bot_process and bot_process.poll() is None)
    return JSONResponse(
        {
            "running": is_running,
            "exchange": os.getenv("EXCHANGE", "binance"),
            "preferred_pair": os.getenv("PREFERRED_PAIR", "BTCUSDT"),
            "last_signal": log_buffer[-1] if log_buffer else None,
            "pid": bot_process.pid if bot_process else None,
            "uptime": "active" if is_running else "stopped",
        }
    )


@app.get("/logs")
async def get_logs():
    return {"logs": log_buffer[-50:]}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


# --- Entrypoint for `python api.py` (used by Docker/Render/Fly) ------------

if __name__ == "__main__":
    import os
    import uvicorn

    # PaaS platforms (Render, Fly, Heroku) inject PORT.
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
    logger.info("Starting dashboard on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
