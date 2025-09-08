#!/usr/bin/env python
"""
Plot P&L from trading CSV files.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_pnl(ticker: str):
    """Read option trades CSV and create comprehensive PnL plots"""
    trades_file = Path(f"output/option_trades_{ticker}.csv")
    if not trades_file.exists():
        print(f"No option trades file found: {trades_file}")
        return

    df = pd.read_csv(trades_file)
    if df.empty:
        print("No trades found")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Use cumulative_pnl if available, otherwise calculate from pnl
    if "cumulative_pnl" not in df.columns or df["cumulative_pnl"].isna().all():
        df["cumulative_pnl"] = df["pnl"].fillna(0).cumsum()

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # Cumulative P&L over time
    ax1 = axes[0, 0]
    ax1.plot(
        df["timestamp"], df["cumulative_pnl"], marker="o", linewidth=2, markersize=4
    )
    ax1.set_title(f"{ticker} Cumulative P&L")
    ax1.set_ylabel("Cumulative P&L ($)")
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis="x", rotation=45)

    # Individual trade P&L
    ax2 = axes[0, 1]
    closing_trades = df[df["action"].isin(["SELL", "BUY_TO_CLOSE"])]
    if not closing_trades.empty:
        colors = ["green" if pnl >= 0 else "red" for pnl in closing_trades["pnl"]]
        ax2.bar(
            range(len(closing_trades)), closing_trades["pnl"], color=colors, alpha=0.7
        )
        ax2.set_title(f"{ticker} Individual Trade P&L")
        ax2.set_xlabel("Trade Number")
        ax2.set_ylabel("P&L ($)")
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color="black", linestyle="-", alpha=0.3)

    # Option Greeks over time (Delta)
    ax3 = axes[1, 0]
    if "delta" in df.columns and not df["delta"].isna().all():
        ax3.plot(
            df["timestamp"],
            df["delta"],
            marker="s",
            linewidth=1,
            markersize=3,
            color="blue",
        )
        ax3.set_title(f"{ticker} Option Delta")
        ax3.set_ylabel("Delta")
        ax3.grid(True, alpha=0.3)
        ax3.tick_params(axis="x", rotation=45)

    # Underlying vs Strike prices
    ax4 = axes[1, 1]
    if "underlying_price" in df.columns and not df["underlying_price"].isna().all():
        ax4.scatter(
            df["timestamp"], df["underlying_price"], label="Underlying", alpha=0.6, s=20
        )
        ax4.scatter(df["timestamp"], df["strike"], label="Strike", alpha=0.6, s=20)
        ax4.set_title(f"{ticker} Underlying vs Strike Prices")
        ax4.set_ylabel("Price ($)")
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plot_file = f"output/{ticker}_option_pnl_plot.png"
    plt.savefig(plot_file, dpi=150, bbox_inches="tight")
    print(f"Plot saved to: {plot_file}")
    plt.show()


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    plot_pnl(ticker)
