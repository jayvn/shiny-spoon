1% done
# target implementation. 

# Poor Man's Covered Call (PMCC) Strategy

Automated implementation of the Poor Man's Covered Call options strategy using Interactive Brokers API.

## Overview

PMCC is a cost-efficient alternative to traditional covered calls, using a long-term LEAPS call option instead of owning 100 shares of stock. The strategy generates income by selling short-term calls against the LEAPS position.

## Features

- **Automated LEAPS Selection**: Finds optimal 70+ delta LEAPS with 200+ DTE
- **Smart Short Call Management**: Sells 15-delta calls with configurable expiry (daily/weekly)
- **Risk Management**: 
  - Loss limits (dollar and percentage based)
  - Profit taking at 50% of max profit
  - Delta-based rolling triggers
- **Position Rolling**: Automatically rolls challenged positions when delta hits 0.35
- **Liquidity Filters**: Ensures tradeable options with adequate volume and tight spreads
- **State Persistence**: Saves and loads positions between sessions

## Quick Start

```python
from ib_insync import IB
from pmcc_strategy.pmcc_strategy import PMCCStrategy
from pmcc_strategy.config import PMCCConfig

# Connect to IB
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Configure strategy
config = PMCCConfig(
    underlying_ticker="QQQ",
    short_call_dte_target=7  # Weekly options
)

# Run strategy
strategy = PMCCStrategy(ib, config)
strategy.run()
```

## Configuration Parameters

Key parameters in `config.py`:

- `leaps_delta_target`: Target delta for LEAPS (default: 0.70)
- `short_call_delta_target`: Target delta for short calls (default: 0.15)
- `roll_trigger_delta`: Roll when short call delta reaches this (default: 0.35)
- `max_loss_threshold`: Maximum loss per contract (default: $200)
- `profit_take_percentage`: Take profit at this percentage (default: 50%)

## Strategy Workflow

1. **Initial Setup**
   - Buy LEAPS call with 70+ delta and 200+ DTE
   - Sell first short call at 15 delta

2. **Daily Management**
   - Check LEAPS health
   - Monitor short call position
   - Take action based on triggers:
     - Close for profit (50% target)
     - Close for loss (stop loss)
     - Roll if challenged (delta > 0.35)
     - Sell new call if none active

3. **Position Rolling**
   - Roll up and out when short delta exceeds threshold
   - Maintain net credit or small debit ($25 max)

## Files

- `pmcc_strategy.py` - Main strategy execution
- `config.py` - Configuration and state management
- `option_selection.py` - Option scoring and selection
- `short_call_manager.py` - Short call position management
- `daily_manager.py` - Daily routine and metrics

## Risk Warnings

- Options trading involves substantial risk
- PMCC can result in losses exceeding initial investment
- Requires active management and monitoring
- Not suitable for all investors

## Requirements

- Interactive Brokers account with options trading
- IB Gateway or TWS running
- Python packages: ib_insync, pandas, datetime
