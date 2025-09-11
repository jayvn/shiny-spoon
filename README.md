# Poor Man's Covered Call (PMCC) Strategy

Automated options trading strategies for Interactive Brokers, featuring PMCC implementation with comprehensive logging, monitoring, and Telegram notifications.

## Overview

This repository contains two main trading strategies:
- **PMCC Strategy** (`run_pmcc.py`): Poor Man's Covered Call implementation using LEAPS as collateral
- **Basic Options Strategy** (`run_basic.py`): Simple short call selling strategy for testing

## Features

- **Automated Trading**: Fully automated option selection and execution
- **Advanced Logging**: Comprehensive trade tracking with Greeks, IV, and market data
- **Telegram Notifications**: Real-time alerts for trades and position updates
- **P&L Visualization**: Interactive charts for performance analysis
- **State Management**: Persistent position tracking across sessions
- **Risk Controls**: Built-in stop-loss and profit-taking mechanisms

## Project Structure

```
├── run_pmcc.py           # Main PMCC strategy execution
├── run_basic.py          # Simple options strategy for testing
├── option_trades.py      # Trade logging with Greeks and market data
├── telegram_bot.py       # Telegram notification system
├── plot_pnl.py          # P&L visualization and analysis
├── requirements.txt      # Python dependencies
├── CLAUDE.md            # Development guidelines
└── Generated Files:
    ├── state_<TICKER>.pkl       # Position state persistence
    ├── trades_<TICKER>.csv      # Basic trade log
    └── option_trades_<TICKER>.csv  # Detailed option trades log
```

## Quick Start

1. **Setup Environment**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Configure IB Gateway**
- Ensure IB Gateway/TWS is running
- Enable API access on `127.0.0.1:4002`
- Paper trading account recommended for testing

3. **Run PMCC Strategy**
```bash
python run_pmcc.py
```

4. **Run Basic Strategy (Testing)**
```bash
python run_basic.py
```

## Configuration

Edit strategy parameters at the top of each script:
- `PORT`: IB Gateway port (default: 4002)
- `TICKER`: Underlying symbol
- `DTE_DAYS`: Days to expiration target
- `QUANTITY`: Number of contracts

## Trading Strategies

### PMCC Strategy
- Buys long-term LEAPS (70+ delta, 200+ DTE)
- Sells short-term calls against LEAPS position
- Automatic rolling when challenged
- Profit target: 50% of max profit
- Stop loss: Configurable dollar/percentage limits

### Basic Strategy
- Simple short call selling
- Used for testing infrastructure
- Minimal risk management

## Monitoring & Analysis

### Trade Logging
- `option_trades.py`: Captures comprehensive trade data including:
  - Entry/exit prices and timestamps
  - Greeks (Delta, Gamma, Theta, Vega)
  - Implied volatility
  - Market conditions at trade time

### Telegram Notifications
- Real-time trade alerts
- Position updates
- P&L notifications
- Risk warnings

### Performance Visualization
```bash
python plot_pnl.py
```
Generates interactive charts showing:
- Cumulative P&L
- Greeks evolution
- Underlying price correlation
- Trade distribution analysis

## Development

### Code Quality
```bash
ruff check .
ruff format .
basedpyright
```

### Testing
Paper trading account strongly recommended for all testing.

## Risk Warnings

⚠️ **IMPORTANT**: This is for paper trading only. Options trading involves substantial risk including total loss of capital.

## Requirements

- Python 3.8+
- Interactive Brokers account
- IB Gateway or TWS
- See `requirements.txt` for Python packages
