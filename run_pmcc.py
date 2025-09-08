#!/usr/bin/env python
"""
PMCC (Poor Man's Covered Call) with Stop Loss strategy
Based on algorithm.md - buys LEAPS and sells short calls against it
Includes comprehensive stop loss protection for the LEAPS position
"""

import csv
import datetime
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ib_async import IB, MarketOrder, Option, Stock

import telegram_bot as tg

# Configuration
PORT = 4002
CLIENT_ID = 0
TICKER = "SPY"

# LEAPS Parameters
LEAPS_MIN_DTE = 365
LEAPS_DELTA_TARGET = 0.7

# Short Call Parameters
SHORT_DTE_TARGET = 30
SHORT_DELTA_TARGET = 0.3
PROFIT_TAKE_PERCENTAGE = 75.0
MAX_LOSS_PERCENTAGE = 200.0
MAX_LOSS_ABSOLUTE = 100.0
ROLL_TRIGGER_DELTA = 0.5

# Stop Loss Parameters
LEAPS_STOP_LOSS_PERCENTAGE = 20.0
LEAPS_STOP_LOSS_ABSOLUTE = 500.0
TOTAL_POSITION_STOP_LOSS = 1000.0
TRAILING_STOP_ENABLED = True
TRAILING_STOP_PERCENTAGE = 15.0


@dataclass
class PMCCState:
    """Track state of PMCC position"""

    # LEAPS tracking
    leaps_strike: Optional[float] = None
    leaps_expiry: Optional[str] = None
    leaps_original_cost: Optional[float] = None
    leaps_high_water_mark: Optional[float] = None
    position_opened_date: Optional[str] = None
    stop_loss_triggered: bool = False

    # Short call tracking
    short_strike: Optional[float] = None
    short_expiry: Optional[str] = None
    short_original_premium: Optional[float] = None

    # P&L tracking
    total_short_premium_collected: float = 0.0
    realized_pnl: float = 0.0


def load_state(ticker: str) -> PMCCState:
    """Load state from JSON file"""
    state_file = Path(f"output/state_{ticker}.json")
    state_file.parent.mkdir(exist_ok=True)
    if state_file.exists():
        with state_file.open("r") as f:
            data = json.load(f)
            return PMCCState(**data)
    return PMCCState()


def save_state(ticker: str, state: PMCCState):
    """Save state to JSON file"""
    state_file = Path(f"output/state_{ticker}.json")
    state_file.parent.mkdir(exist_ok=True)
    with state_file.open("w") as f:
        json.dump(asdict(state), f, indent=2, default=str)


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
                    "type",
                    "ticker",
                    "strike",
                    "expiry",
                    "price",
                    "delta",
                    "pnl",
                    "cumulative_pnl",
                    "notes",
                ]
            )


def log_trade(
    ticker: str,
    action: str,
    option_type: str,
    strike: float,
    expiry: str,
    price: float,
    delta: float = 0.0,
    pnl: float = 0.0,
    cumulative_pnl: float = 0.0,
    notes: str = "",
):
    """Log trade to CSV and send Telegram notification"""
    trades_file = Path(f"output/trades_{ticker}.csv")
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
                price,
                delta,
                pnl,
                cumulative_pnl,
                notes,
            ]
        )

    # Send to Telegram
    tg.send_trade_alert(
        f"{action} {option_type}",
        ticker,
        strike,
        expiry,
        price,
        delta=f"{delta:.3f}" if delta else None,
        pnl=f"${pnl:.2f}" if pnl != 0 else None,
        total_pnl=f"${cumulative_pnl:.2f}" if cumulative_pnl != 0 else None,
        notes=notes if notes else None,
    )


def get_option_delta(ib: IB, option) -> float:
    """Get current delta for an option"""
    tickers = ib.reqTickers(option)
    if tickers and tickers[0].modelGreeks:
        return tickers[0].modelGreeks.delta or 0.0
    return 0.0


