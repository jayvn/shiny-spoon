#!/usr/bin/env python
"""
Plot P&L from trading CSV files.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_pnl(ticker: str):
    """Read CSV and create PnL plots"""
    trades_file = Path(f"output/trades_{ticker}.csv")
    if not trades_file.exists():
        print(f"No trades file found: {trades_file}")
        return

    df = pd.read_csv(trades_file)
    if df.empty:
        print("No trades found")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    df["cumulative_pnl"] = df["pnl"].cumsum()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(df["timestamp"], df["cumulative_pnl"], marker="o")
    ax1.set_title(f"{ticker} Cumulative P&L")
    ax1.set_ylabel("Cumulative P&L ($)")
    ax1.grid(True, alpha=0.3)

    sell_trades = df[df["action"] == "SELL"]
    if not sell_trades.empty:
        ax2.bar(range(len(sell_trades)), sell_trades["pnl"])
        ax2.set_title(f"{ticker} Individual Trade P&L")
        ax2.set_xlabel("Trade Number")
        ax2.set_ylabel("P&L ($)")
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_file = f"output/{ticker}_pnl_plot.png"
    plt.savefig(plot_file)
    print(f"Plot saved to: {plot_file}")
    plt.show()


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    plot_pnl(ticker)
