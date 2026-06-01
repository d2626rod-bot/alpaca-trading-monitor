# Alpaca Paper Trading — Project Status
**Last updated:** May 29, 2026 (Friday — week close, 3 bugs fixed, entry rules tightened)
**Student:** Daniel Rodriguez, Calgary Alberta (Mountain Time)

---

## 🎯 Project Goal
Learning to trade stocks using Alpaca paper trading (simulated money).
Goal: paper trade for 3 months before using real money.

---

## 🖥️ System Setup

### Hardware
- **Primary machine:** Apple Mac Mini (Apple Silicon M-series)
- **Backup:** Windows laptop (agent previously ran here)
- **Location:** Calgary, Alberta, Canada (Mountain Time — MT)

### Software
- **Python:** 3.14 (Mac, installed at `/Library/Frameworks/Python.framework/Versions/3.14/bin`)
- **Key libraries:** alpaca-trade-api, pandas, numpy, ta, schedule, openpyxl
- **Editor:** Terminal / nano (considering VS Code)
- **Notifications:** Telegram bot

### File Location (Mac)
**Location:** `~/alpaca_trading/` (NOT in `~/Documents` — macOS protects that folder from background processes)

```
~/alpaca_trading/
├── agent.py                       ← Main trading bot (Bug 1 fixed May 26)
├── agent.py.bak_20260526_0703     ← Pre-fix backup
├── config.py                      ← All settings and credentials
├── sms.py                         ← Telegram alert system
├── strategy.py                    ← Entry/exit rules
├── strategy.md                    ← Strategy documentation
├── reference_strategy_trailing.md ← Reference-only spec (NOT active), saved May 27

├── risk.py                        ← Position sizing and stop loss
├── risk_rules.md                  ← Risk rules documentation
├── journal.py                     ← Trade logging to Excel
├── journal.md                     ← Journal documentation
├── watchlist.md                   ← Watchlist documentation
├── README.md                      ← Setup instructions
├── PROJECT_STATUS.md              ← This file
├── PROJECT_STATUS.md.bak_*        ← Dated backups before rewrites
├── run_agent.sh                   ← Wrapper script for LaunchAgent (with -u flag)
├── run_agent.sh.bak               ← Backup before -u flag edit (May 25)
├── check_smci.py                  ← Diagnostic script for Alpaca order history
├── Alpaca_Mobile_Monitor.html     ← iPhone/browser monitor
├── Alpaca_Trading_Journal.xlsx    ← Excel trade journal
├── agent_output.log               ← stdout log (live output works since May 26)
├── agent_error.log                ← stderr log (truncated clean May 27)
├── agent_error.log.archive_*      ← Dated archives of old stderr logs
├── triggered_profits.json         ← Profit-taking state
└── __pycache__/                   ← Python cache
```

---

## 🔑 Credentials

**All credentials are stored in `~/alpaca_trading/config.py` on the Mac.**
Variable names used: `API_KEY`, `SECRET_KEY`, `BASE_URL`.

To view/edit credentials:
```bash
cat ~/alpaca_trading/config.py     # view
nano ~/alpaca_trading/config.py    # edit (or use sed for find/replace)
```

If credentials are ever lost, regenerate from:
- **Alpaca paper trading:** https://app.alpaca.markets (paper account dashboard → API keys)
- **Telegram bot:** message @BotFather on Telegram, use `/mybots`

**Account info (non-sensitive):**
- Alpaca Account ID: PA3EK1A1VPDA
- Telegram bot name: alpaca_d2626_bot
- Telegram phone: Bell Canada 403-383-7840

**⚠️ Credential security TODO:** The original API key/secret and Telegram bot token were shared in plain text in earlier PROJECT_STATUS.md versions. Before any push to GitHub (e.g. for iPhone monitor hosting):
1. Regenerate Alpaca API key/secret in dashboard
2. Regenerate Telegram bot token via @BotFather (`/revoke`)
3. Move credentials from `config.py` to `.env` + add `.env` to `.gitignore`

---

## ⏰ Agent Schedule (Mountain Time)

