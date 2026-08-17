# ============================================================
# agent.py — Main Alpaca Paper Trading Agent
# ============================================================
# Based on Trend Following + Trailing Stop Strategy
#
# HOW TO RUN:
#   python agent.py
#
# WHAT IT DOES:
#   - Scans watchlist every morning at 9:35 AM EST
#   - Checks entry conditions (MA, RSI, Volume)
#   - Places buy orders automatically
#   - Monitors trailing stops every 5 minutes
#   - Takes partial profits at +10% and +20%
#   - Generates daily report at 4:05 PM EST
#   - Logs all trades to your Excel journal
# ============================================================

import time
import os
import schedule
from datetime import datetime, timedelta
import alpaca_trade_api as tradeapi
import pandas as pd

from config import (
    API_KEY, SECRET_KEY, BASE_URL,
    WATCHLIST, SCAN_TIME, SCAN_TIME_2, SCAN_TIME_EOD, REPORT_TIME,
    TRAILING_CHECK_MINS, VIX_MAX, TRAILING_ACTIVATE_AT,
    MAX_TOTAL_EXPOSURE, PROFIT_TAKE_SIZE,
    RE_ENTRY_WAIT_DAYS, MAX_NEW_POSITIONS_PER_SCAN,
    SCALE_OUT_AT, SCALE_OUT_SIZE
)
from strategy import (
    check_entry_conditions, check_trailing_stop,
    check_profit_targets, market_is_favorable,
    get_trailing_stop_pct, compute_signal_strength, decide_exit
)
from risk import (
    calculate_position_size, check_exposure,
    portfolio_risk_summary, get_stop_loss_pct
)
from journal import log_trade, close_trade, print_summary, log_partial_sell
from sms import (
    alert_order_placed, alert_stop_hit, alert_profit_target,
    alert_daily_report, alert_agent_started, alert_trailing_stop_update
)

# ── Connect to Alpaca ──
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version="v2")

# ── Track highest prices for trailing stops ──
# Format: { "SYMBOL": highest_price_seen }
price_highs = {}

# ── Track recent stop-outs to enforce re-entry waiting period ──
# Format: { "SYMBOL": datetime_of_stopout }
recent_stopouts = {}

# ── Track entry dates for the momentum-swing time stop ──
# Format: { "SYMBOL": "YYYY-MM-DD" }  (persisted to entry_dates.json)
entry_dates = {}


def load_entry_dates():
    """Load persisted per-position entry dates (for the time stop)."""
    import json
    try:
        if os.path.exists("entry_dates.json"):
            with open("entry_dates.json", "r") as f:
                entry_dates.update(json.load(f))
            log(f"[ENTRY DATES] Loaded {len(entry_dates)} entry dates")
    except Exception as e:
        log(f"[ENTRY DATES] Error loading: {e}")


def save_entry_dates():
    """Persist per-position entry dates."""
    import json
    try:
        with open("entry_dates.json", "w") as f:
            json.dump(entry_dates, f)
    except Exception as e:
        log(f"[ENTRY DATES] Error saving: {e}")


def trading_days_held(entry_date_str):
    """Trading (business) days a position has been held. 0 if the date is unknown."""
    if not entry_date_str:
        return 0
    try:
        entry = pd.to_datetime(entry_date_str).date()
        today = datetime.now().date()
        if today <= entry:
            return 0
        return max(0, len(pd.bdate_range(entry, today)) - 1)
    except Exception:
        return 0


def _clear_position_state(symbol):
    """Forget all per-position tracking after a full close."""
    keys = [symbol, f"{symbol}_scaled"] + [k for k in list(price_highs.keys())
                                            if k.startswith(f"{symbol}_profit_")]
    for k in keys:
        price_highs.pop(k, None)
    entry_dates.pop(symbol, None)


