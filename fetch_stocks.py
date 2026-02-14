"""
Multi-Stock EMA Slope Screener
Scans stocks and finds bullish trends
"""

import yfinance as yf
import pandas as pd
from datetime import datetime

# List of stocks to scan (Nifty 50 sample)
STOCKS = [
    'RELIANCE.NS',
    'TCS.NS',
    'HDFCBANK.NS',
    'INFY.NS',
    'ICICIBANK.NS',
    'HINDUNILVR.NS',
    'ITC.NS',
    'SBIN.NS',
    'BHARTIARTL.NS',
    'KOTAKBANK.NS',
    'LT.NS',
    'AXISBANK.NS',
    'ASIANPAINT.NS',
    'MARUTI.NS',
    'TITAN.NS'
]

def calculate_ema_slope(ticker_symbol, ema_period=20, lookback=3):
    """
    Calculate if EMA is rising or falling
    Returns: True if rising (bullish), False if falling
    """
    try:
        # Fetch data
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period='3mo')  # Get 3 months
        
        if len(data) < ema_period + lookback:
            return None  # Not enough data
        
        # Calculate EMA
        data['EMA'] = data['Close'].ewm(span=ema_period, adjust=False).mean()
        
        # Get current and past EMA
        ema_now = data['EMA'].iloc[-1]
        ema_past = data['EMA'].iloc[-(lookback + 1)]
        
        # Check if rising
        is_rising = ema_now > ema_past
        
        return is_rising
        
    except Exception as e:
        print(f"Error fetching {ticker_symbol}: {e}")
        return None

def screen_stocks():
    """
    Screen all stocks and find bullish ones
    """
    print("="*60)
    print(f"EMA SLOPE SCREENER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)
    print(f"\nScanning {len(STOCKS)} stocks...\n")
    
    bullish_stocks = []
    bearish_stocks = []
    
    for i, stock in enumerate(STOCKS, 1):
        # Show progress
        print(f"[{i}/{len(STOCKS)}] Checking {stock}...", end=' ')
        
        result = calculate_ema_slope(stock)
        
        if result is None:
            print("❓ No data")
        elif result:
            print("✅ BULLISH")
            bullish_stocks.append(stock)
        else:
            print("❌ Bearish")
            bearish_stocks.append(stock)
    
    # Show results
    print("\n" + "="*60)
    print("RESULTS:")
    print("="*60)
    
    print(f"\n✅ BULLISH STOCKS ({len(bullish_stocks)}):")
    if bullish_stocks:
        for stock in bullish_stocks:
            print(f"  • {stock.replace('.NS', '')}")
    else:
        print("  None found")
    
    print(f"\n❌ BEARISH STOCKS ({len(bearish_stocks)}):")
    if bearish_stocks:
        for stock in bearish_stocks:
            print(f"  • {stock.replace('.NS', '')}")
    else:
        print("  None found")
    
    print("\n" + "="*60)
    print(f"✅ {len(bullish_stocks)} bullish | ❌ {len(bearish_stocks)} bearish")
    print("="*60)
    
    return bullish_stocks

# Run the screener
if __name__ == "__main__":
    bullish_list = screen_stocks()