def find_leaps_option(ib: IB, ticker: str):
    """Find best LEAPS option matching criteria"""
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)

    tickers = ib.reqTickers(stock)
    current_price = tickers[0].marketPrice()

    target_date = datetime.date.today() + datetime.timedelta(days=LEAPS_MIN_DTE)
    chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)

    # Get all strikes and expirations from chains
    all_strikes = set()
    valid_expirations = []

    for chain in chains:
        if chain.tradingClass == ticker:  # Use main trading class only
            for exp in chain.expirations:
                exp_date = datetime.datetime.strptime(exp, "%Y%m%d").date()
                if exp_date >= target_date:
                    valid_expirations.append(exp)
                    all_strikes.update(chain.strikes)

    if not valid_expirations:
        print(f"No LEAPS found with DTE >= {LEAPS_MIN_DTE}")
        return None

    # Sort and get closest expiry
    valid_expirations = sorted(set(valid_expirations))
    closest_expiry = valid_expirations[0]

    # Filter strikes near current price for LEAPS (80-110% of spot)
    min_strike = current_price * 0.8
    max_strike = current_price * 1.1
    test_strikes = sorted(
        [int(s) for s in all_strikes if min_strike <= s <= max_strike]
    )

    print(f"Testing {len(test_strikes)} strikes for LEAPS (exp {closest_expiry})...")

    best_option = None
    best_delta_diff = float("inf")

    for strike in test_strikes:
        option = Option(ticker, closest_expiry, strike, "C", "SMART")
        try:
            contract = ib.qualifyContracts(option)[0]
            delta = get_option_delta(ib, contract)

            if delta == 0:  # Skip if no delta available
                continue

            delta_diff = abs(delta - LEAPS_DELTA_TARGET)

            if delta >= LEAPS_DELTA_TARGET - 0.15 and delta_diff < best_delta_diff:
                best_option = contract
                best_delta_diff = delta_diff

        except Exception:
            continue

    if best_option:
        delta = get_option_delta(ib, best_option)
        print(f"Selected LEAPS: Strike ${best_option.strike}, Delta {delta:.3f}")

    return best_option


def find_short_option(ib: IB, ticker: str, leaps_strike: float):
    """Find best short call option to sell"""
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)

    tickers = ib.reqTickers(stock)
    current_price = tickers[0].marketPrice()

    target_date = datetime.date.today() + datetime.timedelta(days=SHORT_DTE_TARGET)
    chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)

    # Get all strikes and find closest expiry to target
    all_strikes = set()
    all_expirations = []

    for chain in chains:
        if chain.tradingClass == ticker:  # Use main trading class only
            all_expirations.extend(chain.expirations)
            all_strikes.update(chain.strikes)

    if not all_expirations:
        print("No expirations found")
        return None

    all_expirations = sorted(set(all_expirations))

    # Find expiry closest to target DTE
    closest_expiry = min(
        all_expirations,
        key=lambda x: abs(datetime.datetime.strptime(x, "%Y%m%d").date() - target_date),
    )

    # Filter strikes above LEAPS strike but below 110% of current price
    min_strike = max(int(leaps_strike) + 1, int(current_price * 0.95))
    max_strike = int(current_price * 1.15)
    test_strikes = sorted(
        [int(s) for s in all_strikes if min_strike <= s <= max_strike]
    )

    if not test_strikes:
        print(f"No suitable strikes found above LEAPS ${leaps_strike}")
        return None

    print(
        f"Testing {len(test_strikes)} strikes for short call (exp {closest_expiry})..."
    )

    best_option = None
    best_delta_diff = float("inf")

    for strike in test_strikes:
        option = Option(ticker, closest_expiry, strike, "C", "SMART")
        try:
            contract = ib.qualifyContracts(option)[0]
            delta = get_option_delta(ib, contract)

            if delta == 0:  # Skip if no delta available
                continue

            delta_diff = abs(delta - SHORT_DELTA_TARGET)

            if delta <= SHORT_DELTA_TARGET + 0.15 and delta_diff < best_delta_diff:
                best_option = contract
                best_delta_diff = delta_diff

        except Exception:
            continue

    if best_option:
        delta = get_option_delta(ib, best_option)
        print(f"Selected short call: Strike ${best_option.strike}, Delta {delta:.3f}")

    return best_option