def load_triggered_profits():
    """Load previously triggered profit levels from file."""
    import json
    try:
        if os.path.exists("triggered_profits.json"):
            with open("triggered_profits.json", "r") as f:
                data = json.load(f)
                for k, v in data.items():
                    price_highs[k] = v
            log(f"[PROFITS] Loaded triggered levels: {list(data.keys())}")
    except Exception as e:
        log(f"[PROFITS] Error loading triggered levels: {e}")


def save_triggered_profits():
    """Save triggered profit levels to file."""
    import json
    try:
        triggered = {k: v for k, v in price_highs.items()
                     if "_profit_" in str(k) or "_scaled" in str(k)}
        with open("triggered_profits.json", "w") as f:
            json.dump(triggered, f)
    except Exception as e:
        log(f"[PROFITS] Error saving triggered levels: {e}")


def restore_price_highs():
    """
    On startup, restore the true highest price for each open position
    since entry. This ensures trailing stops are correct even after restart.
    """
    positions = get_positions()
    if not positions:
        return

    log("Restoring trailing stop highs from historical data...")
    for position in positions:
        symbol      = position.symbol
        entry_price = float(position.avg_entry_price)
        current     = float(position.current_price)

        try:
            end   = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            entry_date = entry_dates.get(symbol)
            fetched = False

            for feed in ["sip", "iex"]:
                try:
                    bars = api.get_bars(
                        symbol,
                        tradeapi.rest.TimeFrame.Day,
                        start=start,
                        end=end,
                        feed=feed
                    ).df
                    if bars is None or len(bars) == 0:
                        continue
                    bars.index = pd.to_datetime(bars.index)
                    if isinstance(bars.columns, pd.MultiIndex):
                        bars.columns = bars.columns.get_level_values(0)
                    bars = bars.sort_index()
                    # Clip to the holding period — the high must be the peak SINCE
                    # entry, never a pre-entry high (which would fake a huge gain and
                    # trip the trailing stop on a freshly-bought name).
                    if entry_date:
                        bars = bars[bars.index.date >= pd.to_datetime(entry_date).date()]
                    since_entry_high = float(bars["high"].max()) if len(bars) else current
                    true_high = max(since_entry_high, current, entry_price)
                    price_highs[symbol] = true_high
                    log(f"  {symbol}: High since entry ({entry_date or 'unknown'}) = ${true_high:.2f}")
                    fetched = True
                    break
                except Exception:
                    continue

            if not fetched:
                price_highs[symbol] = max(current, entry_price)
                log(f"  {symbol}: Using current price ${current:.2f} as high (no history available)")

        except Exception as e:
            price_highs[symbol] = max(float(position.current_price), entry_price)
            log(f"  {symbol}: Error restoring high — {e}")