| Time MT | Event |
|---------|-------|
| 7:00 AM Mon-Fri | LaunchAgent starts agent |
| 7:35 AM | First morning scan |
| 8:30 AM | Second morning scan (added for better volume) |
| Every 5 min | Trailing stop monitor |
| Every hour | Health check Telegram |
| 2:05 PM | Daily report Telegram |
| 5:00 PM | Stop LaunchAgent |

---

## 📊 Trading Strategy

### Watchlist (16 stocks)
AAPL, MSFT, NVDA, AMD, GOOGL, META, SPY, QQQ,
MU, AVGO, MRVL, TSM, LRCX, AMAT, SMCI, ARM

### Entry Rules (ALL must pass)
1. Price above 20-day AND 50-day MA
2. Volume > 0.3x 20-day average (relaxed from 1.0x for IEX free feed)
3. RSI between 55 and 70
4. Uptrend confirmed (3-candle OR 5-candle higher highs/lows)
5. Market (SPY) bullish

### Stop Loss
- Volatile stocks (NVDA, AMD, META, SMCI, ARM, MU, MRVL): **8%**
- Stable stocks (AAPL, MSFT, GOOGL, AVGO, TSM, LRCX, AMAT): **5%**
- ETFs (SPY, QQQ): **4%**

### Trailing Stop
- Activates after **+3%** gain ← **ENFORCED IN CODE since May 26**
- Same % as stop loss per stock type
- Only moves UP — never down
- Restored correctly from 90-day history on restart

### Profit Taking
- **+10%** → sell 25% of position (fires ONCE per position — verified clean)
- **+20%** → sell another 25% (fires ONCE per position — **verified clean May 27**)
- State persisted in `triggered_profits.json` — survives LaunchAgent restart cycle

### Position Sizing
- Max risk per trade: **2% of portfolio**
- Max position size: **10% of portfolio**
- Max total exposure: **80%**

---

## 💰 Trade Activity

### May 27 — MU +20% profit-take fired cleanly ✅
| Time MT | Symbol | Action | Shares | Price | Trigger |
|---------|--------|--------|--------|-------|---------|
| 7:34 AM | MU | SELL | 1 | $929.78 | +22.4% — second profit-take (25% of 5, rounded). Position now at 4 shares. |

This is the **first +20% profit-take to fire in production**. Single trigger, no duplicates. Persistence in `triggered_profits.json` confirmed working across yesterday's 5 PM stop and today's 7 AM start.

### May 26 — Profit-takes fired correctly ✅
| Time MT | Symbol | Action | Shares | Price | Trigger |
|---------|--------|--------|--------|-------|---------|
| 7:33 AM | MRVL | SELL | 6 | $212.51 | +11.8% — first profit-take (25% of 26) |
| 7:56 AM | MU | SELL | 1 | $857.26 | +11.2% — first profit-take (25% of 6, rounded) |

Both sells: exactly 25% of position, single trigger per stock.

### May 26 pre-market snapshot (7:12 AM MT)
- Portfolio Value: $51,341.10
- Today's P&L: +$1,083.67 (+2.16%)
- All 6 positions green

---

## 🔧 Mac Auto-Start Setup (LaunchAgent)

### LaunchAgent files
```
~/Library/LaunchAgents/com.danielrodriguez.alpacatrading.plist
~/Library/LaunchAgents/com.danielrodriguez.alpacatrading.stop.plist
```

The plist calls `~/alpaca_trading/run_agent.sh`, which:
1. Sets PATH to find Python 3.14
2. cd's to `~/alpaca_trading`
3. Runs `python3 -u agent.py` with stdout → agent_output.log, stderr → agent_error.log

### Key commands
```bash
# Check if running (should show bash wrapper + python child)
pgrep -lf agent.py
launchctl list | grep alpaca

# Start / stop
launchctl start com.danielrodriguez.alpacatrading
launchctl stop com.danielrodriguez.alpacatrading

# Reload after editing plist
launchctl unload ~/Library/LaunchAgents/com.danielrodriguez.alpacatrading.plist
launchctl load ~/Library/LaunchAgents/com.danielrodriguez.alpacatrading.plist

# Watch log file live (works now thanks to -u flag)
tail -f ~/alpaca_trading/agent_output.log
```

