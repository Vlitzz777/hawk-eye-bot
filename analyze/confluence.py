import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# --- Per-timeframe scoring functions ---------------------------------------
# Each returns: positive = bullish, negative = bearish, 0 = neutral.


def _score_ema(df: pd.DataFrame) -> int:
    """Bullish when EMA9 > EMA21 > EMA50 > EMA200 (short-term above long-term).

    The original code had this condition INVERTED (close > e200 > e50 > e21 > e9),
    which describes a downtrend, not an uptrend. This is a critical correctness
    fix — without it, the bot would issue Long signals in bearish markets.
    """
    if len(df) < 200:
        return 0

    close = df["close"].iloc[-1]
    e9 = df["ema_9"].iloc[-1]
    e21 = df["ema_21"].iloc[-1]
    e50 = df["ema_50"].iloc[-1]
    e200 = df["ema_200"].iloc[-1]

    # Skip if any EMA is NaN (e.g. series too short)
    if any(pd.isna(v) for v in (close, e9, e21, e50, e200)):
        return 0

    # Strong bullish stack: short EMAs above long EMAs
    if close > e9 > e21 > e50 > e200:
        return 3
    # Weaker bullish: price above key EMAs
    if close > e21 > e50:
        return 1
    # Strong bearish stack
    if close < e9 < e21 < e50 < e200:
        return -3
    # Weaker bearish
    if close < e21 < e50:
        return -1
    return 0


def _score_rsi(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 0
    rsi = df["rsi_14"].iloc[-1]
    prev_rsi = df["rsi_14"].iloc[-2]
    if pd.isna(rsi) or pd.isna(prev_rsi):
        return 0

    # Oversold + turning up = bullish
    if rsi < 30 and rsi > prev_rsi:
        return 1
    # Overbought + turning down = bearish
    if rsi > 70 and rsi < prev_rsi:
        return -1
    return 0


def _score_macd(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.0
    hist = df["macd_hist"].iloc[-1]
    prev_hist = df["macd_hist"].iloc[-2]
    sig = df["macd_signal"].iloc[-1]
    line = df["macd_line"].iloc[-1]

    if any(pd.isna(v) for v in (hist, prev_hist, sig, line)):
        return 0.0

    # Histogram expanding positively
    if hist > 0 and hist > prev_hist:
        return 1.0
    if hist < 0 and hist < prev_hist:
        return -1.0
    # Weaker confirmation: MACD line above/below signal
    if line > sig:
        return 0.5
    if line < sig:
        return -0.5
    return 0.0


def _score_bb(df: pd.DataFrame) -> int:
    if len(df) < 1:
        return 0
    close = df["close"].iloc[-1]
    open_ = df["open"].iloc[-1]
    upper = df["bb_upper"].iloc[-1]
    lower = df["bb_lower"].iloc[-1]

    if any(pd.isna(v) for v in (close, open_, upper, lower)):
        return 0

    # Touch lower band AND close above open (rejection candle) = bullish
    if close <= lower * 1.002 and close >= open_:
        return 1
    # Touch upper band AND close below open (rejection) = bearish
    if close >= upper * 0.998 and close <= open_:
        return -1
    return 0


def _score_volume(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.0
    vol = df["volume"].iloc[-1]
    vma = df["vol_ma_20"].iloc[-1]
    if pd.isna(vma) or vma <= 0:
        return 0.0

    # Volume spike (>1.5x 20-period average) confirms the bar's direction
    is_bullish_bar = df["close"].iloc[-1] > df["open"].iloc[-1]
    is_bearish_bar = df["close"].iloc[-1] < df["open"].iloc[-1]

    if vol > vma * 1.5:
        if is_bullish_bar:
            return 0.5
        if is_bearish_bar:
            return -0.5
    return 0.0


def _score_sr(df: pd.DataFrame) -> int:
    """Support/Resistance reaction.

    Bug in original: used max(lows, key=abs(close-x)) which returns the
    FURTHEST support, not the nearest. Fixed to use min on absolute distance.
    """
    if len(df) < 2:
        return 0
    close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]

    highs = df[df["is_resistance"] == 1]["high"].tolist()
    lows = df[df["is_support"] == 1]["low"].tolist()

    # Filter to only supports below price (real support) and resistances above
    valid_supports = [l for l in lows if l < close]
    valid_resistances = [h for h in highs if h > close]

    if not valid_supports and not valid_resistances:
        return 0

    # Nearest support below price
    if valid_supports:
        nearest_sup = max(valid_supports)  # closest to close from below
        dist_sup = (close - nearest_sup) / close
        if 0 < dist_sup < 0.015 and prev_close < nearest_sup:
            # Bounced off support
            return 1

    # Nearest resistance above price
    if valid_resistances:
        nearest_res = min(valid_resistances)  # closest to close from above
        dist_res = (nearest_res - close) / close
        if 0 < dist_res < 0.015 and prev_close > nearest_res:
            # Rejected at resistance
            return -1

    return 0


def _score_timeframe(df: pd.DataFrame) -> float:
    if len(df) < 50:
        return 0.0
    return (
        _score_ema(df)
        + _score_rsi(df)
        + _score_macd(df)
        + _score_bb(df)
        + _score_volume(df)
        + _score_sr(df)
    )


def evaluate_confluence(ohlcv_data: dict) -> Optional[dict]:
    """Deterministic confluence engine.

    Timeframe weights: 1D=3, 4H=2, 1H=1.
    Returns a signal dict if |total_score| >= 5, otherwise None.

    Confidence formula fixed: original was `min(|s|, 100) / 2.0` which caps
    at 50% and can never produce a >50% confidence — useless. New formula
    linearly maps |score| in [5, 20] to [50%, 95%] confidence.
    """
    weights = {"1d": 3, "4h": 2, "1h": 1}
    total_score = 0.0
    per_tf: dict = {}

    for tf, df in ohlcv_data.items():
        s = _score_timeframe(df)
        per_tf[tf] = s
        total_score += s * weights.get(tf, 1)

    if abs(total_score) < 5:
        return None

    direction = "Long" if total_score > 0 else "Short"

    # Map |score| in [5, 20] -> [50%, 95%] confidence (clamped).
    abs_score = abs(total_score)
    confidence = 50.0 + (min(abs_score, 20.0) - 5.0) * (45.0 / 15.0)
    confidence = max(50.0, min(95.0, confidence))

    return {
        "direction": direction,
        "confidence": round(confidence, 1),
        "weighted_score": round(total_score, 2),
        "per_timeframe": {tf: round(v, 2) for tf, v in per_tf.items()},
    }
