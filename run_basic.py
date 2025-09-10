#!/usr/bin/env python
"""
Simple paper-trading option strategy.
Buys ATM calls when no position, sells when position exists.
Logs trades to CSV with timestamps and P&L.
"""

import csv
import datetime
import sys
from pathlib import Path

from ib_async import IB, MarketOrder, Option, Stock

import log_n_notify

# Configuration
PORT = 4002
CLIENT_ID = 0  # Using 0 allows auto-incrementing if connection exists
TICKER = "SPY"
DTE_DAYS = 1


def init_csv(ticker: str):
    """Initialize CSV file if it doesn't exist"""
    trades_file = Path(f"output/trades_{ticker}.csv")
    trades_file.parent.mkdir(exist_ok=True)
    if not trades_file.exists():
        with trades_file.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "action",
                    "ticker",
                    "strike",
                    "expiry",
                    "price",
                    "pnl",
                ]
            )


def last_trade(ticker: str):
    """Return last trade row as dict or None"""
    return log_n_notify.get_last_option_trade(ticker)


def get_atm_option(ib: IB, ticker: str, dte_days: int, right: str = "C") -> Option:
    """Get at-the-money option with target DTE"""
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)

    tickers = ib.reqTickers(stock)
    current_price = tickers[0].marketPrice()
    strike = round(current_price)

    # Cancel market data subscription to avoid lingering connections
    for ticker_obj in tickers:
        if ticker_obj.contract:
            ib.cancelMktData(ticker_obj.contract)

    target_date = datetime.date.today() + datetime.timedelta(days=dte_days)
    chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)

    expirations: list[str] = []
    for chain in chains:
        expirations.extend(chain.expirations)
    expirations = sorted(set(expirations))
    closest_expiry = min(
        expirations,
        key=lambda x: abs(datetime.datetime.strptime(x, "%Y%m%d").date() - target_date),
    )

    option = Option(ticker, closest_expiry, strike, right, "SMART")
    qualified = ib.qualifyContracts(option)
    if qualified and isinstance(qualified[0], Option):
        return qualified[0]
    raise ValueError(f"Failed to qualify option contract for {ticker}")


def buy_option(ib: IB, ticker: str, dte_days: int) -> bool:
    """Buy a single option contract"""
    option = get_atm_option(ib, ticker, dte_days, "C")
    order = MarketOrder("BUY", 1)
    trade = ib.placeOrder(option, order)

    while not trade.isDone():
        ib.sleep(1)

    fill_price = trade.orderStatus.avgFillPrice
    print(f"Bought {ticker} {option.strike} Call @ ${fill_price:.2f}")

    # Log to comprehensive option trades CSV
    log_n_notify.log_option_trade(
        ib=ib,
        action="BUY",
        option_contract=option,
        trade_price=fill_price,
        option_type="CALL",
        notes="ATM call purchase",
    )

    return True


def sell_option(
    ib: IB, ticker: str, strike: float, expiry: str, entry_price: float
) -> bool:
    """Sell the current option position reconstructed from CSV"""
    option = Option(ticker, expiry, strike, "C", "SMART")
    contract = ib.qualifyContracts(option)[0]

    order = MarketOrder("SELL", 1)
    trade = ib.placeOrder(contract, order)

    while not trade.isDone():
        ib.sleep(1)

    exit_price = trade.orderStatus.avgFillPrice
    pnl = (exit_price - entry_price) * 100

    print(f"Sold {ticker} {contract.strike} Call @ ${exit_price:.2f}")
    print(f"P&L: ${pnl:.2f}")

    # Log to comprehensive option trades CSV
    log_n_notify.log_option_trade(
        ib=ib,
        action="SELL",
        option_contract=contract,
        trade_price=exit_price,
        option_type="CALL",
        pnl=pnl,
        notes="Closing ATM call position",
    )

    return True


def display_position(ib: IB, ticker: str):
    """Display current position"""
    print("\n" + "=" * 50)
    print(f"POSITION STATUS - {ticker}")
    print("=" * 50)

    last = last_trade(ticker)
    if last and last["action"] == "BUY":
        print(f"Position: LONG {last['strike']} Call")
        print(f"Entry Price: ${last['price']:.2f}")
        print(f"Entry Time: {last['timestamp']}")
        print(f"Expiry: {last['expiry']}")
        option = Option(
            ticker, str(last["expiry"]), float(last["strike"]), "C", "SMART"
        )
        contract = ib.qualifyContracts(option)[0]
        tickers = ib.reqTickers(contract)
        current_price = tickers[0].marketPrice()
        pnl = (current_price - float(last["price"])) * 100
        print(f"Current Price: ${current_price:.2f}")
        print(f"Unrealized P&L: ${pnl:.2f}")

        # Cancel market data subscription
        for ticker_obj in tickers:
            if ticker_obj.contract:
                ib.cancelMktData(ticker_obj.contract)
    else:
        print("No active position")

    print("=" * 50 + "\n")


def run_daily(ib: IB, ticker: str, dte_days: int):
    """Run daily trading logic"""
    print(f"=== Daily Run for {ticker} ===")

    last = last_trade(ticker)
    if last and last["action"] == "BUY":
        print("Have position - selling")
        sell_option(
            ib, ticker, float(last["strike"]), str(last["expiry"]), float(last["price"])
        )
    else:
        print("No position - buying")
        buy_option(ib, ticker, dte_days)

    display_position(ib, ticker)


def main():
    """Main entry point - connect to IB and run strategy"""
    ib = IB()

    try:
        print(f"Connecting to IB on port {PORT}...")
        ib.connect("127.0.0.1", PORT, clientId=CLIENT_ID)
        print("Connected")

        init_csv(TICKER)
        log_n_notify.init_option_trades_csv(TICKER)
        run_daily(ib, TICKER, DTE_DAYS)

    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        # Always disconnect properly
        if ib.isConnected():
            ib.disconnect()
            print("Disconnected from IB")

    return 0


if __name__ == "__main__":
    """
    Simple Option Trading Strategy
    
    Configuration (edit at top of file):
    - PORT: IB connection port (default: 4002)
    - TICKER: Stock to trade options on (default: "SPY")
    - DTE_DAYS: Days to expiration (default: 1)
    
    Files created:
    - output/trades_SPY.csv: Trade log with timestamps and P&L
    
    Usage:
        python strategy.py
    
    Requirements:
        pip install ib_async
    """
    sys.exit(main())
