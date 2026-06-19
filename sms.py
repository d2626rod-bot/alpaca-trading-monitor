# ============================================================
# sms.py — Telegram Alert System for Alpaca Trading Agent
# ============================================================

import urllib.request
import urllib.parse
import json
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SMS_ENABLED


def send_sms(message):
    """
    Send a Telegram message to your iPhone.
    """
    if not SMS_ENABLED:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read())
            if result.get("ok"):
                print(f"[TELEGRAM] Sent: {message}")
            else:
                print(f"[TELEGRAM] Failed: {result}")

    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")


# ============================================================
# Pre-built alert messages
# ============================================================

def alert_order_placed(side, qty, symbol, price, order_type):
    icon = "🟢" if side.upper() == "BUY" else "🔴"
    send_sms(f"{icon} <b>ORDER:</b> {side.upper()} {qty} {symbol} @ ${price:.2f} ({order_type})")


def alert_stop_hit(symbol, current_price, stop_price):
    send_sms(f"🛑 <b>STOP HIT:</b> {symbol} sold @ ${current_price:.2f}\nStop was ${stop_price:.2f}")


def alert_profit_target(symbol, qty_sold, gain_pct):
    send_sms(f"💰 <b>PROFIT TARGET:</b> Sold {qty_sold} {symbol} at +{gain_pct:.0f}%")


def alert_daily_report(portfolio_value, pnl, pnl_pct, positions):
    sign = "+" if pnl >= 0 else ""
    icon = "📈" if pnl >= 0 else "📉"
    msg  = f"{icon} <b>DAILY REPORT</b>\n"
    msg += f"Portfolio: ${portfolio_value:,.2f}\n"
    msg += f"P&amp;L: {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)\n"
    if positions:
        msg += "\n<b>Positions:</b>\n"
        for p in positions:
            pl     = float(p.unrealized_pl)
            pl_pct = float(p.unrealized_plpc) * 100
            sign_p = "+" if pl >= 0 else ""
            msg += f"  {p.symbol}: {sign_p}${pl:.2f} ({sign_p}{pl_pct:.1f}%)\n"
    send_sms(msg)


def alert_agent_started(portfolio_value):
    send_sms(f"🤖 <b>Alpaca Agent Started</b>\nPortfolio: ${portfolio_value:,.2f}\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")


def alert_trailing_stop_update(symbol, new_stop, gain_pct):
    send_sms(f"📊 <b>{symbol}</b> Trail stop → ${new_stop:.2f} | Gain: +{gain_pct:.1f}%")
