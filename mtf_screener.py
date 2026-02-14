"""
Multi-Timeframe EMA Slope Screener
Checks EMA slope across multiple timeframes
"""

import yfinance as yf
import pandas as pd

STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS'
]

def check_ema_slope_mtf(ticker_symbol, ema_period=20):
    """
    Check EMA slope across multiple timeframes
    Returns: dict with timeframe results
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Define timeframes
        timeframes = {
            '1D': ticker.history(period='3mo', interval='1d'),
            '1W': ticker.history(period='1y', interval='1wk'),
            '1M': ticker.history(period='2y', interval='1mo')
        }
        
        results = {}
        
        for tf_name, data in timeframes.items():
            if len(data) < ema_period + 3:
                results[tf_name] = None
                continue
            
            # Calculate EMA
            data['EMA'] = data['Close'].ewm(span=ema_period, adjust=False).mean()
            
            # Check slope
            ema_now = data['EMA'].iloc[-1]
            ema_past = data['EMA'].iloc[-4]
            
            results[tf_name] = ema_now > ema_past
        
        return results
        
    except Exception as e:
        return None

def screen_multi_timeframe():
    """
    Screen stocks across multiple timeframes
    """
    print("="*70)
    print("MULTI-TIMEFRAME EMA SLOPE SCREENER")
    print("="*70)
    print(f"\nScanning {len(STOCKS)} stocks across 3 timeframes...\n")
    
    all_results = []
    
    for i, stock in enumerate(STOCKS, 1):
        print(f"[{i}/{len(STOCKS)}] {stock}...", end=' ')
        
        results = check_ema_slope_mtf(stock)
        
        if results is None:
            print("❓ Error")
            continue
        
        # Count bullish timeframes
        bullish_count = sum(1 for v in results.values() if v == True)
        
        # Display
        status_1d = "✅" if results.get('1D') else "❌"
        status_1w = "✅" if results.get('1W') else "❌"
        status_1m = "✅" if results.get('1M') else "❌"
        
        print(f"1D:{status_1d} 1W:{status_1w} 1M:{status_1m} ({bullish_count}/3)")
        
        all_results.append({
            'stock': stock,
            'bullish_count': bullish_count,
            'results': results
        })
    
    # Show stocks with all timeframes bullish
    print("\n" + "="*70)
    print("✅ STOCKS WITH ALL TIMEFRAMES BULLISH:")
    print("="*70)
    
    all_bullish = [r for r in all_results if r['bullish_count'] == 3]
    
    if all_bullish:
        for item in all_bullish:
            print(f"  🎯 {item['stock'].replace('.NS', '')} - ALL 3 TIMEFRAMES ALIGNED!")
    else:
        print("  None found")
    
    # Show stocks with 2/3 bullish
    print("\n" + "="*70)
    print("⚠️  STOCKS WITH 2/3 TIMEFRAMES BULLISH:")
    print("="*70)
    
    partial_bullish = [r for r in all_results if r['bullish_count'] == 2]
    
    if partial_bullish:
        for item in partial_bullish:
            print(f"  • {item['stock'].replace('.NS', '')}")
    else:
        print("  None found")
    
    print("\n" + "="*70)

# Run
if __name__ == "__main__":
    screen_multi_timeframe()