def buy_leaps(ib: IB, ticker: str, state: PMCCState) -> bool:
    """Buy LEAPS call option"""
    option = find_leaps_option(ib, ticker)
    if not option:
        print("No suitable LEAPS found")
        return False

    order = MarketOrder("BUY", 1)
    trade = ib.placeOrder(option, order)

    while not trade.isDone():
        ib.sleep(1)

    fill_price = trade.orderStatus.avgFillPrice
    delta = get_option_delta(ib, option)

    state.leaps_strike = option.strike
    state.leaps_expiry = option.lastTradeDateOrContractMonth
    state.leaps_original_cost = fill_price * 100
    state.leaps_high_water_mark = fill_price * 100
    state.position_opened_date = datetime.datetime.now().isoformat()
    state.stop_loss_triggered = False

    print(
        f"Bought LEAPS: {ticker} {option.strike}C {option.lastTradeDateOrContractMonth}"
    )
    print(f"Price: ${fill_price:.2f} Delta: {delta:.3f}")
    print(
        f"Stop loss at: ${state.leaps_original_cost * (1 - LEAPS_STOP_LOSS_PERCENTAGE / 100):.2f}"
    )

    log_trade(
        ticker,
        "BUY",
        "LEAPS",
        option.strike,
        option.lastTradeDateOrContractMonth,
        fill_price,
        delta,
        0,
        state.realized_pnl,
        "Initial LEAPS purchase",
    )

    save_state(ticker, state)
    return True


def sell_short_call(ib: IB, ticker: str, state: PMCCState) -> bool:
    """Sell short call against LEAPS"""
    if not state.leaps_strike:
        print("No LEAPS position to sell against")
        return False

    option = find_short_option(ib, ticker, state.leaps_strike)
    if not option:
        print("No suitable short call found")
        return False

    order = MarketOrder("SELL", 1)
    trade = ib.placeOrder(option, order)

    while not trade.isDone():
        ib.sleep(1)

    fill_price = trade.orderStatus.avgFillPrice
    delta = get_option_delta(ib, option)

    state.short_strike = option.strike
    state.short_expiry = option.lastTradeDateOrContractMonth
    state.short_original_premium = fill_price * 100
    state.total_short_premium_collected += fill_price * 100

    print(
        f"Sold short call: {ticker} {option.strike}C {option.lastTradeDateOrContractMonth}"
    )
    print(f"Premium: ${fill_price:.2f} Delta: {delta:.3f}")

    log_trade(
        ticker,
        "SELL",
        "SHORT",
        option.strike,
        option.lastTradeDateOrContractMonth,
        fill_price,
        delta,
        0,
        state.realized_pnl,
        "Sold short call",
    )

    save_state(ticker, state)
    return True


def close_short_call(ib: IB, ticker: str, state: PMCCState, reason: str) -> bool:
    """Buy back short call"""
    if not state.short_strike:
        return False

    option = Option(ticker, state.short_expiry, state.short_strike, "C", "SMART")
    contract = ib.qualifyContracts(option)[0]

    order = MarketOrder("BUY", 1)
    trade = ib.placeOrder(contract, order)

    while not trade.isDone():
        ib.sleep(1)

    exit_price = trade.orderStatus.avgFillPrice
    pnl = state.short_original_premium - (exit_price * 100)
    state.realized_pnl += pnl

    print(f"Closed short call @ ${exit_price:.2f}")
    print(f"P&L on trade: ${pnl:.2f}")

    log_trade(
        ticker,
        "BUY_TO_CLOSE",
        "SHORT",
        state.short_strike,
        state.short_expiry,
        exit_price,
        0,
        pnl,
        state.realized_pnl,
        reason,
    )

    state.short_strike = None
    state.short_expiry = None
    state.short_original_premium = None

    save_state(ticker, state)
    return True


def roll_short_call(ib: IB, ticker: str, state: PMCCState) -> bool:
    """Roll short call to new strike/expiry"""
    print("Rolling short call...")
    if close_short_call(ib, ticker, state, "Rolling to new position"):
        return sell_short_call(ib, ticker, state)
    return False