def log(msg):
    """Print a timestamped log message."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def get_account():
    """Get current account info."""
    try:
        return api.get_account()
    except Exception as e:
        log(f"ERROR getting account: {e}")
        return None


def get_positions():
    """Get all open positions."""
    try:
        return api.list_positions()
    except Exception as e:
        log(f"ERROR getting positions: {e}")
        return []


def get_bars(symbol, limit=60):
    """Get historical daily bars for a symbol."""
    end   = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=limit * 2)).strftime("%Y-%m-%d")

    for feed in ["sip", "iex"]:
        try:
            bars = api.get_bars(
                symbol,
                tradeapi.rest.TimeFrame.Day,
                start=start,
                end=end,
                feed=feed
            ).df
            if bars is None or len(bars) == 0:
                continue
            bars.index = pd.to_datetime(bars.index)
            if isinstance(bars.columns, pd.MultiIndex):
                bars.columns = bars.columns.get_level_values(0)
            bars = bars[["open", "high", "low", "close", "volume"]]
            bars = bars.sort_index()
            if len(bars) >= 10:
                return bars
        except Exception as e:
            log(f"  {symbol}: Feed '{feed}' error — {e}")
            continue

    log(f"  {symbol}: Could not retrieve bars from any feed")
    return None


def place_buy_order(symbol, qty, stop_loss_price, reason):
    """Place a market buy order."""
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            type="market",
            time_in_force="day"
        )
        log(f"ORDER PLACED: BUY {qty} {symbol} — {reason}")
        alert_order_placed("BUY", qty, symbol, float(api.get_latest_trade(symbol).price), "Market")
        log_trade(
            symbol=symbol,
            side="BUY",
            qty=qty,
            entry_price=float(api.get_latest_trade(symbol).price),
            stop_loss=stop_loss_price,
            order_type="Market",
            reason=reason,
            notes="Placed by trading agent"
        )
        return order
    except Exception as e:
        log(f"ERROR placing buy order for {symbol}: {e}")
        return None


# Sentinel returned by place_sell_order when the broker reports the shares are
# already gone. Intentionally truthy so stop-exit callers still journal the
# close (the position IS closed — we just didn't place the fill ourselves).
SELL_ALREADY_CLOSED = "ALREADY_CLOSED"


def place_sell_order(symbol, qty, reason, price=None):
    """Place a market sell order.

    Returns:
        the order object on success;
        SELL_ALREADY_CLOSED if the broker says the shares are already gone
            (caller should still journal the close so no ghost 'Open' row is left);
        None on a genuine error (caller should leave the trade open and retry next cycle).
    """
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            type="market",
            time_in_force="day"
        )
        log(f"ORDER PLACED: SELL {qty} {symbol} — {reason}")
        if price is None:
            try:
                price = float(api.get_latest_trade(symbol).price)
            except Exception:
                price = 0.0
        alert_order_placed("SELL", qty, symbol, price, "Market")
        return order
    except Exception as e:
        err = str(e).lower()
        if "insufficient qty" in err or "available: 0" in err:
            log(f"[SELL SKIPPED] {symbol} — shares already sold (manual order or race condition)")
            return SELL_ALREADY_CLOSED
        else:
            log(f"ERROR placing sell order for {symbol}: {e}")
        return None


def is_market_open():
    """Check if the market is currently open."""
    try:
        clock = api.get_clock()
        return clock.is_open
    except Exception as e:
        log(f"ERROR checking market clock: {e}")
        return False


def can_re_enter(symbol):
    """Check if we're past the re-entry waiting period after a stop-out."""
    if symbol not in recent_stopouts:
        return True
    wait_until = recent_stopouts[symbol] + timedelta(days=RE_ENTRY_WAIT_DAYS)
    if datetime.now() >= wait_until:
        del recent_stopouts[symbol]
        return True
    log(f"  {symbol}: Re-entry blocked until {wait_until.strftime('%Y-%m-%d')}")
    return False