### Restart after code changes (standard recipe)
```bash
# Backup first
cp ~/alpaca_trading/agent.py ~/alpaca_trading/agent.py.bak_$(date +%Y%m%d_%H%M)

# Make edits with sed (or nano)

# Verify syntax before restart
cd ~/alpaca_trading
python3 -c "import ast; ast.parse(open('agent.py').read()); print('Syntax OK')"

# Restart
launchctl stop com.danielrodriguez.alpacatrading
sleep 5
launchctl start com.danielrodriguez.alpacatrading
sleep 8
pgrep -lf agent.py
```

### Truncate the live error log safely (keeps inode, no agent restart needed)
```bash
# Archive first
cp ~/alpaca_trading/agent_error.log ~/alpaca_trading/agent_error.log.archive_$(date +%Y%m%d)
# Truncate in place — the running agent's stderr stream stays connected
: > ~/alpaca_trading/agent_error.log
```

### Diagnostic: query Alpaca for trade history
```bash
cd ~/alpaca_trading
python3 check_smci.py    # Adapt symbol filter as needed
```

---

## ✅ Recent Wins

### Week of May 26–29 — Summary

**Portfolio: $51,341 → $52,309 | +$968 (+1.89%) in 4 trading days**

| Day | P&L | Key Event |
|-----|-----|-----------|
| Mon May 26 | +$1,967 | MRVL and MU profit-takes fired; big SMCI/MU run |
| Tue May 27 | -$160 | MRVL trailing stop exit; GOOGL + TSM entries |
| Wed May 28 | +$392 | SMCI +20% profit-take; credential rotation done |
| Thu May 29 | +$196 | GOOGL manually exited (stop bug); MSFT entered |

**Trades:**
- 💰 MRVL +10% partial sell
- 💰 MU +10% partial sell
- 💰 MU +20% partial sell
- 💰 MRVL trailing stop exit (+$185)
- 💰 SMCI +20% partial sell
- 🔴 GOOGL manual exit (-$135, trailing stop bug)
- 🟢 GOOGL entry (May 27)
- 🟢 TSM entry (May 27)
- 🟢 MSFT entry (May 29)

**Open positions at week close:**
SMCI (+42.3%), MU (+25.2%), MSFT (+1.6%), AMAT (+3.7%), LRCX (+3.6%), SPY (+1.2%), TSM (-0.5%)

**Bugs fixed this week (4):**
1. Trailing stop blind spot — hard stop added for positions that never reach +3%
2. Sell Telegram alert showing $0.00 — SIP feed exception now isolated
3. Entry MA20 buffer — price must be 2%+ above MA20 (caught GOOGL weakness in hindsight)
4. Volume floor raised 0.3× → 0.5× to filter weak-volume days

**Lessons learned:**
- Strong runners (MU +25%, SMCI +42%) do the heavy lifting — protect them
- A stock just touching MA20 has no real momentum — needs a buffer
- The trailing stop +3% gate had a dangerous side effect for losing positions
- Credentials in plain text are a real risk — `.env` is the right home
- Every bug costs simulated money — cheap lessons before real money

---

### May 28 — Credential rotation + GitHub Pages + bug fix

**Fixes made (take effect at 7 AM restart May 29):**

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `agent.py` | Sell alert showed `$0.00` — SIP feed exception caused `place_sell_order` to return `None`, skipping journal too | Wrapped `get_latest_trade` in its own try/except; both profit-take and trailing-stop calls now pass `current_price` directly |

**Credential rotation completed:**
- Alpaca API key regenerated — old key invalidated
- Telegram bot token regenerated via @BotFather — old token invalidated
- Both credentials moved from `config.py` (plain text) to `.env` (git-ignored)
- `config.py` now reads credentials via `python-dotenv`
- `.gitignore` created — blocks `.env`, `config.py`, logs, backups from GitHub

**GitHub Pages live:**
- Repo: https://github.com/d2626rod-bot/alpaca-trading-monitor
- iPhone monitor URL: https://d2626rod-bot.github.io/alpaca-trading-monitor/Alpaca_Mobile_Monitor.html
- Monitor HTML updated with new Alpaca API credentials before push