def check_leaps_stop_loss(ib: IB, ticker: str, state: PMCCState) -> bool:
    """Check if LEAPS stop loss triggered"""
    if state.stop_loss_triggered or not state.leaps_strike or not state.leaps_expiry:
        return False

    option = Option(ticker, state.leaps_expiry, state.leaps_strike, "C", "SMART")
    contract = ib.qualifyContracts(option)[0]
    tickers = ib.reqTickers(contract)
    current_price = tickers[0].marketPrice() * 100

    # Update trailing stop
    if TRAILING_STOP_ENABLED and current_price > state.leaps_high_water_mark:
        print(f"New high water mark: ${current_price:.2f}")
        state.leaps_high_water_mark = current_price
        save_state(ticker, state)

    # Calculate losses
    original_cost = state.leaps_original_cost or 0.0
    leaps_loss = original_cost - current_price
    leaps_loss_pct = (leaps_loss / original_cost) * 100 if original_cost else 0

    # Include short call value
    short_value = 0
    if state.short_strike and state.short_expiry and state.short_original_premium:
        short_opt = Option(ticker, state.short_expiry, state.short_strike, "C", "SMART")
        short_contract = ib.qualifyContracts(short_opt)[0]
        short_tickers = ib.reqTickers(short_contract)
        short_current = short_tickers[0].marketPrice() * 100
        short_value = state.short_original_premium - short_current

    total_position_value = current_price + short_value
    total_loss = original_cost - total_position_value

    stop_hit = False
    reason = ""

    # Check stop conditions
    if leaps_loss_pct >= LEAPS_STOP_LOSS_PERCENTAGE:
        stop_hit = True
        reason = f"LEAPS percentage stop: {leaps_loss_pct:.1f}%"

    if leaps_loss >= LEAPS_STOP_LOSS_ABSOLUTE:
        stop_hit = True
        reason = f"LEAPS absolute stop: ${leaps_loss:.2f}"

    if total_loss >= TOTAL_POSITION_STOP_LOSS:
        stop_hit = True
        reason = f"Total position stop: ${total_loss:.2f}"

    if TRAILING_STOP_ENABLED and state.leaps_high_water_mark:
        trailing_level = state.leaps_high_water_mark * (
            1 - TRAILING_STOP_PERCENTAGE / 100
        )
        if current_price <= trailing_level:
            stop_hit = True
            reason = f"Trailing stop at ${current_price:.2f}"

    if stop_hit:
        print(f"STOP LOSS TRIGGERED: {reason}")
        tg.send_stop_loss_alert(ticker, reason, leaps_loss)
        liquidate_all_positions(ib, ticker, state)
        return True

    return False


def liquidate_all_positions(ib: IB, ticker: str, state: PMCCState):
    """Close all positions"""
    print("LIQUIDATING ALL POSITIONS")

    # Close short first
    if state.short_strike:
        close_short_call(ib, ticker, state, "STOP LOSS - closing short")

    # Close LEAPS
    if state.leaps_strike and state.leaps_expiry and state.leaps_original_cost:
        option = Option(ticker, state.leaps_expiry, state.leaps_strike, "C", "SMART")
        contract = ib.qualifyContracts(option)[0]

        order = MarketOrder("SELL", 1)
        trade = ib.placeOrder(contract, order)

        while not trade.isDone():
            ib.sleep(1)

        exit_price = trade.orderStatus.avgFillPrice
        pnl = (exit_price * 100) - (state.leaps_original_cost or 0.0)
        state.realized_pnl += pnl

        print(f"Closed LEAPS @ ${exit_price:.2f}")
        print(f"LEAPS P&L: ${pnl:.2f}")

        log_trade(
            ticker,
            "SELL_TO_CLOSE",
            "LEAPS",
            state.leaps_strike,
            state.leaps_expiry,
            exit_price,
            0,
            pnl,
            state.realized_pnl,
            "STOP LOSS TRIGGERED",
        )

    state.stop_loss_triggered = True
    state.leaps_strike = None
    state.short_strike = None

    print(f"Final P&L: ${state.realized_pnl:.2f}")
    save_state(ticker, state)