# ============================================================
# MORNING SCAN — runs at 9:35 AM
# ============================================================
def morning_scan():
    """Scan the watchlist for valid entry signals."""
    log("=" * 60)
    log("MORNING SCAN STARTED")
    log("=" * 60)
    orders_placed = []

    if not is_market_open():
        log("Market is closed — skipping scan")
        return

    account = get_account()
    if not account:
        return

    portfolio_value = float(account.portfolio_value)
    positions       = get_positions()
    symbols_held    = [p.symbol for p in positions]

    log(f"Portfolio value: ${portfolio_value:,.2f}")
    log(f"Current positions: {symbols_held if symbols_held else 'None'}")
    log(portfolio_risk_summary(positions, portfolio_value))

    # Check market conditions using SPY
    spy_bars = get_bars("SPY", limit=30)
    if not market_is_favorable(spy_bars):
        log("MARKET CONDITION: Bearish — no new entries today")
        from sms import send_sms
        send_sms("🔴 <b>MORNING SCAN</b>\nMarket bearish — no new entries today.\nExisting positions monitored.")
        log("MORNING SCAN COMPLETE")
        log("=" * 60)
        return
    else:
        log("MARKET CONDITION: Bullish — scanning for entries")

    log("-" * 60)

    # ── Phase 1: gather every candidate that passes entry conditions ──
    candidates = []
    for symbol in WATCHLIST:
        log(f"Scanning {symbol}...")

        # Skip if already holding this stock
        if symbol in symbols_held:
            log(f"  {symbol}: Already in portfolio — skip")
            continue

        # Skip if in re-entry waiting period
        if not can_re_enter(symbol):
            continue

        # Get historical data
        bars = get_bars(symbol, limit=60)

        # Check entry conditions
        should_enter, reason = check_entry_conditions(symbol, bars)
        if not should_enter:
            log(f"  {symbol}: No entry signal — {reason}")
            continue

        # Size the position now so 0-share names drop out before ranking
        current_price = float(bars.iloc[-1]["close"])
        shares, dollar_amount, stop_price, sizing_reason = calculate_position_size(
            symbol, portfolio_value, current_price
        )
        if shares <= 0:
            log(f"  {symbol}: ENTRY SIGNAL but position size is 0 — skip ({sizing_reason})")
            continue

        score, score_detail = compute_signal_strength(bars)
        log(f"  {symbol}: ENTRY SIGNAL — {score_detail} | {sizing_reason}")
        candidates.append({
            "symbol": symbol, "score": score, "current_price": current_price,
            "shares": shares, "dollar_amount": dollar_amount,
            "stop_price": stop_price, "reason": reason,
        })

    # ── Phase 2: rank by signal strength, keep the strongest, then buy ──
    candidates.sort(key=lambda c: c["score"], reverse=True)
    if len(candidates) > MAX_NEW_POSITIONS_PER_SCAN:
        deferred = candidates[MAX_NEW_POSITIONS_PER_SCAN:]
        log(f"RANKING: {len(candidates)} signals — taking top {MAX_NEW_POSITIONS_PER_SCAN} "
            f"by strength, deferring {len(deferred)}: "
            f"{', '.join(c['symbol'] + ' (' + str(c['score']) + ')' for c in deferred)}")
        candidates = candidates[:MAX_NEW_POSITIONS_PER_SCAN]
    else:
        log(f"RANKING: {len(candidates)} signal(s) — all within the "
            f"{MAX_NEW_POSITIONS_PER_SCAN}-per-scan cap")

    committed_this_scan = 0.0  # running $ tally of entries placed in THIS scan
    for c in candidates:
        symbol = c["symbol"]

        # Check total exposure — include $ already committed in this same scan
        # (positions list is fetched once and does NOT update mid-loop)
        ok, exposure_pct, exposure_msg = check_exposure(
            positions, portfolio_value, c["dollar_amount"] + committed_this_scan
        )
        log(f"  {symbol}: Exposure check — {exposure_msg}")
        if not ok:
            log(f"  {symbol}: Exposure limit reached — skip")
            continue

        # PLACE ORDER
        place_buy_order(symbol, c["shares"], c["stop_price"], c["reason"])
        committed_this_scan += c["dollar_amount"]  # count it against the exposure cap
        price_highs[symbol] = c["current_price"]
        entry_dates[symbol] = datetime.now().strftime("%Y-%m-%d")  # start the time-stop clock
        save_entry_dates()
        orders_placed.append(
            f"{symbol} {c['shares']} shares @ ~${c['current_price']:.2f} (rank {c['score']})"
        )

    # ── Send Telegram scan summary ──
    from sms import send_sms
    if orders_placed:
        msg = f"🟢 <b>MORNING SCAN</b>\nOrders placed:\n"
        msg += "\n".join([f"  • {o}" for o in orders_placed])
    else:
        msg = f"🔍 <b>MORNING SCAN COMPLETE</b>\nNo entry signals today.\nWatchlist: {', '.join(WATCHLIST)}"
    send_sms(msg)

    log("MORNING SCAN COMPLETE")
    log("=" * 60)


