# ============================================================
# strategy.py — Entry and Exit Strategy Logic
# ============================================================

import pandas as pd
import numpy as np
import ta
from config import (
    MA_SHORT, MA_LONG, RSI_MIN, RSI_MAX, RSI_OVERBOUGHT,
    VOLUME_MULTIPLIER, TRAILING_ACTIVATE_AT,
    TRAILING_STOP_STABLE, TRAILING_STOP_VOLATILE, TRAILING_STOP_ETF,
    VOLATILE_STOCKS, ETFS
)


def get_trailing_stop_pct(symbol):
    """Return the trailing stop % based on stock type."""
    if symbol in ETFS:
        return TRAILING_STOP_ETF
    elif symbol in VOLATILE_STOCKS:
        return TRAILING_STOP_VOLATILE
    else:
        return TRAILING_STOP_STABLE


def check_entry_conditions(symbol, bars_df):
    """
    Check all entry conditions for a symbol.
    bars_df: pandas DataFrame with columns: open, high, low, close, volume
    Returns: (bool: should_enter, str: reason)
    """
    if bars_df is None or len(bars_df) < MA_LONG + 5:
        return False, "Not enough historical data"

    df = bars_df.copy()

    # ── Moving Averages ──
    df["ma20"] = df["close"].rolling(MA_SHORT).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()

    # ── RSI ──
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    # ── Volume Average ──
    df["vol_avg"] = df["volume"].rolling(MA_SHORT).mean()

    latest = df.iloc[-1]
    price   = latest["close"]
    ma20    = latest["ma20"]
    ma50    = latest["ma50"]
    rsi     = latest["rsi"]
    volume  = latest["volume"]
    vol_avg = latest["vol_avg"]

    # ── Condition Checks ──
    reasons = []

    # 1. Price above both MAs (must be at least 2% above MA20 — avoids razor-thin entries)
    if price <= ma20 * 1.02:
        reasons.append(f"Price ${price:.2f} is NOT 2%+ above MA20 ${ma20:.2f} (threshold ${ma20*1.02:.2f})")
    if price <= ma50:
        reasons.append(f"Price ${price:.2f} is NOT above MA50 ${ma50:.2f}")

    # 2. Volume confirmation
    if volume < VOLUME_MULTIPLIER * vol_avg:
        reasons.append(f"Volume {volume:,.0f} is below {VOLUME_MULTIPLIER}x average {vol_avg:,.0f}")

    # 3. RSI in range
    if rsi < RSI_MIN:
        reasons.append(f"RSI {rsi:.1f} is too low (min {RSI_MIN})")
    if rsi > RSI_MAX:
        reasons.append(f"RSI {rsi:.1f} is too high (max {RSI_MAX})")
    if rsi > RSI_OVERBOUGHT:
        reasons.append(f"RSI {rsi:.1f} is OVERBOUGHT (above {RSI_OVERBOUGHT})")

    # 4. Higher highs and higher lows (relaxed — 3 OR 5 candle confirmation)
    recent3 = df.tail(3)
    recent5 = df.tail(5)
    hh3 = all(recent3["high"].diff().dropna() > 0)
    hl3 = all(recent3["low"].diff().dropna() > 0)
    hh5 = all(recent5["high"].diff().dropna() > 0)
    hl5 = all(recent5["low"].diff().dropna() > 0)
    if not ((hh3 and hl3) or (hh5 and hl5)):
        reasons.append("No clear uptrend (higher highs / higher lows not confirmed)")

    if reasons:
        return False, " | ".join(reasons)

    return True, (
        f"All conditions met — Price: ${price:.2f} | "
        f"MA20: ${ma20:.2f} | MA50: ${ma50:.2f} | "
        f"RSI: {rsi:.1f} | Volume: {volume:,.0f}"
    )


def check_trailing_stop(symbol, entry_price, current_price, highest_price):
    """
    Check if trailing stop has been hit.
    Returns: (bool: stop_hit, float: stop_price, str: status)
    """
    gain_pct = (current_price - entry_price) / entry_price
    trail_pct = get_trailing_stop_pct(symbol)

    # Only activate trailing stop after minimum gain
    if gain_pct < TRAILING_ACTIVATE_AT:
        stop_price = entry_price * (1 - trail_pct)
        return False, stop_price, f"Trailing stop not yet active (gain: {gain_pct*100:.1f}%)"

    # Trailing stop is based on highest price reached
    stop_price = highest_price * (1 - trail_pct)

    if current_price <= stop_price:
        return True, stop_price, f"TRAILING STOP HIT — Current: ${current_price:.2f} | Stop: ${stop_price:.2f}"

    return False, stop_price, f"Trailing stop active — Stop: ${stop_price:.2f} | Current: ${current_price:.2f}"


def check_profit_targets(entry_price, current_price):
    """
    Check if profit taking levels have been reached.
    Returns list of triggered levels.
    """
    gain_pct = (current_price - entry_price) / entry_price
    triggered = []

    if gain_pct >= 0.20:
        triggered.append({"level": 2, "pct": 20, "action": "Sell 25% of position"})
    elif gain_pct >= 0.10:
        triggered.append({"level": 1, "pct": 10, "action": "Sell 25% of position"})

    return triggered


def market_is_favorable(spy_bars_df):
    """
    Check if overall market trend is bullish.
    Uses SPY as market proxy.
    """
    if spy_bars_df is None or len(spy_bars_df) < 10:
        return True  # Assume favorable if no data

    df = spy_bars_df.copy()
    df["ma20"] = df["close"].rolling(20).mean()
    latest = df.iloc[-1]

    # Market is bullish if SPY is above its 20-day MA
    return latest["close"] > latest["ma20"]
