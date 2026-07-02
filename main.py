import asyncio
import logging
import sys

from aiogram import exceptions as aio_exceptions

from bot.dispatcher import setup_dispatcher
from config import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_once(bot, dp, db) -> float:
    """Run a single polling session. Returns suggested backoff (sec), 0 = exit."""
    try:
        await db.connect()
    except Exception:
        logger.exception("Failed to open SQLite database; aborting.")
        return 0

    try:
        logger.info("Bot starting long-polling…")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=False,
        )
    except aio_exceptions.RetryAfter as e:
        delay = min(max(e.retry_after, 1), 60)
        logger.warning("Rate limit hit. Sleeping %ss before reconnect.", delay)
        return delay
    except aio_exceptions.NetworkError as e:
        logger.warning("Network error: %s. Reconnecting in 5s.", e)
        return 5
    except Exception:
        logger.exception("Fatal error in bot loop.")
        return 10
    finally:
        try:
            await db.close()
        except Exception:
            logger.exception("Error while closing DB.")
        try:
            await bot.session.close()
        except Exception:
            pass
    return 0


async def main():
    """Bot loop with bounded retry on transient Telegram errors (no recursion)."""
    while True:
        bot, dp, db = setup_dispatcher()
        backoff = await _run_once(bot, dp, db)
        if not backoff:
            break
        await asyncio.sleep(backoff)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except SystemExit:
        pass