# ============================================================
# TRAILING STOP MONITOR — runs every 5 minutes
# ============================================================
def monitor_positions():
    """Check trailing stops and profit targets for all open positions."""
    try:
        if not is_market_open():
            return

        positions = get_positions()
        if not positions:
            return

        for position in positions:
            try:
                symbol        = position.symbol
                qty           = int(float(position.qty))
                entry_price   = float(position.avg_entry_price)
                current_price = float(position.current_price)

                # Update highest price seen since entry
                if symbol not in price_highs:
                    price_highs[symbol] = current_price
                else:
                    price_highs[symbol] = max(price_highs[symbol], current_price)
                highest_price = price_highs[symbol]

                gain_pct       = (current_price - entry_price) / entry_price * 100
                days_held      = trading_days_held(entry_dates.get(symbol))
                scaled_key     = f"{symbol}_scaled"
                already_scaled = bool(price_highs.get(scaled_key, False))
                hard_stop_pct  = get_stop_loss_pct(symbol)

                log(f"[MONITOR] {symbol}: Price=${current_price:.2f} | High=${highest_price:.2f} | "
                    f"P&L={gain_pct:+.1f}% | Held={days_held}d")

                decision = decide_exit(entry_price, current_price, highest_price,
                                       days_held, already_scaled, hard_stop_pct)
                action = decision["action"]

                # Don't re-trade a name we just stopped out this cycle
                if symbol in recent_stopouts and action != "sell_all":
                    continue

                # ── Full exit (protective stop or time stop) ──
                if action == "sell_all":
                    log(f"EXIT {symbol}: {decision['reason']} — selling {qty} shares at ${current_price:.2f}")
                    alert_stop_hit(symbol, current_price, decision["stop"])
                    order = place_sell_order(symbol, qty, decision["reason"], price=current_price)
                    if order:  # real fill OR the SELL_ALREADY_CLOSED sentinel (both truthy)
                        close_trade(symbol, current_price, decision["reason"])
                        recent_stopouts[symbol] = datetime.now()
                        _clear_position_state(symbol)
                        save_triggered_profits()
                        save_entry_dates()

                # ── Scale-out: bank half the pop, let the rest ride the trail ──
                elif action == "scale_out":
                    sell_qty = max(1, int(qty * SCALE_OUT_SIZE))
                    if sell_qty >= qty:          # never scale the whole position out
                        sell_qty = max(1, qty - 1)
                    log(f"SCALE-OUT {symbol}: {decision['reason']} — selling {sell_qty}/{qty} at ${current_price:.2f}")
                    alert_profit_target(symbol, sell_qty, int(SCALE_OUT_AT * 100))
                    order = place_sell_order(symbol, sell_qty, decision["reason"], price=current_price)
                    if order == SELL_ALREADY_CLOSED:
                        close_trade(symbol, current_price, "Position already closed at broker (reconciled)")
                        recent_stopouts[symbol] = datetime.now()
                        _clear_position_state(symbol)
                        save_triggered_profits()
                        save_entry_dates()
                    elif order:
                        log_partial_sell(symbol, sell_qty, entry_price, current_price, decision["reason"])
                        price_highs[scaled_key] = True   # one-time flag
                        save_triggered_profits()
                # else: action == "hold" — nothing to do

            except Exception as e:
                log(f"[MONITOR] ERROR processing {position.symbol}: {e}")

    except Exception as e:
        log(f"[MONITOR] ERROR in monitor_positions: {e}")


