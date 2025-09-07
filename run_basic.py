#!/usr/bin/env python
"""
Simple paper-trading option strategy.
Buys ATM calls when no position, sells when position exists.
Logs trades to CSV with timestamps and P&L.
"""

import csv
import datetime
import pickle
import sys
from pathlib import Path

from ib_async import IB, MarketOrder, Option, Stock

# Configuration
PORT = 4002
CLIENT_ID = 0
TICKER = "SPY"
DTE_DAYS = 1


class SimpleOptionStrategy:
    """Simple daily option trading strategy - buy and sell a single option"""

    def __init__(self, ib: IB, ticker: str = TICKER, dte_days: int = DTE_DAYS):
        self.ib = ib
        self.ticker = ticker
        self.dte_days = dte_days
        self.state_file = Path(f"state_{ticker}.pkl")
        self.trades_file = Path(f"trades_{ticker}.csv")
        self.current_position = None
        # Initialize CSV if doesn't exist
        if not self.trades_file.exists():
            with self.trades_file.open("w", newline="") as f:
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

    def save_state(self):
        """Save current position to file"""
        with self.state_file.open("wb") as f:
            pickle.dump(self.current_position, f)

    def load_state(self) -> bool:
        """Load saved position if exists"""
        if self.state_file.exists():
            with self.state_file.open("rb") as f:
                self.current_position = pickle.load(f)
            return True
        return False

    def get_atm_option(self, right: str = "C") -> Option:
        """Get at-the-money option with target DTE"""
        stock = Stock(self.ticker, "SMART", "USD")
        self.ib.qualifyContracts(stock)

        tickers = self.ib.reqTickers(stock)
        current_price = tickers[0].marketPrice()
        strike = round(current_price)

        target_date = datetime.date.today() + datetime.timedelta(days=self.dte_days)
        chains = self.ib.reqSecDefOptParams(
            stock.symbol, "", stock.secType, stock.conId
        )

        expirations: list[str] = []
        for chain in chains:
            expirations.extend(chain.expirations)
        expirations = sorted(set(expirations))
        closest_expiry = min(
            expirations,
            key=lambda x: abs(
                datetime.datetime.strptime(x, "%Y%m%d").date() - target_date
            ),
        )

        option = Option(self.ticker, closest_expiry, strike, right, "SMART")
        return self.ib.qualifyContracts(option)[0]

    def buy_option(self) -> bool:
        """Buy a single option contract"""
        option = self.get_atm_option("C")
        order = MarketOrder("BUY", 1)
        trade = self.ib.placeOrder(option, order)

        while not trade.isDone():
            self.ib.sleep(1)

        fill_price = trade.orderStatus.avgFillPrice
        self.current_position = {
            "contract": option,
            "side": "BUY",
            "entry_price": fill_price,
            "entry_time": datetime.datetime.now().isoformat(),
            "strike": option.strike,
            "expiry": option.lastTradeDateOrContractMonth,
        }
        print(f"Bought {self.ticker} {option.strike} Call @ ${fill_price:.2f}")

        with self.trades_file.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.datetime.now().isoformat(),
                    "BUY",
                    self.ticker,
                    option.strike,
                    option.lastTradeDateOrContractMonth,
                    fill_price,
                    0,
                ]
            )

        self.save_state()
        return True

    def sell_option(self) -> bool:
        """Sell the current option position"""
        contract = self.current_position["contract"]

        order = MarketOrder("SELL", 1)
        trade = self.ib.placeOrder(contract, order)

        while not trade.isDone():
            self.ib.sleep(1)

        exit_price = trade.orderStatus.avgFillPrice
        entry_price = self.current_position["entry_price"]
        pnl = (exit_price - entry_price) * 100

        print(f"Sold {self.ticker} {contract.strike} Call @ ${exit_price:.2f}")
        print(f"P&L: ${pnl:.2f}")

        with self.trades_file.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.datetime.now().isoformat(),
                    "SELL",
                    self.ticker,
                    contract.strike,
                    contract.lastTradeDateOrContractMonth,
                    exit_price,
                    round(pnl, 2),
                ]
            )

        self.current_position = None
        self.save_state()
        return True

    def display_position(self):
        """Display current position"""
        print("\n" + "=" * 50)
        print(f"POSITION STATUS - {self.ticker}")
        print("=" * 50)

        if self.current_position:
            pos = self.current_position
            print(f"Position: LONG {pos['strike']} Call")
            print(f"Entry Price: ${pos['entry_price']:.2f}")
            print(f"Entry Time: {pos['entry_time']}")
            print(f"Expiry: {pos['expiry']}")

            tickers = self.ib.reqTickers(pos["contract"])
            current_price = tickers[0].marketPrice()
            pnl = (current_price - pos["entry_price"]) * 100
            print(f"Current Price: ${current_price:.2f}")
            print(f"Unrealized P&L: ${pnl:.2f}")
        else:
            print("No active position")

        print("=" * 50 + "\n")

    def run_daily(self):
        """Run daily trading logic"""
        print(f"=== Daily Run for {self.ticker} ===")

        self.load_state()

        # Simple logic: If no position, buy. If have position, sell.
        if self.current_position:
            print("Have position - selling")
            self.sell_option()
        else:
            print("No position - buying")
            self.buy_option()

        # Display current status
        self.display_position()


def main():
    """Main entry point - connect to IB and run strategy"""
    ib = IB()

    print(f"Connecting to IB on port {PORT}...")
    ib.connect("127.0.0.1", PORT, clientId=CLIENT_ID)
    print("Connected")

    strategy = SimpleOptionStrategy(ib, ticker=TICKER, dte_days=DTE_DAYS)
    strategy.run_daily()

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
    - trades_SPY.csv: Trade log with timestamps and P&L
    - state_SPY.pkl: Saved position state
    
    Usage:
        python strategy.py
    
    Requirements:
        pip install ib_async
    """
    sys.exit(main())
