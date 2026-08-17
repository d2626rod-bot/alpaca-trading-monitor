# ============================================================
# strategy.py — Entry and Exit Strategy Logic
# ============================================================

import pandas as pd
import numpy as np
import ta
from datetime import datetime
from config import (
    MA_SHORT, MA_LONG, RSI_MIN, RSI_MAX, RSI_OVERBOUGHT,
    VOLUME_MULTIPLIER, TRAILING_ACTIVATE_AT,
    TRAILING_STOP_STABLE, TRAILING_STOP_VOLATILE, TRAILING_STOP_ETF,
    VOLATILE_STOCKS, ETFS,
    BREAKEVEN_AT, SWING_TRAIL_PCT, SCALE_OUT_AT, SCALE_OUT_SIZE,
    MAX_HOLD_DAYS, TIME_STOP_EXEMPT_GAIN, TIME_STOP_NEAR_HIGH
)


def get_trailing_stop_pct(symbol):
    """Return the trailing stop % based on stock type."""
    if symbol in ETFS:
        return TRAILING_STOP_ETF
    elif symbol in VOLATILE_STOCKS:
        return TRAILING_STOP_VOLATILE
    else:
        return TRAILING_STOP_STABLE


def _completed_bars(df):
    """Return bars through the last COMPLETED session, dropping today's
    in-progress daily bar.

    On the free IEX feed that current-day bar is only a partial slice during
    market hours, which distorts any check that reads the latest bar's volume
    or high/low (volume reads far below the full-day average; today's high/low
    hasn't formed yet). Price/MA/RSI deliberately still use the live bar.
    """
    try:
        if len(df) >= 2 and df.index[-1].date() == datetime.now().date():
            return df.iloc[:-1]
    except AttributeError:
        pass  # non-datetime index (e.g. unit tests) — use as-is
    return df


def _completed_bar_volume(df):
    """Return (volume, 20-day avg volume) from the last COMPLETED daily bar."""
    cdf = _completed_bars(df)
    avg = cdf["volume"].rolling(MA_SHORT).mean().iloc[-1]
    return float(cdf["volume"].iloc[-1]), float(avg)


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

    latest = df.iloc[-1]
    price   = latest["close"]
    ma20    = latest["ma20"]
    ma50    = latest["ma50"]
    rsi     = latest["rsi"]

    # Volume confirmation uses the last COMPLETED daily bar — today's in-progress
    # bar on the free IEX feed is a partial slice and would always read below the
    # full-day average, falsely failing every morning entry.
    volume, vol_avg = _completed_bar_volume(df)

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

    # 4. Higher highs and higher lows (relaxed — 3 OR 5 candle confirmation).
    # Evaluated on COMPLETED bars: today's partial high/low on the free IEX feed
    # hasn't formed yet, so including it falsely fails the trend on strong names.
    cdf = _completed_bars(df)
    recent3 = cdf.tail(3)
    recent5 = cdf.tail(5)
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


def compute_signal_strength(bars_df):
    """Score a candidate that already PASSED check_entry_conditions, so the
    scanner can rank the survivors and take only the strongest. Higher = better.

    Blend (all from the latest bar):
      - momentum: percent the price sits above its 20-day MA (primary weight)
      - volume confirmation: last completed bar's volume / 20-day avg (capped at 3x)
      - RSI headroom: distance below the overbought cap (rewards 55-65 over 68-70)

    Returns (score: float, detail: str). Returns (0.0, "no data") if bars are
    insufficient — the caller already has the pass/fail from check_entry_conditions.
    """
    if bars_df is None or len(bars_df) < MA_LONG + 5:
        return 0.0, "no data"

    df = bars_df.copy()
    df["ma20"]    = df["close"].rolling(MA_SHORT).mean()
    df["rsi"]     = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    latest = df.iloc[-1]

    price   = latest["close"]
    ma20    = latest["ma20"]
    rsi     = latest["rsi"]
    volume, vol_avg = _completed_bar_volume(df)   # last completed bar, not today's partial

    momentum     = (price - ma20) / ma20 * 100.0 if ma20 else 0.0   # % above MA20
    vol_ratio    = (volume / vol_avg) if vol_avg else 1.0
    vol_score    = min(vol_ratio, 3.0) * 2.0                        # confirmation, capped
    rsi_headroom = max(0.0, RSI_OVERBOUGHT - rsi) * 0.2             # prefer room to run

    score = momentum + vol_score + rsi_headroom
    detail = f"score {score:.1f} (mom {momentum:+.1f}% | vol {vol_ratio:.1f}x | rsi {rsi:.0f})"
    return round(score, 2), detail


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