# ============================================================
# DAILY REPORT — runs at 4:05 PM
# ============================================================
def daily_report():
    """Generate end-of-day report."""
    log("\n" + "=" * 60)
    log("DAILY REPORT")
    log("=" * 60)

    account = get_account()
    if not account:
        return

    portfolio_value = float(account.portfolio_value)
    cash            = float(account.cash)
    equity          = float(account.equity)
    last_equity     = float(account.last_equity)
    pnl             = equity - last_equity
    pnl_pct         = (pnl / last_equity * 100) if last_equity > 0 else 0

    sign = "+" if pnl >= 0 else ""

    log(f"Portfolio Value : ${portfolio_value:,.2f}")
    log(f"Cash            : ${cash:,.2f}")
    log(f"Today's P&L     : {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%)")
    positions_for_sms = get_positions()
    alert_daily_report(portfolio_value, pnl, pnl_pct, positions_for_sms)
    log("-" * 60)

    positions = get_positions()
    if positions:
        log("OPEN POSITIONS:")
        for p in positions:
            pl      = float(p.unrealized_pl)
            pl_pct  = float(p.unrealized_plpc) * 100
            trail   = get_trailing_stop_pct(p.symbol) * 100
            highest = price_highs.get(p.symbol, float(p.current_price))
            stop    = highest * (1 - get_trailing_stop_pct(p.symbol))
            sign_p  = "+" if pl >= 0 else ""
            log(
                f"  {p.symbol}: {p.qty} shares | "
                f"Entry: ${float(p.avg_entry_price):.2f} | "
                f"Current: ${float(p.current_price):.2f} | "
                f"P&L: {sign_p}${pl:.2f} ({sign_p}{pl_pct:.1f}%) | "
                f"Trail stop: ${stop:.2f}"
            )
    else:
        log("No open positions")

    log("-" * 60)
    print_summary()
    log("=" * 60 + "\n")




# ============================================================
# HOURLY HEALTH CHECK
# ============================================================
def health_check():
    """Send hourly status update via Telegram during trading day."""
    try:
        # Run during market hours only (7 AM - 2 PM MT)
        now = datetime.now()
        if not (7 <= now.hour < 14):
            return

        account   = get_account()
        positions = get_positions()

        if not account:
            return

        portfolio_value = float(account.portfolio_value)
        pnl             = float(account.equity) - float(account.last_equity)
        sign            = "+" if pnl >= 0 else ""

        msg = f"⏰ <b>HOURLY CHECK</b> {datetime.now().strftime('%H:%M')} MT\n"
        msg += f"Portfolio: ${portfolio_value:,.2f} | P&L: {sign}${pnl:.2f}\n"

        if positions:
            for p in positions:
                cp        = float(p.current_price)
                ep        = float(p.avg_entry_price)
                pl        = float(p.unrealized_pl)
                pl_pct    = float(p.unrealized_plpc) * 100
                high      = price_highs.get(p.symbol, cp)
                trail_pct = get_trailing_stop_pct(p.symbol)
                stop      = high * (1 - trail_pct)
                buffer    = ((cp - stop) / cp) * 100
                sign_p    = "+" if pl >= 0 else ""
                icon      = "📈" if pl >= 0 else "📉"
                msg += f"{icon} {p.symbol}: ${cp:.2f} | {sign_p}${pl:.2f} ({sign_p}{pl_pct:.1f}%)\n"
                msg += f"   Stop: ${stop:.2f} | Buffer: {buffer:.1f}%\n"
        else:
            msg += "No open positions"

        from sms import send_sms
        send_sms(msg)
        log(f"[HEALTH CHECK] Sent hourly update")

    except Exception as e:
        log(f"[HEALTH CHECK] ERROR: {e}")
