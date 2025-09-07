#!/usr/bin/env python
"""
Complete standalone simple option trading strategy for paper trading automation.
Buys ATM calls when no position, sells when position exists.
Logs all trades to CSV with timestamps and P&L.
"""

import logging
import datetime
from typing import Optional
from ib_async import IB, Stock, Option, MarketOrder
import pickle
import csv
import sys
from pathlib import Path

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
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize CSV if doesn't exist
        if not self.trades_file.exists():
            with self.trades_file.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'action', 'ticker', 'strike', 'expiry', 'price', 'pnl'])
    
    def save_state(self):
        """Save current position to file"""
        try:
            with self.state_file.open('wb') as f:
                pickle.dump(self.current_position, f)
            self.logger.info(f"State saved: {self.current_position}")
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def load_state(self) -> bool:
        """Load saved position if exists"""
        if self.state_file.exists():
            try:
                with self.state_file.open('rb') as f:
                    self.current_position = pickle.load(f)
                self.logger.info(f"State loaded: {self.current_position}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to load state: {e}")
        return False
    
    def get_atm_option(self, right: str = 'C') -> Optional[Option]:
        """Get at-the-money option with target DTE"""
        try:
            # Get underlying stock
            stock = Stock(self.ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            # Get current price
            tickers = self.ib.reqTickers(stock)
            if not tickers:
                self.logger.error("Could not get stock price")
                return None
            
            current_price = tickers[0].marketPrice()
            if not current_price:
                # Try midpoint if no market price
                ticker = tickers[0]
                if ticker.bid and ticker.ask:
                    current_price = (ticker.bid + ticker.ask) / 2
                else:
                    self.logger.error("No price available for stock")
                    return None
            
            # Find nearest strike
            strike = round(current_price)
            
            # Calculate target expiry
            target_date = datetime.date.today() + datetime.timedelta(days=self.dte_days)
            
            # Get option chains
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
            
            if not chains:
                self.logger.error("No option chains found")
                return None
            
            # Find closest expiry
            expirations = []
            for chain in chains:
                expirations.extend(chain.expirations)
            
            expirations = sorted(set(expirations))
            if not expirations:
                self.logger.error("No expirations found")
                return None
                
            closest_expiry = min(expirations, key=lambda x: abs(
                datetime.datetime.strptime(x, '%Y%m%d').date() - target_date
            ))
            
            # Create option contract
            option = Option(self.ticker, closest_expiry, strike, right, 'SMART')
            qualified = self.ib.qualifyContracts(option)
            
            if qualified:
                return qualified[0]
            else:
                self.logger.error("Could not qualify option contract")
                return None
                
        except Exception as e:
            self.logger.error(f"Error finding ATM option: {e}")
            return None
    
    def buy_option(self) -> bool:
        """Buy a single option contract"""
        try:
            option = self.get_atm_option('C')  # Buy a call
            if not option:
                self.logger.error("Could not find suitable option")
                return False
            
            # Place buy order
            order = MarketOrder('BUY', 1)
            trade = self.ib.placeOrder(option, order)
            
            # Wait for fill with timeout
            timeout = 30  # seconds
            start_time = datetime.datetime.now()
            
            while not trade.isDone():
                self.ib.sleep(1)
                if (datetime.datetime.now() - start_time).seconds > timeout:
                    self.logger.error("Order timeout")
                    self.ib.cancelOrder(order)
                    return False
            
            if trade.orderStatus.status == 'Filled':
                fill_price = trade.orderStatus.avgFillPrice
                self.current_position = {
                    'contract': option,
                    'side': 'BUY',
                    'entry_price': fill_price,
                    'entry_time': datetime.datetime.now().isoformat(),
                    'strike': option.strike,
                    'expiry': option.lastTradeDateOrContractMonth
                }
                self.logger.info(f"Bought {self.ticker} {option.strike} Call @ ${fill_price:.2f}")
                
                # Log to CSV
                with self.trades_file.open('a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.datetime.now().isoformat(),
                        'BUY',
                        self.ticker,
                        option.strike,
                        option.lastTradeDateOrContractMonth,
                        fill_price,
                        0  # No P&L on entry
                    ])
                
                self.save_state()
                return True
            else:
                self.logger.error(f"Order failed: {trade.orderStatus.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error buying option: {e}")
            return False
    
    def sell_option(self) -> bool:
        """Sell the current option position"""
        if not self.current_position:
            self.logger.info("No position to sell")
            return False
        
        try:
            contract = self.current_position['contract']
            
            # Place sell order
            order = MarketOrder('SELL', 1)
            trade = self.ib.placeOrder(contract, order)
            
            # Wait for fill with timeout
            timeout = 30  # seconds
            start_time = datetime.datetime.now()
            
            while not trade.isDone():
                self.ib.sleep(1)
                if (datetime.datetime.now() - start_time).seconds > timeout:
                    self.logger.error("Sell order timeout")
                    self.ib.cancelOrder(order)
                    return False
            
            if trade.orderStatus.status == 'Filled':
                exit_price = trade.orderStatus.avgFillPrice
                entry_price = self.current_position['entry_price']
                pnl = (exit_price - entry_price) * 100
                
                self.logger.info(f"Sold {self.ticker} {contract.strike} Call @ ${exit_price:.2f}")
                self.logger.info(f"P&L: ${pnl:.2f}")
                
                # Log to CSV
                with self.trades_file.open('a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.datetime.now().isoformat(),
                        'SELL',
                        self.ticker,
                        contract.strike,
                        contract.lastTradeDateOrContractMonth,
                        exit_price,
                        round(pnl, 2)
                    ])
                
                self.current_position = None
                self.save_state()
                return True
            else:
                self.logger.error(f"Sell order failed: {trade.orderStatus.status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error selling option: {e}")
            return False
    
    def display_position(self):
        """Display current position"""
        print("\n" + "="*50)
        print(f"POSITION STATUS - {self.ticker}")
        print("="*50)
        
        if self.current_position:
            pos = self.current_position
            print(f"Position: LONG {pos['strike']} Call")
            print(f"Entry Price: ${pos['entry_price']:.2f}")
            print(f"Entry Time: {pos['entry_time']}")
            print(f"Expiry: {pos['expiry']}")
            
            # Get current price
            try:
                tickers = self.ib.reqTickers(pos['contract'])
                if tickers and tickers[0].marketPrice():
                    current_price = tickers[0].marketPrice()
                    pnl = (current_price - pos['entry_price']) * 100
                    print(f"Current Price: ${current_price:.2f}")
                    print(f"Unrealized P&L: ${pnl:.2f}")
                else:
                    print("Current Price: Unable to fetch")
            except:
                print("Current Price: Unable to fetch")
        else:
            print("No active position")
        
        print("="*50 + "\n")
    
    def run_daily(self):
        """Run daily trading logic"""
        self.logger.info(f"=== Daily Run for {self.ticker} ===")
        
        # Load any existing state
        self.load_state()
        
        # Simple logic: If no position, buy. If have position, sell.
        if self.current_position:
            self.logger.info("Have position - selling")
            self.sell_option()
        else:
            self.logger.info("No position - buying")
            self.buy_option()
        
        # Display current status
        self.display_position()


def main():
    """Main entry point - connect to IB and run strategy"""
    ib = IB()
    
    try:
        # Connect to IB Gateway/TWS
        print(f"Connecting to IB on port {PORT}...")
        ib.connect('127.0.0.1', PORT, clientId=CLIENT_ID)
        print(f"Connected successfully!")
        
        # Create and run strategy
        strategy = SimpleOptionStrategy(ib, ticker=TICKER, dte_days=DTE_DAYS)
        strategy.run_daily()
        
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to IB on port {PORT}")
        print("Make sure IB Gateway or TWS is running with API enabled")
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
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
    - trades_SPY.csv: Trade log with timestamps and P&L
    - state_SPY.pkl: Saved position state
    
    Usage:
        python strategy.py
    
    Requirements:
        pip install ib_async
    """
    sys.exit(main())