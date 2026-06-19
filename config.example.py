# ============================================================
# config.example.py — Template configuration (safe to commit)
# ============================================================
#
# This is a TEMPLATE. The real config.py is gitignored because it is the
# project's secrets boundary. To set the project up from a fresh clone:
#
#   1.  cp config.example.py config.py
#   2.  Create a .env file (also gitignored) in this same folder with:
#
#         ALPACA_API_KEY=your_paper_api_key_here
#         ALPACA_SECRET_KEY=your_paper_secret_key_here
#         ALPACA_BASE_URL=https://paper-api.alpaca.markets
#         TELEGRAM_TOKEN=your_telegram_bot_token_here
#         TELEGRAM_CHAT_ID=your_telegram_chat_id_here
#
#   3.  Adjust the tunables below to taste. None of them are secret.
#
# No real keys live in this file — they are read from .env at runtime via
# os.getenv(), so this template exposes nothing.
# ============================================================
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Alpaca API Credentials (Paper Trading) — loaded from .env, never hard-coded
API_KEY    = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# ============================================================
# Risk Management Rules
# ============================================================
MAX_RISK_PER_TRADE    = 0.02   # Max 2% of portfolio per trade
MAX_POSITION_SIZE     = 0.10   # Max 10% of portfolio in one stock
MAX_TOTAL_EXPOSURE    = 0.80   # Max 80% of portfolio invested at once
MAX_EXPOSURE_CAUTIOUS = 0.50   # Max 50% when market is uncertain

# Cap on how many NEW positions a single scan may open.
# The scanner gathers every name that passes the entry filter, ranks them by
# compute_signal_strength() (momentum + volume confirmation + RSI headroom),
# then opens only the top N and defers the rest. This keeps one bullish day
# from spraying 20+ entries at once (which over-leverages the account and
# dilutes into marginal setups). Lower = more concentrated, higher = broader.
MAX_NEW_POSITIONS_PER_SCAN = 5

# Stop Loss Settings
STOP_LOSS_STABLE      = 0.05   # 5% stop loss for stable large-cap stocks
STOP_LOSS_VOLATILE    = 0.08   # 8% stop loss for volatile growth stocks
STOP_LOSS_ETF         = 0.04   # 4% stop loss for ETFs

# Trailing Stop Settings
TRAILING_STOP_STABLE  = 0.05   # 5% trailing stop for stable stocks
TRAILING_STOP_VOLATILE= 0.08   # 8% trailing stop for volatile stocks
TRAILING_STOP_ETF     = 0.04   # 4% trailing stop for ETFs

# Profit Taking Rules
PROFIT_TAKE_LEVEL_1   = 0.10   # Sell 25% of position at +10%
PROFIT_TAKE_LEVEL_2   = 0.20   # Sell another 25% at +20%
PROFIT_TAKE_SIZE      = 0.25   # Sell 25% at each profit level

# Trailing Stop Activation
TRAILING_ACTIVATE_AT  = 0.03   # Activate trailing stop after +3% gain

# ============================================================
# Entry Conditions
# ============================================================
RSI_MIN               = 55     # Minimum RSI for entry
RSI_MAX               = 70     # Maximum RSI for entry (avoid overbought)
RSI_OVERBOUGHT        = 75     # Hard overbought limit
VOLUME_MULTIPLIER     = 0.5    # Require at least half the normal average volume
MA_SHORT              = 20     # 20-day moving average
MA_LONG               = 50     # 50-day moving average

# ============================================================
# Market Risk Filters
# ============================================================
VIX_MAX               = 30     # Stop trading if VIX spikes above 30
MARKET_DROP_LIMIT     = 0.025  # Stop trading if market drops 2.5% in one day
RE_ENTRY_WAIT_DAYS    = 2      # Wait 2 days before re-entering same stock