def manage_short_call(ib: IB, ticker: str, state: PMCCState):
    """Daily management of short call position"""
    if not state.short_strike or not state.short_expiry:
        return

    option = Option(ticker, state.short_expiry, state.short_strike, "C", "SMART")
    contract = ib.qualifyContracts(option)[0]
    tickers = ib.reqTickers(contract)
    current_price = tickers[0].marketPrice() * 100
    delta = get_option_delta(ib, contract)

    original_premium = state.short_original_premium or 0.0
    current_loss = current_price - original_premium
    current_profit = original_premium - current_price
    loss_pct = (current_loss / original_premium) * 100 if original_premium else 0
    profit_pct = (current_profit / original_premium) * 100 if original_premium else 0

    print(f"Short call: ${state.short_strike}C Delta: {delta:.3f}")
    print(f"P&L: ${-current_loss:.2f} ({profit_pct:.1f}%)")

    # Check exit conditions
    if current_loss >= MAX_LOSS_ABSOLUTE or loss_pct >= MAX_LOSS_PERCENTAGE:
        print(f"Short call loss limit hit: ${current_loss:.2f}")
        close_short_call(ib, ticker, state, "Stop loss on short")

    elif profit_pct >= PROFIT_TAKE_PERCENTAGE:
        print(f"Profit target hit: {profit_pct:.1f}%")
        close_short_call(ib, ticker, state, "Profit target reached")

    elif delta >= ROLL_TRIGGER_DELTA:
        print(f"Delta trigger hit: {delta:.3f}")
        roll_short_call(ib, ticker, state)


def display_position_status(ib: IB, ticker: str, state: PMCCState):
    """Display current position status"""
    print("\n" + "=" * 60)
    print(f"PMCC POSITION STATUS - {ticker}")
    print("=" * 60)

    if state.leaps_strike and state.leaps_expiry:
        option = Option(ticker, state.leaps_expiry, state.leaps_strike, "C", "SMART")
        contract = ib.qualifyContracts(option)[0]
        tickers = ib.reqTickers(contract)
        current_value = tickers[0].marketPrice() * 100

        original_cost = state.leaps_original_cost or 0.0
        unrealized_pnl = current_value - original_cost
        unrealized_pct = (unrealized_pnl / original_cost) * 100 if original_cost else 0

        stop_level = original_cost * (1 - LEAPS_STOP_LOSS_PERCENTAGE / 100)
        distance_to_stop = ((current_value - stop_level) / current_value) * 100

        print(f"LEAPS: {state.leaps_strike}C exp {state.leaps_expiry}")
        print(
            f"Value: ${current_value:.2f} | P&L: ${unrealized_pnl:.2f} ({unrealized_pct:.1f}%)"
        )
        print(f"Stop Loss: ${stop_level:.2f} | Distance: {distance_to_stop:.1f}%")

        if TRAILING_STOP_ENABLED and state.leaps_high_water_mark:
            trailing_level = state.leaps_high_water_mark * (
                1 - TRAILING_STOP_PERCENTAGE / 100
            )
            print(
                f"Trailing Stop: ${trailing_level:.2f} | High: ${state.leaps_high_water_mark:.2f}"
            )

    if state.short_strike and state.short_original_premium:
        print(f"\nShort Call: {state.short_strike}C exp {state.short_expiry}")
        print(f"Premium collected: ${state.short_original_premium:.2f}")

    print(f"\nTotal Premium Collected: ${state.total_short_premium_collected:.2f}")
    print(f"Realized P&L: ${state.realized_pnl:.2f}")
    print("=" * 60 + "\n")


def run_daily(ib: IB, ticker: str):
    """Run daily PMCC management"""
    print(f"=== Daily PMCC Management for {ticker} ===")

    state = load_state(ticker)

    # Check stop loss first
    if check_leaps_stop_loss(ib, ticker, state):
        print("Stop loss triggered - strategy halted")
        return

    # Setup LEAPS if needed
    if not state.leaps_strike and not state.stop_loss_triggered:
        print("No LEAPS position - initiating setup")
        if not buy_leaps(ib, ticker, state):
            print("Failed to buy LEAPS")
            return

    # Manage short call
    if state.short_strike:
        manage_short_call(ib, ticker, state)
    elif state.leaps_strike and not state.stop_loss_triggered:
        print("No short call - selling new one")
        sell_short_call(ib, ticker, state)

    display_position_status(ib, ticker, state)


def main():
    """Main entry point"""
    ib = IB()

    print(f"Connecting to IB on port {PORT}...")
    ib.connect("127.0.0.1", PORT, clientId=CLIENT_ID)
    print("Connected")

    init_csv(TICKER)
    run_daily(ib, TICKER)

    ib.disconnect()
    print("Disconnected from IB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