**Backups created:**
- `config.py.bak_20260528_*` — pre-credential-rotation backup
- `Alpaca_Mobile_Monitor.html.bak_20260528_*` — pre-credential-update backup
- `agent.py.bak_20260528_*` — pre-sell-fix backup

### May 27 (evening) — Code review session: 4 bugs fixed

**Fixes made (all take effect at 7 AM restart tomorrow):**

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `journal.py` | Partial sells (profit-takes) never logged to Excel — only BUY rows appeared | Added `log_partial_sell()` function; called from `agent.py` after every successful profit-take order |
| 2 | `agent.py` | Sell order Telegram alert showed `$0.00` price (hardcoded `0` instead of live price) | Changed to `api.get_latest_trade(symbol).price` — matches what the BUY alert already did |
| 3 | `strategy.py` | Uptrend check used `or` — a stock with rising highs but flat/declining lows would pass | Changed to `(hh3 and hl3) or (hh5 and hl5)` — now requires higher highs AND higher lows |
| 4 | `risk.py` | `MAX_TOTAL_EXPOSURE` defined in config but hardcoded `0.80` used in `check_exposure()` | Imported `MAX_TOTAL_EXPOSURE` from config; used in comparison and log message |

**Backups created before each change:**
- `agent.py.bak_20260527_1903` — pre-fix backup
- `journal.py.bak_20260527_1903` — pre-fix backup
- `strategy.py.bak_20260527_1912` — pre-fix backup
- `risk.py.bak_20260527_1912` — pre-fix backup

**Impact of fix #3 (uptrend check):** Tomorrow's 7:35 AM scan will be stricter — may see more "No clear uptrend" rejections. This is correct behavior; the old logic was too lenient.

---

### May 27 (morning) — First +20% profit-take fired cleanly + system health verified
**Trade:** MU at +22.4% triggered the +20% tier at 7:34 AM MT. Sold 1 share at $929.78. Single fire, recorded in `triggered_profits.json` as `MU_profit_20: true`.

**Health check confirmed:**
- Agent alive, PID 21156, running `python3 -u agent.py`
- 7:35 AM scan: all 16 watchlist stocks evaluated in 6 seconds, market bullish
- Monitor ticks every 5 minutes, all 6 positions tracked correctly
- Zero stderr entries since May 24 18:25 — three full days of clean execution
- `triggered_profits.json` state: `SMCI_profit_10`, `MRVL_profit_10`, `MU_profit_10`, `MU_profit_20` all `true` — persistence across LaunchAgent restart cycle verified

**Maintenance done:** archived stale `agent_error.log` (897 KB of pre-May-24 errors from the old `~/Documents/` path) to `agent_error.log.archive_20260527`, truncated live log to 0 lines for fresh signal.

**This means three profit-takes in 24 hours have all fired exactly once each** (MRVL +10%, MU +10%, MU +20%) — Bug 2 (repeated profit-takes) is conclusively dead.

### May 26 — Bug 1 FIXED: Trailing stop now respects +3% activation threshold
**Problem:** `agent.py monitor_positions()` ignored the `TRAILING_ACTIVATE_AT` config setting. The strategy doc said "trailing stop activates after +3% gain" but the code fired the trailing stop immediately when `current_price <= highest_price × (1 - trail_pct)`. This caused NVDA to exit prematurely on May 21 at -1.16% loss.

**Root cause:** `strategy.py` has a proper `check_trailing_stop()` function that DOES check the +3% threshold, but `agent.py` never calls it — it reimplements the check inline without the gate.

**Fix:**
1. Added `TRAILING_ACTIVATE_AT` to imports in agent.py line 29
2. Changed line 398 to require `gain_pct >= TRAILING_ACTIVATE_AT * 100` before firing trailing stop
3. Verified syntax → restarted agent → Telegram "🤖 Agent started" confirmed

**Backup:** `agent.py.bak_20260526_0703` saved before edits.

### May 26 — Bug 2 confirmed RESOLVED (from prior session)
**Background:** On May 22, SMCI sold down from 153 → 38 shares in 5 separate profit-take sells over 2 hours. Investigation via Alpaca API confirmed:

| Time MT | Sell Qty | Remaining | % of remaining |
|---------|----------|-----------|----------------|
| 11:09 AM | 38 | 115 | 25% of 153 |
| 11:49 AM | 28 | 87  | 25% of 115 |
| 12:47 PM | 21 | 66  | 25% of 87 |
| 12:52 PM | 16 | 50  | 25% of 66 |
| 1:02 PM  | 12 | 38  | 25% of 50 |

The +10% profit-take re-fired 5 times instead of once — likely due to agent restarts that day (this was BEFORE the May 24 LaunchAgent error 78 fix). On each restart, the trigger state was lost or reset, and the next monitor tick re-triggered.

**Resolution:** This bug was identified and patched in a previous Claude session. May 26 (MRVL, MU at +10%) and May 27 (MU at +20%) profit-takes each fired only once — confirming the fix works for both tiers.

### May 25 — Cleanup session
- Removed leftover plist files (`.save` backup, Downloads copy, Trash copy)
- Deleted old `~/Documents/Claude_Project/Alpaca_Trading/` folder
- Added `-u` flag to `run_agent.sh` for unbuffered Python logging
- Live logging confirmed working May 26 morning

### May 24 — LaunchAgent error 78 SOLVED
**Root cause:** macOS protects `~/Documents`, `~/Desktop`, `~/Downloads` from background processes.
**Fix:** Moved all project files to `~/alpaca_trading/`, updated `run_agent.sh` and plist with `sed`.

---

## 🐛 Open Issues

### Active
- **Journal partial sell not yet verified in production** — `log_partial_sell()` was added May 27 PM. Will confirm on next profit-take — look for `[JOURNAL] Partial sell logged:` in agent_output.log.

### Theoretical / lower priority
- **`price_highs[symbol]` initialization audit** — when a new position is observed for the first time, `price_highs[symbol]` is set to the current price. If a stock dips immediately after purchase, this locks in a low reference. The +3% activation threshold mitigates this but initialization could use entry price as the floor.
- **VIX / market drop filter not wired up** — `VIX_MAX = 30` and `MARKET_DROP_LIMIT = 0.025` defined in `config.py` but agent never queries VIX. Needs Alpaca VIX data feed.
- **IEX feed limitation** — free Alpaca account only gets IEX data (2-3% of real market volume) — volume threshold at 0.5x to compensate.
- **Profit-take tiers for strong runners** — revisit in week of Jun 1: consider wider tiers (+20%/+40%) for explosive movers like MU and SMCI vs. keeping +10%/+20% for moderate stocks. Deferred pending real exit data.
- **Considering VS Code** for easier file editing

---

## 📚 Key Lessons Learned

