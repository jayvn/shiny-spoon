#!/usr/bin/env python
"""
Option trades logging with comprehensive option data
"""

import csv
import datetime
from pathlib import Path

from ib_async import IB, Option

import telegram_bot as tg

# Global configuration
SEND_TELEGRAM_NOTIFICATIONS = True


def init_option_trades_csv(ticker: str):
    """Initialize option trades CSV with comprehensive columns"""
    trades_file = Path(f"output/option_trades_{ticker}.csv")
    trades_file.parent.mkdir(exist_ok=True)
    if not trades_file.exists():
        with trades_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "action",
                    "option_type",
                    "ticker",
                    "strike",
                    "expiry",
                    "right",
                    "price",
                    "quantity",
                    "delta",
                    "gamma",
                    "theta",
                    "vega",
                    "implied_volatility",
                    "time_to_expiry_days",
                    "underlying_price",
                    "intrinsic_value",
                    "time_value",
                    "pnl",
                    "cumulative_pnl",
                    "commission",
                    "contract_symbol",
                    "notes",
                ]
            )


def log_option_trade(
    ib: IB,
    action: str,
    option_contract: Option,
    trade_price: float,
    option_type: str = "",
    quantity: int = 1,
    pnl: float = 0.0,
    cumulative_pnl: float = 0.0,
    commission: float = 0.0,
    notes: str = "",
):
    """Log comprehensive option trade data from ib_async objects and send Telegram notification"""
    from ib_async import Stock

    ticker = option_contract.symbol
    trades_file = Path(f"output/option_trades_{ticker}.csv")

    # Get option Greeks and market data
    option_tickers = ib.reqTickers(option_contract)
    option_ticker = option_tickers[0] if option_tickers else None

    delta = gamma = theta = vega = implied_volatility = 0.0
    if option_ticker and option_ticker.modelGreeks:
        greeks = option_ticker.modelGreeks
        delta = greeks.delta or 0.0
        gamma = greeks.gamma or 0.0
        theta = greeks.theta or 0.0
        vega = greeks.vega or 0.0
        implied_volatility = (
            getattr(greeks, "impliedVol", getattr(greeks, "impliedVolatility", 0.0))
            or 0.0
        )

    # Get underlying price
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)
    stock_tickers = ib.reqTickers(stock)
    underlying_price = stock_tickers[0].marketPrice() if stock_tickers else 0.0

    # Clean up market data subscriptions
    for t in option_tickers + stock_tickers:
        if t.contract:
            ib.cancelMktData(t.contract)

    # Calculate derived values
    strike = option_contract.strike
    right = option_contract.right
    expiry = option_contract.lastTradeDateOrContractMonth

    intrinsic_value = (
        max(0, underlying_price - strike)
        if right == "C"
        else max(0, strike - underlying_price)
    )
    time_value = trade_price - intrinsic_value

    # Calculate time to expiry
    try:
        expiry_date = datetime.datetime.strptime(expiry, "%Y%m%d").date()
        today = datetime.date.today()
        time_to_expiry_days = (expiry_date - today).days
    except ValueError:
        time_to_expiry_days = 0

    # Generate contract symbol
    contract_symbol = f"{ticker} {expiry} {strike}{right}"

    # Write to CSV
    with trades_file.open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.datetime.now().isoformat(),
                action,
                option_type,
                ticker,
                strike,
                expiry,
                right,
                trade_price,
                quantity,
                round(delta, 4),
                round(gamma, 4),
                round(theta, 4),
                round(vega, 4),
                round(implied_volatility, 4),
                time_to_expiry_days,
                round(underlying_price, 2),
                round(intrinsic_value, 2),
                round(time_value, 2),
                pnl,
                cumulative_pnl,
                commission,
                contract_symbol,
                notes,
            ]
        )

    # Send Telegram notification if enabled
    if SEND_TELEGRAM_NOTIFICATIONS:
        alert_params = tg.format_trade_alert_params(delta, pnl, cumulative_pnl, notes)
        tg.send_trade_alert(
            f"{action} {option_type}",
            ticker,
            strike,
            expiry,
            trade_price,
            **alert_params,
        )



def get_last_option_trade(ticker: str) -> dict[str, str] | None:
    """Get the last option trade from CSV as a dictionary"""
    trades_file = Path(f"output/option_trades_{ticker}.csv")
    if not trades_file.exists():
        return None

    last = None
    with trades_file.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last = row

    return last if last else None


def get_option_trades_summary(ticker: str) -> dict[str, int | float | dict[str, int]]:
    """Get summary statistics from option trades"""
    trades_file = Path(f"output/option_trades_{ticker}.csv")
    if not trades_file.exists():
        return {}

    total_trades = 0
    total_pnl = 0.0
    total_commission = 0.0
    trades_by_type = {}

    with trades_file.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_trades += 1
            total_pnl += float(row.get("pnl", 0))
            total_commission += float(row.get("commission", 0))

            option_type = row.get("option_type", "")
            if option_type in trades_by_type:
                trades_by_type[option_type] += 1
            else:
                trades_by_type[option_type] = 1

    return {
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "total_commission": total_commission,
        "trades_by_type": trades_by_type,
        "net_pnl": total_pnl - total_commission,
    }
