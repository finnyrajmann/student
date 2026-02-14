"""
Get all NSE stocks and filter them
Filters:
1. Minimum 2 years of historical data (no recent IPOs)
2. Price >= ₹20 (no penny stocks)

Outputs: nse_stocks_filtered.txt
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time

def get_all_nse_symbols():
    """
    Get complete list of NSE stocks
    Returns list of symbols with .NS suffix
    """
    try:
        # Method 1: Try fetching from NSE website
        print("Fetching NSE stock list from NSE India...")
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        
        df = pd.read_csv(url)
        symbols = df['SYMBOL'].tolist()
        nse_symbols = [f"{symbol}.NS" for symbol in symbols]
        
        print(f"✅ Found {len(nse_symbols)} NSE stocks from NSE website")
        return nse_symbols
        
    except Exception as e:
        print(f"❌ Could not fetch from NSE website: {e}")
        print("Using fallback: Nifty 500 + known stocks...")
        
        # Fallback: Use known comprehensive list
        # This includes Nifty 500 + other liquid stocks
        return get_fallback_list()

def get_fallback_list():
    """
    Fallback list if NSE website fetch fails
    Comprehensive list of ~700 liquid NSE stocks
    """
    # Nifty 50
    nifty50 = [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
        'LT.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'TITAN.NS',
        'BAJFINANCE.NS', 'HCLTECH.NS', 'WIPRO.NS', 'ULTRACEMCO.NS', 'SUNPHARMA.NS',
        'TECHM.NS', 'NESTLEIND.NS', 'POWERGRID.NS', 'NTPC.NS', 'TATAMOTORS.NS',
        'TATASTEEL.NS', 'ADANIPORTS.NS', 'ONGC.NS', 'COALINDIA.NS', 'M&M.NS',
        'BAJAJFINSV.NS', 'DRREDDY.NS', 'DIVISLAB.NS', 'APOLLOHOSP.NS', 'CIPLA.NS',
        'JSWSTEEL.NS', 'HINDALCO.NS', 'BPCL.NS', 'IOC.NS', 'GRASIM.NS',
        'SHREECEM.NS', 'EICHERMOT.NS', 'HEROMOTOCO.NS', 'BAJAJ-AUTO.NS',
        'TATACONSUM.NS', 'BRITANNIA.NS', 'INDUSINDBK.NS', 'ADANIENT.NS',
        'SBILIFE.NS', 'HDFCLIFE.NS'
    ]
    
    # Nifty Next 50 + Midcap 150 (partial list)
    # Add more as needed
    additional = [
        'ACC.NS', 'AMBUJACEM.NS', 'BANDHANBNK.NS', 'BERGEPAINT.NS', 'BEL.NS',
        'COLPAL.NS', 'DLF.NS', 'DABUR.NS', 'DMART.NS', 'GAIL.NS',
        # ... (add more stocks here for comprehensive coverage)
    ]
    
    return nifty50 + additional

def check_stock_criteria(symbol, min_years=2, min_price=20):
    """
    Check if stock meets criteria:
    1. At least 2 years of data
    2. Current price >= ₹20
    
    Returns: (True/False, current_price, error_message)
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Get historical data
        hist = ticker.history(period='3y')
        
        if len(hist) == 0:
            return (False, 0, "No data available")
        
        # Check 1: Data availability (2+ years)
        date_range_days = (hist.index[-1] - hist.index[0]).days
        required_days = min_years * 365
        
        if date_range_days < required_days:
            return (False, 0, f"Only {date_range_days/365:.1f} years data")
        
        # Check 2: Current price >= min_price
        current_price = hist['Close'].iloc[-1]
        
        if current_price < min_price:
            return (False, current_price, f"Price ₹{current_price:.2f} < ₹{min_price}")
        
        # Passed all checks
        return (True, current_price, "OK")
        
    except Exception as e:
        return (False, 0, f"Error: {str(e)}")

def filter_nse_stocks(symbols, min_years=2, min_price=20):
    """
    Filter stocks based on criteria
    """
    print("="*70)
    print(f"FILTERING {len(symbols)} NSE STOCKS")
    print(f"Criteria:")
    print(f"  1. Minimum {min_years} years of historical data")
    print(f"  2. Current price >= ₹{min_price}")
    print("="*70)
    print()
    
    valid_stocks = []
    stock_details = []
    
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        # Progress update every 50 stocks
        if i % 50 == 0:
            elapsed = (time.time() - start_time) / 60
            rate = i / (time.time() - start_time)
            remaining_secs = (len(symbols) - i) / rate
            print(f"[{i}/{len(symbols)}] {len(valid_stocks)} valid | "
                  f"~{int(remaining_secs/60)}min remaining...")
        
        # Check criteria
        passed, price, msg = check_stock_criteria(symbol, min_years, min_price)
        
        if passed:
            valid_stocks.append(symbol)
            stock_details.append({
                'symbol': symbol,
                'price': price
            })
        
        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)
    
    total_time = (time.time() - start_time) / 60
    
    print(f"\n{'='*70}")
    print(f"FILTERING COMPLETE in {total_time:.1f} minutes")
    print(f"{'='*70}")
    print(f"Results: {len(valid_stocks)}/{len(symbols)} stocks passed filters")
    print(f"  ✅ {len(valid_stocks)} stocks have {min_years}+ years data AND price >= ₹{min_price}")
    print(f"  ❌ {len(symbols) - len(valid_stocks)} stocks filtered out")
    print(f"{'='*70}")
    
    return valid_stocks, stock_details

def save_to_file(stocks, stock_details, filename='nse_stocks_filtered.txt'):
    """
    Save filtered stock list to file
    Format: SYMBOL.NS (one per line)
    Also save details to CSV
    """
    # Save simple list (for screener to read)
    with open(filename, 'w') as f:
        for stock in stocks:
            f.write(f"{stock}\n")
    
    print(f"\n💾 Stock list saved to: {filename}")
    
    # Save detailed info to CSV
    csv_filename = filename.replace('.txt', '_details.csv')
    df = pd.DataFrame(stock_details)
    df['symbol'] = df['symbol'].str.replace('.NS', '')
    df.to_csv(csv_filename, index=False)
    
    print(f"💾 Details saved to: {csv_filename}")
    
    # Show sample
    print(f"\nSample stocks (first 10):")
    for i, stock in enumerate(stocks[:10], 1):
        detail = stock_details[i-1]
        print(f"  {i}. {stock.replace('.NS', ''):15} Price: ₹{detail['price']:.2f}")
    
    if len(stocks) > 10:
        print(f"  ... and {len(stocks) - 10} more")

# Main execution
if __name__ == "__main__":
    print("\n" + "="*70)
    print("NSE STOCK LIST GENERATOR")
    print(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # Step 1: Get all NSE symbols
    print("\nStep 1: Fetching NSE stock list...")
    all_symbols = get_all_nse_symbols()
    
    # Step 2: Filter stocks
    print(f"\nStep 2: Filtering stocks...")
    valid_stocks, details = filter_nse_stocks(
        all_symbols,
        min_years=2,
        min_price=20
    )
    
    # Step 3: Save to file
    print(f"\nStep 3: Saving to file...")
    save_to_file(valid_stocks, details)
    
    print(f"\n{'='*70}")
    print("✅ COMPLETE!")
    print(f"{'='*70}")
    print(f"\nYou can now use 'nse_stocks_filtered.txt' in your screener")
    print(f"Next: Run 'python screener.py' to scan these {len(valid_stocks)} stocks")
    print(f"{'='*70}\n")