# ============================================================
# SCHEDULER SETUP
# ============================================================
def setup_schedule():
    """Set up the daily schedule."""
    schedule.every().monday.at(SCAN_TIME).do(morning_scan)
    schedule.every().tuesday.at(SCAN_TIME).do(morning_scan)
    schedule.every().wednesday.at(SCAN_TIME).do(morning_scan)
    schedule.every().thursday.at(SCAN_TIME).do(morning_scan)
    schedule.every().friday.at(SCAN_TIME).do(morning_scan)

    # Second scan at 8:30 AM MT when volume is more representative
    schedule.every().monday.at(SCAN_TIME_2).do(morning_scan)
    schedule.every().tuesday.at(SCAN_TIME_2).do(morning_scan)
    schedule.every().wednesday.at(SCAN_TIME_2).do(morning_scan)
    schedule.every().thursday.at(SCAN_TIME_2).do(morning_scan)
    schedule.every().friday.at(SCAN_TIME_2).do(morning_scan)

    schedule.every().monday.at(SCAN_TIME_EOD).do(morning_scan)
    schedule.every().tuesday.at(SCAN_TIME_EOD).do(morning_scan)
    schedule.every().wednesday.at(SCAN_TIME_EOD).do(morning_scan)
    schedule.every().thursday.at(SCAN_TIME_EOD).do(morning_scan)
    schedule.every().friday.at(SCAN_TIME_EOD).do(morning_scan)

    schedule.every(TRAILING_CHECK_MINS).minutes.do(monitor_positions)

    # Hourly health check during market hours
    schedule.every().hour.do(health_check)

    schedule.every().monday.at(REPORT_TIME).do(daily_report)
    schedule.every().tuesday.at(REPORT_TIME).do(daily_report)
    schedule.every().wednesday.at(REPORT_TIME).do(daily_report)
    schedule.every().thursday.at(REPORT_TIME).do(daily_report)
    schedule.every().friday.at(REPORT_TIME).do(daily_report)

    log(f"Schedule set — Scans: {SCAN_TIME} MT & {SCAN_TIME_2} MT & {SCAN_TIME_EOD} MT | Report: {REPORT_TIME} MT")
    log(f"Trailing stop monitor: every {TRAILING_CHECK_MINS} minutes")


# ============================================================
# MAIN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    log("=" * 60)
    log("ALPACA PAPER TRADING AGENT STARTED")
    log("Strategy: Trend Following + Trailing Stop")
    log("=" * 60)

    # Test connection
    account = get_account()
    if not account:
        log("FATAL: Cannot connect to Alpaca — check your API keys in config.py")
        exit(1)

    log(f"Connected to Alpaca — Account: {account.account_number}")
    log(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
    log(f"Buying Power   : ${float(account.buying_power):,.2f}")

    # Only send startup Telegram if within market hours
    now = datetime.now()
    is_weekday = now.weekday() < 5
    in_market_hours = 7 <= now.hour < 17
    if is_weekday and in_market_hours:
        alert_agent_started(float(account.portfolio_value))
    else:
        log("Outside market hours — skipping Telegram startup alert")
    log(f"Watchlist      : {WATCHLIST}")

    # Restore entry dates FIRST — restore_price_highs() needs them to clip the
    # high to the holding period. Self-heal any held position with no recorded
    # entry date (default to today so it gets a fresh window).
    load_entry_dates()
    for _p in (get_positions() or []):
        entry_dates.setdefault(_p.symbol, datetime.now().strftime("%Y-%m-%d"))
    save_entry_dates()

    # Restore highest-price-since-entry for each position
    restore_price_highs()
    # Restore triggered profit / scale-out flags from file
    load_triggered_profits()

    # Run initial account report
    log("\nRunning initial account report...")
    daily_report()

    # Run morning scan immediately if market is open and we are past scan time
    now = datetime.now()
    scan_hour, scan_min = map(int, SCAN_TIME.split(":"))
    report_hour, report_min = map(int, REPORT_TIME.split(":"))
    past_scan_time   = (now.hour, now.minute) >= (scan_hour, scan_min)
    before_close     = (now.hour, now.minute) < (report_hour, report_min)
    is_weekday       = now.weekday() < 5  # Monday=0 … Friday=4

    if is_market_open() and past_scan_time and before_close and is_weekday:
        log("\nMarket is open and past scan time — running morning scan now...")
        morning_scan()
    else:
        log("\nMorning scan will run at next scheduled time.")

    # Set up schedule
    setup_schedule()

    log("\nAgent is running. Press Ctrl+C to stop.\n")

    # Main loop — launchd handles start/stop scheduling
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)
        except KeyboardInterrupt:
            log("Agent stopped by user.")
            break
        except Exception as e:
            log(f"ERROR in main loop: {e}")
            time.sleep(60)
