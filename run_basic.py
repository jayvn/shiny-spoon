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

    def last_trade(self):
        """Return last trade row as dict or None"""
        if not self.trades_file.exists():
            return None
        last = None
        with self.trades_file.open("r", newline="") as f:
            rdr = csv.reader(f)
            next(rdr, None)
            for row in rdr:
                last = row
        if not last:
            return None
        return {
            "timestamp": last[0],
            "action": last[1],
            "ticker": last[2],
            "strike": float(last[3]),
            "expiry": last[4],
            "price": float(last[5]),
            "pnl": float(last[6]) if last[6] else 0.0,
        }

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

        return True

    def sell_option(self, strike: float, expiry: str, entry_price: float) -> bool:
        """Sell the current option position reconstructed from CSV"""
        option = Option(self.ticker, expiry, strike, "C", "SMART")
        contract = self.ib.qualifyContracts(option)[0]

        order = MarketOrder("SELL", 1)
        trade = self.ib.placeOrder(contract, order)

        while not trade.isDone():
            self.ib.sleep(1)

        exit_price = trade.orderStatus.avgFillPrice
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
        return True

    def display_position(self):
        """Display current position"""
        print("\n" + "=" * 50)
        print(f"POSITION STATUS - {self.ticker}")
        print("=" * 50)

        last = self.last_trade()
        if last and last["action"] == "BUY":
            print(f"Position: LONG {last['strike']} Call")
            print(f"Entry Price: ${last['price']:.2f}")
            print(f"Entry Time: {last['timestamp']}")
            print(f"Expiry: {last['expiry']}")
            option = Option(self.ticker, last["expiry"], last["strike"], "C", "SMART")
            contract = self.ib.qualifyContracts(option)[0]
            tickers = self.ib.reqTickers(contract)
            current_price = tickers[0].marketPrice()
            pnl = (current_price - last["price"]) * 100
            print(f"Current Price: ${current_price:.2f}")
            print(f"Unrealized P&L: ${pnl:.2f}")
        else:
            print("No active position")

        print("=" * 50 + "\n")

    def run_daily(self):
        """Run daily trading logic"""
        print(f"=== Daily Run for {self.ticker} ===")

        last = self.last_trade()
        if last and last["action"] == "BUY":
            print("Have position - selling")
            self.sell_option(strike=last["strike"], expiry=last["expiry"], entry_price=last["price"])
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
    
    Usage:
        python strategy.py
    
    Requirements:
        pip install ib_async
    """
    sys.exit(main())
