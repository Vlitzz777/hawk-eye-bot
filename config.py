import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot_users.db")

    # Trading defaults
    RISK_DEFAULT_PERCENT: float = float(os.getenv("RISK_DEFAULT_PERCENT", "1.0"))
    PREFERRED_PAIR: str = os.getenv("PREFERRED_PAIR", "BTCUSDT")
    EXCHANGE: str = os.getenv("EXCHANGE", "binance").lower()

    # Cache
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Dashboard API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @property
    def is_valid(self) -> bool:
        return bool(self.BOT_TOKEN)


config = Config()
