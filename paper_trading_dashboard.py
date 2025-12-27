#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Paper Trading Dashboard
=======================
Real-time monitoring dashboard for VN30 paper trading portfolio
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json

class PaperTradingDashboard:
    """Simple dashboard for monitoring paper trading performance"""

    def __init__(self, portfolio_file='paper_trading_portfolio.json', trades_file='paper_trading_trades.csv'):
        self.portfolio_file = portfolio_file
        self.trades_file = trades_file
        self.initial_capital = 100_000_000  # 100M VND

        # Initialize files if not exist
        self._initialize_files()

    def _initialize_files(self):
        """Create initial portfolio and trades files"""

        # Portfolio file (JSON)
        if not Path(self.portfolio_file).exists():
            initial_portfolio = {
                'cash': self.initial_capital,
                'positions': {},
                'total_equity': self.initial_capital,
                'start_date': datetime.now().strftime('%Y-%m-%d'),
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.portfolio_file, 'w', encoding='utf-8') as f:
                json.dump(initial_portfolio, f, indent=2, ensure_ascii=False)
            print(f"[Created] {self.portfolio_file}")

        # Trades file (CSV)
        if not Path(self.trades_file).exists():
            trades_df = pd.DataFrame(columns=[
                'date', 'symbol', 'action', 'quantity', 'price',
                'total_amount', 'cash_after', 'note'
            ])
            trades_df.to_csv(self.trades_file, index=False, encoding='utf-8-sig')
            print(f"[Created] {self.trades_file}")

    def load_portfolio(self):
        """Load current portfolio"""
        with open(self.portfolio_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_portfolio(self, portfolio):
        """Save portfolio"""
        portfolio['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)

    def add_trade(self, symbol, action, quantity, price, note=''):
        """Record a trade"""

        portfolio = self.load_portfolio()
        total_amount = quantity * price

        if action.upper() == 'BUY':
            # Deduct cash
            if portfolio['cash'] < total_amount:
                print(f"[ERROR] Not enough cash! Need {total_amount:,.0f}, have {portfolio['cash']:,.0f}")
                return False

            portfolio['cash'] -= total_amount

            # Add to positions
            if symbol not in portfolio['positions']:
                portfolio['positions'][symbol] = {
                    'quantity': 0,
                    'avg_price': 0,
                    'total_cost': 0,
                    'entry_date': datetime.now().strftime('%Y-%m-%d')
                }

            pos = portfolio['positions'][symbol]
            pos['total_cost'] += total_amount
            pos['quantity'] += quantity
            pos['avg_price'] = pos['total_cost'] / pos['quantity']

        elif action.upper() == 'SELL':
            # Check if have position
            if symbol not in portfolio['positions'] or portfolio['positions'][symbol]['quantity'] < quantity:
                print(f"[ERROR] Not enough shares! Have {portfolio['positions'].get(symbol, {}).get('quantity', 0)}, trying to sell {quantity}")
                return False

            portfolio['cash'] += total_amount

            # Remove from positions
            pos = portfolio['positions'][symbol]
            pos['quantity'] -= quantity
            pos['total_cost'] -= quantity * pos['avg_price']

            # Remove position if fully sold
            if pos['quantity'] == 0:
                del portfolio['positions'][symbol]

        # Save portfolio
        self.save_portfolio(portfolio)

        # Record trade
        trade_record = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'action': action.upper(),
            'quantity': quantity,
            'price': price,
            'total_amount': total_amount,
            'cash_after': portfolio['cash'],
            'note': note
        }

        trades_df = pd.read_csv(self.trades_file, encoding='utf-8-sig')
        trades_df = pd.concat([trades_df, pd.DataFrame([trade_record])], ignore_index=True)
        trades_df.to_csv(self.trades_file, index=False, encoding='utf-8-sig')

        print(f"[TRADE] {action.upper()} {quantity} {symbol} @ {price:,.0f} VND = {total_amount:,.0f} VND")
        return True

    def update_prices(self, current_prices):
        """Update portfolio with current market prices"""

        portfolio = self.load_portfolio()

        # Calculate total equity
        total_equity = portfolio['cash']

        for symbol, pos in portfolio['positions'].items():
            if symbol in current_prices:
                current_value = pos['quantity'] * current_prices[symbol]
                total_equity += current_value

        portfolio['total_equity'] = total_equity
        self.save_portfolio(portfolio)

        return total_equity

    def show_dashboard(self, current_prices=None):
        """Display current portfolio dashboard"""

        portfolio = self.load_portfolio()

        print("\n" + "="*80)
        print("PAPER TRADING DASHBOARD")
        print("="*80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Started: {portfolio['start_date']}")

        # Calculate days trading
        start = datetime.strptime(portfolio['start_date'], '%Y-%m-%d')
        days_trading = (datetime.now() - start).days
        print(f"Days trading: {days_trading}")

        print("\n" + "-"*80)
        print("PORTFOLIO SUMMARY")
        print("-"*80)

        # Cash
        print(f"Cash:              {portfolio['cash']:>15,.0f} VND")

        # Positions
        total_position_value = 0
        if portfolio['positions'] and current_prices:
            print(f"\nPositions:")
            print(f"  {'Symbol':<8} {'Qty':>8} {'Avg Price':>12} {'Current':>12} {'Value':>15} {'P&L':>12} {'P&L%':>8}")
            print(f"  {'-'*8} {'-'*8} {'-'*12} {'-'*12} {'-'*15} {'-'*12} {'-'*8}")

            for symbol, pos in sorted(portfolio['positions'].items()):
                qty = pos['quantity']
                avg_price = pos['avg_price']
                current_price = current_prices.get(symbol, avg_price)

                current_value = qty * current_price
                total_cost = qty * avg_price
                pnl = current_value - total_cost
                pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0

                total_position_value += current_value

                print(f"  {symbol:<8} {qty:>8} {avg_price:>12,.0f} {current_price:>12,.0f} "
                      f"{current_value:>15,.0f} {pnl:>12,.0f} {pnl_pct:>7.2f}%")

        elif portfolio['positions']:
            print(f"\nPositions: {len(portfolio['positions'])} (need current prices to show details)")
            # Estimate from avg price
            for symbol, pos in portfolio['positions'].items():
                total_position_value += pos['quantity'] * pos['avg_price']

        # Total
        total_equity = portfolio['cash'] + total_position_value
        total_return = total_equity - self.initial_capital
        total_return_pct = (total_return / self.initial_capital * 100)

        print(f"\n  {'TOTAL POSITIONS':>30}: {total_position_value:>15,.0f} VND")
        print(f"  {'TOTAL EQUITY':>30}: {total_equity:>15,.0f} VND")
        print(f"  {'TOTAL RETURN':>30}: {total_return:>15,.0f} VND ({total_return_pct:+.2f}%)")

        # Performance metrics
        if days_trading > 0:
            print("\n" + "-"*80)
            print("PERFORMANCE METRICS")
            print("-"*80)

            # Daily return
            daily_return = total_return_pct / days_trading
            print(f"Daily avg return:   {daily_return:>10.3f}%")

            # Annualized return (252 trading days)
            annual_return = daily_return * 252
            print(f"Annualized return:  {annual_return:>10.2f}%")

            # Load trades for more metrics
            trades_df = pd.read_csv(self.trades_file, encoding='utf-8-sig')
            if len(trades_df) > 0:
                num_trades = len(trades_df)
                buy_trades = len(trades_df[trades_df['action'] == 'BUY'])
                sell_trades = len(trades_df[trades_df['action'] == 'SELL'])

                print(f"\nTotal trades:       {num_trades:>10}")
                print(f"  Buys:             {buy_trades:>10}")
                print(f"  Sells:            {sell_trades:>10}")

                # Calculate win rate (from completed trades)
                if sell_trades > 0:
                    # Match buys and sells to calculate wins
                    completed_trades = self._calculate_completed_trades(trades_df)
                    if completed_trades:
                        wins = sum(1 for t in completed_trades if t['pnl'] > 0)
                        win_rate = wins / len(completed_trades) * 100
                        avg_pnl = np.mean([t['pnl_pct'] for t in completed_trades])

                        print(f"\nCompleted trades:   {len(completed_trades):>10}")
                        print(f"Win rate:           {win_rate:>10.1f}%")
                        print(f"Avg P&L per trade:  {avg_pnl:>10.2f}%")

        print("\n" + "="*80)

    def _calculate_completed_trades(self, trades_df):
        """Calculate P&L for completed buy-sell pairs"""
        completed = []

        # Group by symbol
        for symbol in trades_df['symbol'].unique():
            symbol_trades = trades_df[trades_df['symbol'] == symbol].sort_values('date')

            # Simple FIFO matching
            buys = symbol_trades[symbol_trades['action'] == 'BUY'].to_dict('records')
            sells = symbol_trades[symbol_trades['action'] == 'SELL'].to_dict('records')

            for sell in sells:
                if buys:
                    buy = buys.pop(0)
                    pnl = (sell['price'] - buy['price']) * sell['quantity']
                    pnl_pct = (sell['price'] - buy['price']) / buy['price'] * 100

                    completed.append({
                        'symbol': symbol,
                        'buy_date': buy['date'],
                        'sell_date': sell['date'],
                        'buy_price': buy['price'],
                        'sell_price': sell['price'],
                        'quantity': sell['quantity'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })

        return completed

    def show_trades_history(self, last_n=20):
        """Show recent trades"""

        trades_df = pd.read_csv(self.trades_file, encoding='utf-8-sig')

        if len(trades_df) == 0:
            print("\nNo trades yet.")
            return

        print("\n" + "="*80)
        print(f"TRADE HISTORY (Last {last_n})")
        print("="*80)

        recent = trades_df.tail(last_n)
        print(recent[['date', 'symbol', 'action', 'quantity', 'price', 'total_amount', 'note']].to_string(index=False))

    def export_report(self, filename=None):
        """Export detailed report"""

        if filename is None:
            filename = f"paper_trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            # Redirect print to file
            import sys
            old_stdout = sys.stdout
            sys.stdout = f

            self.show_dashboard()
            self.show_trades_history(last_n=100)

            sys.stdout = old_stdout

        print(f"\n[Report exported] {filename}")


# Example usage and CLI
def main():
    """Command-line interface for dashboard"""

    import argparse

    parser = argparse.ArgumentParser(description='Paper Trading Dashboard')
    parser.add_argument('--init', action='store_true', help='Initialize new portfolio')
    parser.add_argument('--buy', nargs=3, metavar=('SYMBOL', 'QTY', 'PRICE'), help='Buy stock')
    parser.add_argument('--sell', nargs=3, metavar=('SYMBOL', 'QTY', 'PRICE'), help='Sell stock')
    parser.add_argument('--show', action='store_true', help='Show dashboard')
    parser.add_argument('--history', action='store_true', help='Show trade history')
    parser.add_argument('--report', action='store_true', help='Export report')

    args = parser.parse_args()

    dashboard = PaperTradingDashboard()

    if args.init:
        print("[Initialized] Paper trading portfolio")

    elif args.buy:
        symbol, qty, price = args.buy
        dashboard.add_trade(symbol, 'BUY', int(qty), float(price))

    elif args.sell:
        symbol, qty, price = args.sell
        dashboard.add_trade(symbol, 'SELL', int(qty), float(price))

    elif args.history:
        dashboard.show_trades_history()

    elif args.report:
        dashboard.export_report()

    else:
        # Default: show dashboard
        # Try to load current prices from latest data
        try:
            current_prices = {}
            passed_stocks = ['ACB', 'MBB', 'SSI', 'STB', 'TCB', 'TPB']

            for symbol in passed_stocks:
                data_file = Path(f'data/historical/{symbol}.parquet')
                if data_file.exists():
                    df = pd.read_parquet(data_file)
                    current_prices[symbol] = df['close'].iloc[-1]

            dashboard.show_dashboard(current_prices)
        except:
            dashboard.show_dashboard()


if __name__ == '__main__':
    main()
