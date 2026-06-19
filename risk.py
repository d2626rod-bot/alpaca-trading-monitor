# ============================================================
# risk.py — Position Sizing and Risk Management
# ============================================================

from config import (
    MAX_RISK_PER_TRADE, MAX_POSITION_SIZE, MAX_TOTAL_EXPOSURE,
    STOP_LOSS_STABLE, STOP_LOSS_VOLATILE, STOP_LOSS_ETF,
    VOLATILE_STOCKS, ETFS
)


def get_stop_loss_pct(symbol):
    """Return stop loss % based on stock type."""
    if symbol in ETFS:
        return STOP_LOSS_ETF
    elif symbol in VOLATILE_STOCKS:
        return STOP_LOSS_VOLATILE
    else:
        return STOP_LOSS_STABLE


def calculate_position_size(symbol, portfolio_value, entry_price):
    """
    Calculate how many shares to buy based on risk rules.

    Rules:
    - Never risk more than 2% of portfolio on one trade
    - Never allocate more than 10% of portfolio to one stock

    Returns: (int: shares, float: dollar_amount, float: stop_loss_price, str: reasoning)
    """
    if portfolio_value <= 0 or entry_price <= 0:
        return 0, 0, 0, "Invalid portfolio or price values"

    stop_loss_pct  = get_stop_loss_pct(symbol)
    stop_loss_price = entry_price * (1 - stop_loss_pct)

    # Max $ to risk = 2% of portfolio
    max_risk_dollars = portfolio_value * MAX_RISK_PER_TRADE

    # Risk per share = entry price - stop loss price
    risk_per_share = entry_price - stop_loss_price

    if risk_per_share <= 0:
        return 0, 0, 0, "Risk per share is zero or negative"

    # Shares based on risk
    shares_by_risk = int(max_risk_dollars / risk_per_share)

    # Shares based on max position size (10% of portfolio)
    max_position_dollars = portfolio_value * MAX_POSITION_SIZE
    shares_by_position   = int(max_position_dollars / entry_price)

    # Take the smaller of the two
    shares = min(shares_by_risk, shares_by_position)

    if shares <= 0:
        return 0, 0, 0, "Position size calculated as 0 shares — portfolio may be too small"

    dollar_amount = shares * entry_price

    reasoning = (
        f"Portfolio: ${portfolio_value:,.2f} | "
        f"Max risk (2%): ${max_risk_dollars:.2f} | "
        f"Stop loss: ${stop_loss_price:.2f} ({stop_loss_pct*100:.0f}% below entry) | "
        f"Risk/share: ${risk_per_share:.2f} | "
        f"Shares by risk: {shares_by_risk} | "
        f"Shares by position limit: {shares_by_position} | "
        f"Final shares: {shares} (${dollar_amount:.2f})"
    )

    return shares, dollar_amount, stop_loss_price, reasoning


def check_exposure(positions, portfolio_value, new_trade_value):
    """
    Check if adding a new trade would exceed max total exposure.
    Returns: (bool: ok_to_trade, float: current_exposure_pct, str: message)
    """
    if portfolio_value <= 0:
        return False, 0, "Portfolio value is zero"

    total_invested = sum(abs(float(p.market_value)) for p in positions)
    current_exposure = total_invested / portfolio_value
    new_exposure = (total_invested + new_trade_value) / portfolio_value

    if new_exposure > MAX_TOTAL_EXPOSURE:
        return False, current_exposure, (
            f"Trade would push exposure to {new_exposure*100:.1f}% "
            f"(max allowed: {MAX_TOTAL_EXPOSURE*100:.0f}%)"
        )

    return True, current_exposure, (
        f"Current exposure: {current_exposure*100:.1f}% | "
        f"After trade: {new_exposure*100:.1f}%"
    )


def portfolio_risk_summary(positions, portfolio_value):
    """Print a summary of current risk exposure."""
    if not positions:
        return "No open positions — 0% exposure"

    total_invested = sum(abs(float(p.market_value)) for p in positions)
    exposure_pct   = (total_invested / portfolio_value) * 100

    lines = [f"Total exposure: {exposure_pct:.1f}% of portfolio"]
    for p in positions:
        pos_pct = (abs(float(p.market_value)) / portfolio_value) * 100
        pl      = float(p.unrealized_pl)
        pl_pct  = float(p.unrealized_plpc) * 100
        sign    = "+" if pl >= 0 else ""
        lines.append(
            f"  {p.symbol}: {pos_pct:.1f}% of portfolio | "
            f"P&L: {sign}${pl:.2f} ({sign}{pl_pct:.1f}%)"
        )

    return "\n".join(lines)
