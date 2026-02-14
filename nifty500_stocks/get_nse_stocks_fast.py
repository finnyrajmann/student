"""
Fast NSE Stock Filter with VISIBLE PROGRESS
Filters Nifty 500 stocks by:
1. Price >= ₹20
2. Has 2+ years data
"""

import yfinance as yf
from datetime import datetime
import time
from nifty500_stocks import get_nifty_500

def check_stock(symbol, min_price=20, min_years=2):
    """
    Check single stock
    Returns: (passed, price, years, error)
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3y')
        
        if len(hist) == 0:
            return (False, 0, 0, "No data")
        
        # Check price
        price = hist['Close'].iloc[-1]
        if price < min_price:
            return (False, price, 0, f"Price ₹{price:.0f} < ₹{min_price}")
        
        # Check years
        days = (hist.index[-1] - hist.index[0]).days
        years = days / 365
        
        if years < min_years:
            return (False, price, years, f"Only {years:.1f}y data")
        
        return (True, price, years, "OK")
        
    except Exception as e:
        return (False, 0, 0, f"Error: {str(e)[:30]}")

def filter_stocks_with_progress(symbols, min_price=20, min_years=2):
    """
    Filter stocks with VISIBLE PROGRESS
    """
    print("="*70)
    print(f"FILTERING {len(symbols)} NIFTY 500 STOCKS")
    print(f"Filters: Price >= ₹{min_price} | Data >= {min_years} years")
    print("="*70)
    print()
    
    valid = []
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        # Check stock
        passed, price, years, msg = check_stock(symbol, min_price, min_years)
        
        # Show progress EVERY stock (so you see activity!)
        stock_name = symbol.replace('.NS', '')
        
        if passed:
            print(f"[{i}/{len(symbols)}] {stock_name:15} ✅ ₹{price:7.2f} | {years:.1f}y")
            valid.append(symbol)
        else:
            print(f"[{i}/{len(symbols)}] {stock_name:15} ❌ {msg}")
        
        # Progress summary every 25 stocks
        if i % 25 == 0:
            elapsed = (time.time() - start_time) / 60
            rate = i / (time.time() - start_time)
            remaining = (len(symbols) - i) / rate / 60
            
            print(f"\n--- Progress: {i}/{len(symbols)} | "
                  f"{len(valid)} valid | "
                  f"~{int(remaining)}min left ---\n")
        
        # Rate limit protection
        if i % 5 == 0:
            time.sleep(0.2)
    
    total_time = (time.time() - start_time) / 60
    
    print(f"\n{'='*70}")
    print(f"COMPLETE in {total_time:.1f} minutes")
    print(f"{'='*70}")
    print(f"✅ {len(valid)}/{len(symbols)} stocks passed")
    print(f"❌ {len(symbols) - len(valid)} stocks filtered out")
    print(f"{'='*70}")
    
    return valid

def save_to_file(stocks, filename='nse_stocks_filtered.txt'):
    """Save stock list"""
    with open(filename, 'w') as f:
        for stock in stocks:
            f.write(f"{stock}\n")
    
    print(f"\n💾 Saved to: {filename}")
    print(f"\nFirst 10 stocks:")
    for i, stock in enumerate(stocks[:10], 1):
        print(f"  {i}. {stock.replace('.NS', '')}")
    
    if len(stocks) > 10:
        print(f"  ... and {len(stocks) - 10} more")

# Main
if __name__ == "__main__":
    print("\n" + "="*70)
    print("NIFTY 500 STOCK FILTER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Get Nifty 500
    stocks = get_nifty_500()
    print(f"\n✅ Loaded {len(stocks)} Nifty 500 stocks\n")
    
    # Filter
    valid = filter_stocks_with_progress(stocks, min_price=20, min_years=2)
    
    # Save
    save_to_file(valid)
    
    print(f"\n{'='*70}")
    print("✅ DONE!")
    print(f"{'='*70}")
    print(f"\nNext: Run 'python screener.py' to scan these stocks")
    print(f"{'='*70}\n")
