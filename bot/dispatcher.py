import logging

from aiogram import Bot, Dispatcher

from config import config
from database.sqlite_db import UserDB
from handlers.start import register_start_handlers
from handlers.analyze import register_analyze_handlers
from handlers.settings import register_settings_handlers


def setup_dispatcher():
    """Build a fresh Bot + Dispatcher + DB instance for a polling session."""
    if not config.is_valid:
        raise RuntimeError(
            "BOT_TOKEN is not set. Create a .env file (see .env.example) "
            "or export BOT_TOKEN before launching."
        )

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    db = UserDB()

    # Make `db` and `bot` available as kwargs in every handler (aiogram 3.x
    # injects workflow_data automatically).
    dp["db"] = db
    dp["bot"] = bot

    # Register routers
    register_start_handlers(dp)
    register_analyze_handlers(dp, db)
    register_settings_handlers(dp, db)

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    return bot, dp, db
