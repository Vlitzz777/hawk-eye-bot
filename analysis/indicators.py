import logging

import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all required indicators deterministically.

    Note on pandas_ta column naming (this was a critical bug in the original
    code — column indices were misread):

      ta.macd(close, fast=12, slow=26, signal=9) returns columns:
        MACD_12_26_9    -> MACD line        (index 0)
        MACDh_12_26_9   -> MACD histogram   (index 1)
        MACDs_12_26_9   -> signal line      (index 2)

      ta.bbands(close, length=20, std=2.0) returns columns:
        BBL_20_2.0      -> lower band       (index 0)
        BBM_20_2.0      -> middle band      (index 1)
        BBU_20_2.0      -> upper band       (index 2)
        BBB_20_2.0      -> bandwidth        (index 3)
        BBP_20_2.0      -> %B               (index 4)
    """
    df = df.copy()

    # EMAs
    for length in [9, 21, 50, 200]:
        df[f"ema_{length}"] = ta.ema(df["close"], length=length)

    # RSI
    df["rsi_14"] = ta.rsi(df["close"], length=14)

    # MACD — explicit column lookup by name to avoid index mistakes.
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is None or macd.empty:
        logger.warning("MACD computation returned empty result.")
        df["macd_line"] = pd.NA
        df["macd_signal"] = pd.NA
        df["macd_hist"] = pd.NA
    else:
        macd_cols = list(macd.columns)
        # Column names follow the pattern MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        line_col = next((c for c in macd_cols if c.startswith("MACD_")), macd_cols[0])
        hist_col = next((c for c in macd_cols if c.startswith("MACDh")), macd_cols[1] if len(macd_cols) > 1 else macd_cols[0])
        sig_col = next((c for c in macd_cols if c.startswith("MACDs")), macd_cols[2] if len(macd_cols) > 2 else macd_cols[0])

        df["macd_line"] = macd[line_col]
        df["macd_hist"] = macd[hist_col]
        df["macd_signal"] = macd[sig_col]

    # Bollinger Bands — explicit column lookup by prefix.
    bb = ta.bbands(df["close"], length=20, std=2.0)
    if bb is None or bb.empty:
        logger.warning("BB computation returned empty result.")
        df["bb_upper"] = df["close"]
        df["bb_middle"] = df["close"]
        df["bb_lower"] = df["close"]
    else:
        bb_cols = list(bb.columns)
        upper_col = next((c for c in bb_cols if c.startswith("BBU")), bb_cols[2] if len(bb_cols) > 2 else bb_cols[0])
        mid_col = next((c for c in bb_cols if c.startswith("BBM")), bb_cols[1] if len(bb_cols) > 1 else bb_cols[0])
        lower_col = next((c for c in bb_cols if c.startswith("BBL")), bb_cols[0])

        df["bb_upper"] = bb[upper_col]
        df["bb_middle"] = bb[mid_col]
        df["bb_lower"] = bb[lower_col]

    # Volume MA
    df["vol_ma_20"] = ta.sma(df["volume"], length=20)

    # Support/Resistance via 5-bar pivot fractals
    pivot_high = df["high"].rolling(5, center=True).max() == df["high"]
    pivot_low = df["low"].rolling(5, center=True).min() == df["low"]
    df["is_resistance"] = pivot_high.astype(float)
    df["is_support"] = pivot_low.astype(float)

    return df