def decide_exit(entry, current, high, days_held, already_scaled, hard_stop_pct):
    """Momentum-swing exit decision for one open position (pure, side-effect free).

    Rules, in priority order:
      1. Protective stop —
           * before the trade ever reaches +BREAKEVEN_AT: the disaster brake at
             entry*(1 - hard_stop_pct);
           * once it has reached +BREAKEVEN_AT ("armed"): the higher of breakeven
             (entry) and a SWING_TRAIL_PCT trail below the peak. So a pop can never
             round-trip into a loss, and gains ratchet up as price rises.
      2. Time stop — at MAX_HOLD_DAYS held, exit UNLESS the position is up
         >= TIME_STOP_EXEMPT_GAIN or still within TIME_STOP_NEAR_HIGH of its peak
         (i.e. genuinely trending — let it run).
      3. Scale-out — the first time gain reaches +SCALE_OUT_AT and we haven't yet,
         sell SCALE_OUT_SIZE of the position to bank the pop; the rest rides the trail.
      4. Otherwise hold.

    Args use raw prices; `high` is the highest price seen since entry, `days_held`
    is trading days, `already_scaled` is whether the one-time scale-out already fired.
    Returns dict: {"action": "sell_all"|"scale_out"|"hold", "reason": str, "stop": float}.
    """
    if entry <= 0:
        return {"action": "hold", "reason": "invalid entry price", "stop": 0.0}

    peak_gain = (high - entry) / entry
    gain      = (current - entry) / entry
    armed     = peak_gain >= BREAKEVEN_AT

    # ── 1. Protective stop ──
    if armed:
        stop = max(entry, high * (1 - SWING_TRAIL_PCT))
    else:
        stop = entry * (1 - hard_stop_pct)

    if current <= stop:
        if not armed:
            reason = f"Hard stop {hard_stop_pct*100:.0f}% hit at ${stop:.2f}"
        elif stop <= entry * 1.0002:
            reason = f"Breakeven stop hit at ${stop:.2f} (protected the pop)"
        else:
            reason = f"Trailing {SWING_TRAIL_PCT*100:.0f}% stop hit at ${stop:.2f} (locked +{(stop-entry)/entry*100:.1f}%)"
        return {"action": "sell_all", "reason": reason, "stop": stop}

    # ── 2. Time stop ──
    # Let it run only if genuinely doing well: up >= TIME_STOP_EXEMPT_GAIN, OR still
    # holding near its peak (within TIME_STOP_NEAR_HIGH) AND at least +BREAKEVEN_AT.
    # A sub-breakeven position hovering under a tiny peak is dead money — flush it.
    strong_or_climbing = (
        gain >= TIME_STOP_EXEMPT_GAIN
        or (gain >= BREAKEVEN_AT and current >= high * (1 - TIME_STOP_NEAR_HIGH))
    )
    if days_held >= MAX_HOLD_DAYS and not strong_or_climbing:
        return {"action": "sell_all",
                "reason": f"Time stop: held {days_held} trading days at {gain*100:+.1f}%, not trending",
                "stop": stop}

    # ── 3. Scale-out (one time) ──
    if gain >= SCALE_OUT_AT and not already_scaled:
        return {"action": "scale_out",
                "reason": f"Scale-out {SCALE_OUT_SIZE*100:.0f}% at +{SCALE_OUT_AT*100:.0f}% (banked the pop)",
                "stop": stop}

    return {"action": "hold", "reason": f"stop ${stop:.2f}", "stop": stop}


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
