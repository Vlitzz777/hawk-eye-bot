import logging
from typing import Dict, List

import ccxt.async_support as ccxt
import pandas as pd

from config import config

logger = logging.getLogger(__name__)

# Cache of exchange instances keyed by name (kept lightweight; ccxt instances
# are cheap to construct but reuse to avoid repeated load_markets calls).
_exchange_cache: Dict[str, ccxt.Exchange] = {}


async def _get_exchange(name: str) -> ccxt.Exchange:
    name = (name or "binance").lower()
    if name in _exchange_cache:
        return _exchange_cache[name]

    exchange_class = getattr(ccxt, name, None)
    if exchange_class is None:
        raise ValueError(f"Unsupported exchange: {name}")

    ex = exchange_class({"enableRateLimit": True})
    _exchange_cache[name] = ex
    return ex


def _normalize_symbol(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT (ccxt canonical format) if needed.

    Different exchanges have different conventions:
      - Binance markets dict has both 'BTCUSDT' and 'BTC/USDT' keys.
      - Bybit markets dict only has 'BTC/USDT' (with slash).

    So we always normalize to the slashed form first, then let ccxt resolve.
    """
    s = symbol.upper().strip()
    # If it already contains a slash, keep as-is
    if "/" in s:
        return s
    # Common quote currencies to split on (longest first to avoid BTCUSDTUSD ambiguity)
    for quote in ("USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH", "BNB"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}"
    return s


async def fetch_ohlcv(
    symbol: str, timeframes: List[str], limit: int = 500
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV data for `symbol` across `timeframes`.

    Returns a dict {timeframe: DataFrame} with columns
    [open, high, low, close, volume] indexed by datetime.
    Raises RuntimeError with a human-friendly message on failure.
    """
    if not symbol:
        raise ValueError("Symbol is required")

    symbol = symbol.upper().strip()
    canonical = _normalize_symbol(symbol)
    logger.info("Symbol normalized: %s → %s", symbol, canonical)

    exchange = await _get_exchange(config.EXCHANGE)

    try:
        await exchange.load_markets()
    except Exception as e:
        logger.error("Failed to load markets for %s: %s", config.EXCHANGE, e)
        raise RuntimeError(f"Exchange {config.EXCHANGE} unreachable: {e}") from e

    # Verify the symbol exists in the exchange's markets
    if canonical not in exchange.markets:
        # Try the original form (without slash) as a fallback
        if symbol in exchange.markets:
            canonical = symbol
        else:
            logger.warning(
                "Symbol %s not found in markets dict; passing to ccxt as-is.",
                canonical,
            )

    ohlcv_data: Dict[str, pd.DataFrame] = {}
    try:
        for tf in timeframes:
            raw = await exchange.fetch_ohlcv(canonical, timeframe=tf, limit=limit)
            if not raw:
                raise RuntimeError(f"No data returned for {canonical} {tf}")

            df = pd.DataFrame(
                raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("datetime").drop(columns=["timestamp"])
            ohlcv_data[tf] = df

        return ohlcv_data
    except ccxt.BadSymbol as e:
        raise RuntimeError(
            f"Symbol {canonical} not supported on {config.EXCHANGE}: {e}"
        ) from e
    except ccxt.NetworkError as e:
        raise RuntimeError(f"Network error fetching {canonical}: {e}") from e
    except ccxt.ExchangeError as e:
        raise RuntimeError(f"Exchange error for {canonical}: {e}") from e


async def close_all_exchanges():
    for ex in _exchange_cache.values():
        try:
            await ex.close()
        except Exception:
            pass
    _exchange_cache.clear()
