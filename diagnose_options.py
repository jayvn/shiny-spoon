#!/usr/bin/env python
"""
Diagnostic script to list available options for SPY
"""

import datetime
import sys
from ib_async import IB, Option, Stock

# Configuration
PORT = 4002
CLIENT_ID = 0
TICKER = "SPY"


def main():
    """List all available options"""
    ib = IB()
    
    print(f"Connecting to IB on port {PORT}...")
    ib.connect("127.0.0.1", PORT, clientId=CLIENT_ID)
    print("Connected\n")
    
    # Get stock info
    stock = Stock(TICKER, "SMART", "USD")
    ib.qualifyContracts(stock)
    
    # Get current price
    tickers = ib.reqTickers(stock)
    current_price = tickers[0].marketPrice()
    print(f"Current {TICKER} price: ${current_price:.2f}\n")
    
    # Get option chains
    chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
    
    print(f"Found {len(chains)} option chains\n")
    
    # Analyze chains
    all_expirations = set()
    all_strikes = set()
    
    for i, chain in enumerate(chains):
        print(f"Chain {i+1}:")
        print(f"  Exchange: {chain.exchange}")
        print(f"  Underlying ConId: {chain.underlyingConId}")
        print(f"  Trading Class: {chain.tradingClass}")
        print(f"  Multiplier: {chain.multiplier}")
        print(f"  Expirations: {len(chain.expirations)}")
        print(f"  Strikes: {len(chain.strikes)}")
        
        all_expirations.update(chain.expirations)
        all_strikes.update(chain.strikes)
        
        # Show first few strikes
        sorted_strikes = sorted(chain.strikes)[:10]
        print(f"  First strikes: {sorted_strikes}")
        print()
    
    # Sort and display expirations
    sorted_expirations = sorted(all_expirations)
    print("\nAvailable expirations:")
    today = datetime.date.today()
    
    for exp_str in sorted_expirations[:10]:  # Show first 10
        exp_date = datetime.datetime.strptime(exp_str, "%Y%m%d").date()
        dte = (exp_date - today).days
        print(f"  {exp_str} ({exp_date.strftime('%Y-%m-%d')}) - {dte} DTE")
    
    # Find LEAPS (>365 DTE)
    leaps_expirations = []
    for exp_str in sorted_expirations:
        exp_date = datetime.datetime.strptime(exp_str, "%Y%m%d").date()
        dte = (exp_date - today).days
        if dte >= 365:
            leaps_expirations.append((exp_str, exp_date, dte))
    
    print(f"\nLEAPS expirations (>= 365 DTE): {len(leaps_expirations)}")
    for exp_str, exp_date, dte in leaps_expirations[:5]:
        print(f"  {exp_str} ({exp_date.strftime('%Y-%m-%d')}) - {dte} DTE")
    
    # Show strikes around current price
    sorted_strikes = sorted(all_strikes)
    strikes_near_price = [s for s in sorted_strikes if current_price * 0.8 <= s <= current_price * 1.2]
    
    print(f"\nStrikes near current price (80%-120% of ${current_price:.2f}):")
    print(f"  Total: {len(strikes_near_price)} strikes")
    print(f"  Range: ${min(strikes_near_price):.0f} - ${max(strikes_near_price):.0f}")
    
    # Sample some strikes
    sample_strikes = strikes_near_price[::5][:10]  # Every 5th strike, max 10
    print(f"  Sample: {[f'${s:.0f}' for s in sample_strikes]}")
    
    # Test a specific option
    if leaps_expirations and strikes_near_price:
        test_expiry = leaps_expirations[0][0]
        test_strike = min(strikes_near_price, key=lambda x: abs(x - current_price))
        
        print(f"\nTesting specific option:")
        print(f"  {TICKER} {test_strike}C exp {test_expiry}")
        
        option = Option(TICKER, test_expiry, test_strike, "C", "SMART")
        try:
            contracts = ib.qualifyContracts(option)
            if contracts:
                print(f"  ✓ Contract qualified successfully")
                contract = contracts[0]
                
                # Get market data
                tickers = ib.reqTickers(contract)
                if tickers:
                    ticker = tickers[0]
                    print(f"  Bid: ${ticker.bid:.2f}")
                    print(f"  Ask: ${ticker.ask:.2f}")
                    print(f"  Last: ${ticker.last:.2f}")
                    
                    if ticker.modelGreeks:
                        print(f"  Delta: {ticker.modelGreeks.delta:.3f}")
                        print(f"  Gamma: {ticker.modelGreeks.gamma:.4f}")
                        print(f"  Theta: {ticker.modelGreeks.theta:.3f}")
                        print(f"  Vega: {ticker.modelGreeks.vega:.3f}")
            else:
                print(f"  ✗ Failed to qualify contract")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    ib.disconnect()
    print("\nDisconnected from IB")
    return 0


if __name__ == "__main__":
    sys.exit(main())