# ============================================================
# Watchlist — Stocks to scan daily (edit freely; not sensitive)
# ============================================================
WATCHLIST = [
    # ── ETFs ──
    "SPY",    # S&P 500 ETF
    "QQQ",    # NASDAQ ETF

    # ── Mega-cap Tech ──
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # NVIDIA
    "AMD",    # AMD
    "GOOGL",  # Alphabet
    "META",   # Meta
    "AMZN",   # Amazon
    "TSLA",   # Tesla
    "ORCL",   # Oracle
    "CRM",    # Salesforce
    "ADBE",   # Adobe
    "NOW",    # ServiceNow
    "INTU",   # Intuit
    "CSCO",   # Cisco
    "IBM",    # IBM
    "TXN",    # Texas Instruments
    "QCOM",   # Qualcomm
    "ACN",    # Accenture

    # ── Semiconductors ──
    "MU",     # Micron Technology
    "AVGO",   # Broadcom
    "MRVL",   # Marvell Technology
    "TSM",    # Taiwan Semiconductor
    "LRCX",   # Lam Research
    "AMAT",   # Applied Materials
    "SMCI",   # Super Micro Computer
    "ARM",    # ARM Holdings

    # ── Financials ──
    "JPM",    # JPMorgan Chase
    "BAC",    # Bank of America
    "GS",     # Goldman Sachs
    "MS",     # Morgan Stanley
    "V",      # Visa
    "MA",     # Mastercard
    "AXP",    # American Express
    "BLK",    # BlackRock
    "SCHW",   # Charles Schwab
    "SPGI",   # S&P Global

    # ── Healthcare ──
    "LLY",    # Eli Lilly
    "UNH",    # UnitedHealth
    "JNJ",    # Johnson & Johnson
    "ABBV",   # AbbVie
    "MRK",    # Merck
    "TMO",    # Thermo Fisher
    "ABT",    # Abbott
    "DHR",    # Danaher
    "AMGN",   # Amgen
    "GILD",   # Gilead
    "ISRG",   # Intuitive Surgical
    "VRTX",   # Vertex Pharma
    "REGN",   # Regeneron
    "MDT",    # Medtronic
    "SYK",    # Stryker
    "BSX",    # Boston Scientific
    "ZTS",    # Zoetis
    "BMY",    # Bristol-Myers Squibb
    "PFE",    # Pfizer
    "CI",     # Cigna
    "ELV",    # Elevance Health

    # ── Consumer ──
    "HD",     # Home Depot
    "MCD",    # McDonald's
    "COST",   # Costco
    "WMT",    # Walmart
    "PG",     # Procter & Gamble
    "KO",     # Coca-Cola
    "PEP",    # PepsiCo
    "PM",     # Philip Morris
    "MO",     # Altria
    "LOW",    # Lowe's
    "BKNG",   # Booking Holdings
    "NFLX",   # Netflix
    "DIS",    # Walt Disney
    "TMUS",   # T-Mobile

    # ── Industrials & Energy ──
    "GE",     # GE Aerospace
    "CAT",    # Caterpillar
    "HON",    # Honeywell
    "RTX",    # Raytheon
    "UNP",    # Union Pacific
    "NSC",    # Norfolk Southern
    "FDX",    # FedEx
    "ETN",    # Eaton
    "ITW",    # Illinois Tool Works
    "EMR",    # Emerson Electric
    "DE",     # Deere & Co
    "XOM",    # ExxonMobil
    "CVX",    # Chevron
    "FCX",    # Freeport-McMoRan

    # ── Other S&P 100 ──
    "LIN",    # Linde
    "APD",    # Air Products
    "SHW",    # Sherwin-Williams
    "WM",     # Waste Management
    "PLD",    # Prologis
    "CME",    # CME Group
    "ICE",    # Intercontinental Exchange
    "AON",    # Aon
    "MMC",    # Marsh & McLennan
    "CB",     # Chubb
    "SO",     # Southern Company
    "DUK",    # Duke Energy
    "T",      # AT&T
]

# ============================================================
# Volatile Growth Stocks (use wider stops)
# ============================================================
VOLATILE_STOCKS = [
    "NVDA", "AMD", "META", "SMCI", "ARM", "MU", "MRVL",  # original
    "TSLA", "NFLX", "CRM", "NOW", "ADBE", "AMZN",        # high-beta tech
    "FCX", "REGN", "VRTX", "ISRG",                        # volatile growth
]

# ============================================================
# ETFs (use tighter stops)
# ============================================================
ETFS = ["SPY", "QQQ"]

# ============================================================
# Schedule (Mountain Time)
# ============================================================
SCAN_TIME             = "07:35"   # First scan 5 min after market open (MT)
SCAN_TIME_2           = "08:30"   # Second scan at 10:30 AM ET when volume is representative
SCAN_TIME_EOD         = "13:55"   # End-of-day scan 5 min before market close (MT = 3:55 PM ET)
REPORT_TIME           = "14:05"   # Generate daily report after market close (MT = 4:05 PM ET)
TRAILING_CHECK_MINS   = 5         # Check trailing stops every 5 minutes

# ============================================================
# Telegram Alerts
# ============================================================
SMS_ENABLED        = True
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
