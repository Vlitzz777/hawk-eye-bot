import logging

from .confluence import evaluate_confluence
from .indicators import calculate_indicators
from .market_data import fetch_ohlcv

logger = logging.getLogger(__name__)


async def get_backtest_stats(symbol: str) -> float:
    """Backtest the 1H confluence signal over the last ~600 candles.

    Critical bug fixed: the original code never called `calculate_indicators`
    on the window before passing it to `evaluate_confluence`, so every call
    raised KeyError on `df["ema_9"]` and silently fell back to the 48.0
    placeholder. The win-rate shown to users was therefore always fake.

    Also: we now evaluate the *full* multi-timeframe engine is not feasible
    inside a rolling backtest (would need 1D / 4H history at each step), so
    we approximate by using only the 1H timeframe with weight=1, and we walk
    forward only on the 1H slice.
    """
    try:
        ohlcv = await fetch_ohlcv(symbol, ["1h"], limit=600)
        df = calculate_indicators(ohlcv["1h"])

        wins = 0
        total_signals = 0
        min_window = 210  # enough to compute EMA200 + indicator warmup

        for i in range(min_window, len(df) - 3):
            window = df.iloc[: i + 1].copy()
            signal = evaluate_confluence({"1h": window})
            if not signal:
                continue

            entry_dir = signal["direction"]
            # Hold for 3 candles, then check net move
            entry_close = df.iloc[i]["close"]
            exit_close = df.iloc[i + 3]["close"]
            actual_move = exit_close - entry_close

            if (entry_dir == "Long" and actual_move > 0) or (
                entry_dir == "Short" and actual_move < 0
            ):
                wins += 1
            total_signals += 1

        if total_signals == 0:
            # No qualifying signals in the backtest window — return neutral
            return 50.0

        return round((wins / total_signals) * 100, 1)

    except Exception:
        logger.exception("Backtest failed; returning neutral 50.0")
        return 50.0