1. Never average up — second AMD buy at $459 hurt the average entry
2. Trust the trailing stop — but verify it's coded correctly first ⚠️
3. Volume at market open (9:30-9:45 AM ET) is only 3-5% of daily average — scan at 10:30 AM ET (8:30 AM MT) gives much better signals
4. IEX free feed shows lower volume than real market — account for this in strategy
5. Paper trading teaches real lessons — bugs cost simulated money, real learning
6. **macOS protects `~/Documents`, `~/Desktop`, `~/Downloads` from background processes** — put project folders directly in `~/` for LaunchAgents
7. **`sed -i ''` is much easier than nano** for find/replace in config files on Mac (the empty `''` is required on macOS)
8. **Credentials don't belong in documentation files** — keep them in config.py only
9. **Python stdout buffering hides output when redirected to files** — always use `python3 -u` in production/background scripts
10. **When fixing paths in LaunchAgents, also check for orphan copies** in Downloads, Trash, and `.save` backups
11. **Strategy docs ≠ code reality** — May 26 trailing stop bug shows that just because a config value exists doesn't mean it's enforced. Always trace the path from config → strategy → agent to confirm a rule actually fires.
12. **Don't react to Friday losers** — MU went from -2.6% Friday close to +5.6% Tuesday pre-market without intervention. Continued up to +22.4% by Wednesday — a +25% swing in 3 trading days.
13. **Always back up before editing live trading code** — `cp agent.py agent.py.bak_$(date +%Y%m%d_%H%M)` takes 1 second and saves the day if syntax breaks.
14. **Verify Python syntax after sed edits** — `python3 -c "import ast; ast.parse(open('agent.py').read())"` catches errors before restart.
15. **When investigating bugs, query the source of truth directly** — Alpaca's order history API revealed the SMCI mystery in seconds; the Excel journal had a logging gap and the phone app only showed recent 8 entries.
16. **Heredocs (`<< 'EOF' ... EOF`) can hang the shell** if the closing EOF gets lost in paste. Press Ctrl+C to escape; for big scripts, write to a file first (`cat > script.py << 'EOF'`) then `python3 script.py`.
17. **Local Python imports need the working directory** — `python3 /tmp/script.py` won't find `config.py` in `~/alpaca_trading/`. Put scripts in the project folder OR cd there first.
18. **`triggered_profits.json` is the single source of truth for profit-take state** — verified May 27 that the JSON survives the LaunchAgent stop/start cycle, which is what kills the repeat-fire bug. If you ever wonder whether a tier has fired, `cat triggered_profits.json` answers in 1 second.
19. **Truncate logs with `: > file`, not `rm`** — the redirection preserves the file's inode and the running agent's stderr stream stays connected. `rm` would force a restart.
20. **Stale error logs hide real signal** — 897 KB of dead errors from the old `~/Documents/` path made it harder to spot new problems. Archive + truncate periodically.

---

## 🔄 Version History (Key Changes)

| Version | Change |
|---------|--------|
| v1 | Initial build — basic order placer |
| v3 | Fixed historical data fetch |
| v4 | Fixed journal title row bug |
| v5 | Fixed trailing stop resetting on restart |
| v6 | Lowered volume multiplier for IEX feed |
| v7-v8 | Added Telegram alerts (replaced failed Bell/Telus SMS) |
| v8b | Fixed trailing stop monitor silent failures |
| v8c | Added hourly health check |
| v9 | Added morning scan Telegram summary |
| v10 | Fixed all times to Mountain Time |
| v11 | Migrated to Mac Mini |
| v12 | Expanded watchlist to 16 stocks |
| v13 | Added second scan at 8:30 AM MT |
| v14 | Relaxed uptrend check to 3-candle OR 5-candle |
| v15 | Lowered volume threshold to 0.3x |
| v16 (May 24) | Moved project to `~/alpaca_trading/` to fix LaunchAgent error 78 |
| v17 (May 25) | Cleanup: removed orphan files, added `-u` flag for unbuffered logging |
| v18 (May 26 AM) | Bug 1 fix: trailing stop now requires +3% gain before firing |
| v19 (May 26 PM) | Bug 2 confirmed resolved (from prior session); both profit-takes fired cleanly |
| v20 (May 27 AM) | First +20% profit-take fires cleanly in production (MU at $929.78); error log archived and truncated; persistence across restart cycle verified |
| v21 (May 27 PM) | Bug fix: partial sell journal logging added (`log_partial_sell()` in journal.py) |
| v22 (May 27 PM) | Bug fix: sell order Telegram alert price was $0.00 — now uses live price |
| v23 (May 27 PM) | Bug fix: uptrend check logic tightened — now requires HH AND HL, not HH OR HL |
| v24 (May 27 PM) | Bug fix: `MAX_TOTAL_EXPOSURE` now imported and used in `risk.py` instead of hardcoded 0.80 |
| v25 (May 28) | Bug fix: sell alert `$0.00` price — SIP feed exception now isolated so order return value and journal call are unaffected |
| v26 (May 28) | Security: credentials rotated, moved to `.env`, `config.py` reads via python-dotenv, `.gitignore` created |
| v27 (May 28) | Feature: GitHub Pages live — iPhone monitor hosted at d2626rod-bot.github.io |
| v28 (May 29) | Bug fix: hard stop loss added — positions that never reach +3% gain now exit correctly |
| v29 (May 29) | Entry rule tightened: price must be 2%+ above MA20 (was just above) |
| v30 (May 29) | Entry rule tightened: volume floor raised from 0.3× to 0.5× average |

---

## 🚀 Next Steps

### Week of Jun 1
1. **Verify journal partial sell** — watch for `[JOURNAL] Partial sell logged:` on next profit-take
2. **Monitor MU and SMCI exits** — track final P&L when they eventually stop out; use data to decide on profit-take tier strategy (hold longer vs. partial sells)
3. **Watch TSM** — slightly underwater at -0.5%, stop at $408.94. Could exit early next week
4. Continue paper trading toward 3-month goal

### Later
5. Audit `price_highs[symbol]` initialization (theoretical bug)
6. Wire up VIX filter — `VIX_MAX = 30` already in config, needs data feed query in `morning_scan()`
7. Get friends' stock suggestions for watchlist expansion
8. Consider VS Code for easier file editing

---

## 💬 For the Next Claude Session

**Quick context:**
- Daniel is paper trading on Alpaca, learning before real money
- Project lives at `~/alpaca_trading/` (NOT in Documents — that broke LaunchAgent with error 78)
- LaunchAgent auto-starts at 7 AM MT, stops at 5 PM MT daily
- Week of May 26–29 complete: +$968 (+1.89%), 4 bugs fixed, entry rules tightened

**System status (May 29 close):**
- Agent: healthy, PID changes daily at 7 AM restart
- Credentials: rotated, stored in `.env`, `config.py` reads via python-dotenv ✅
- GitHub Pages live: https://d2626rod-bot.github.io/alpaca-trading-monitor/Alpaca_Mobile_Monitor.html
- `.gitignore` protects `.env` and `config.py` ✅

**Open positions at May 29 close:**
| Symbol | P&L | Trail Stop | Watch |
|--------|-----|-----------|-------|
| SMCI | +42.3% | $44.45 | 🔥 |
| MU | +25.2% | $901.85 | 🔥 |
| MSFT | +1.6% | $423.32 | New entry |
| AMAT | +3.7% | $438.27 | Healthy |
| LRCX | +3.6% | $316.35 | Healthy |
| SPY | +1.2% | $727.74 | Steady |
| TSM | -0.5% | $408.94 | ⚠️ Watch |

**Active profit-take state** (`triggered_profits.json`):
`SMCI_profit_10`, `SMCI_profit_20`, `MU_profit_10`, `MU_profit_20` — all true

**What to watch week of Jun 1:**
1. Verify `[JOURNAL] Partial sell logged:` fires on next profit-take
2. TSM at -0.5% — could stop out early in the week
3. MU and SMCI — track final exit prices for profit-take strategy review (deferred to Jun 1 week)
4. Sell Telegram alerts should now show real prices (fix applied May 28, first test pending)

**Entry rules as of May 29:**
- Price must be **2%+ above MA20** (raised from just above)
- Volume must be **0.5×** average (raised from 0.3×)
- RSI between 55–70
- 3-candle OR 5-candle higher highs AND higher lows
- Market bullish (SPY above MA20)

**Backups available:**
- `~/alpaca_trading/agent.py.bak_20260529_*` (pre-hard-stop fix)
- `~/alpaca_trading/strategy.py.bak_20260529_*` (pre-MA20-buffer fix)
- `~/alpaca_trading/config.py.bak_20260529_*` (pre-volume fix)
- `~/alpaca_trading/agent.py.bak_20260528_*`
- `~/alpaca_trading/config.py.bak_20260528_*` (contains OLD rotated keys — do not use)

**Diagnostic tools:**
- `tail -f ~/alpaca_trading/agent_output.log` — live log
- `cat ~/alpaca_trading/triggered_profits.json` — profit-take state
- `~/alpaca_trading/check_smci.py` — Alpaca order history query

**Daniel's preferences:**
- Patient step-by-step Terminal guidance (he's learning)
- Prefers `sed` over `nano` for config edits (nano Ctrl+\ shortcut doesn't work on his Mac)
- All times in Mountain Time (Calgary)
- Telegram is the primary monitoring channel
- One step at a time; backup before destructive changes; verify syntax before restart
- Bilingual — comfortable in English and Spanish
