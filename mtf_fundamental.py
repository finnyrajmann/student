"""
Complete Stock Screener
Technical (Multi-timeframe EMA) + Fundamentals (ROE, P/B, Debt)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime

# Stocks to scan
STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'TITAN.NS',
    'WIPRO.NS', 'ULTRACEMCO.NS', 'BAJFINANCE.NS', 'SUNPHARMA.NS', 'TECHM.NS'
]

def check_ema_slope_mtf(ticker, ema_period=20):
    """Check EMA slope across multiple timeframes"""
    try:
        # Get data for different timeframes
        data_1d = ticker.history(period='3mo', interval='1d')
        data_1w = ticker.history(period='1y', interval='1wk')
        data_1m = ticker.history(period='2y', interval='1mo')
        
        results = {}
        
        # Check daily
        if len(data_1d) >= ema_period + 3:
            data_1d['EMA'] = data_1d['Close'].ewm(span=ema_period, adjust=False).mean()
            results['1D'] = data_1d['EMA'].iloc[-1] > data_1d['EMA'].iloc[-4]
        
        # Check weekly
        if len(data_1w) >= ema_period + 3:
            data_1w['EMA'] = data_1w['Close'].ewm(span=ema_period, adjust=False).mean()
            results['1W'] = data_1w['EMA'].iloc[-1] > data_1w['EMA'].iloc[-3]
        
        # Check monthly
        if len(data_1m) >= ema_period + 3:
            data_1m['EMA'] = data_1m['Close'].ewm(span=ema_period, adjust=False).mean()
            results['1M'] = data_1m['EMA'].iloc[-1] > data_1m['EMA'].iloc[-3]
        
        return results
    except:
        return {}

def get_fundamentals(ticker):
    """Get fundamental data"""
    try:
        info = ticker.info
        
        fundamentals = {
            'ROE': info.get('returnOnEquity', None),
            'PB': info.get('priceToBook', None),
            'DE': info.get('debtToEquity', None),
            'PE': info.get('trailingPE', None),
            'MarketCap': info.get('marketCap', None)
        }
        
        # Convert ROE to percentage
        if fundamentals['ROE']:
            fundamentals['ROE'] = fundamentals['ROE'] * 100
        
        # Convert Debt/Equity (sometimes in percentage)
        if fundamentals['DE'] and fundamentals['DE'] > 100:
            fundamentals['DE'] = fundamentals['DE'] / 100
        
        return fundamentals
    except:
        return {}

def passes_fundamental_filters(fundamentals):
    """Check if stock passes fundamental criteria"""
    
    # Define criteria
    min_roe = 12  # Minimum 12% ROE
    max_de = 1.5  # Maximum 1.5 Debt/Equity
    min_market_cap = 10000000000  # Min 10,000 crores (in rupees, roughly)
    
    checks = {
        'roe_ok': False,
        'de_ok': False,
        'pb_ok': False,
        'cap_ok': False
    }
    
    # Check ROE
    if fundamentals.get('ROE') and fundamentals['ROE'] >= min_roe:
        checks['roe_ok'] = True
    
    # Check Debt/Equity
    if fundamentals.get('DE') is not None:
        if fundamentals['DE'] <= max_de:
            checks['de_ok'] = True
    else:
        checks['de_ok'] = True  # Accept if no debt data (might be debt-free)
    
    # Check P/B vs ROE (Fair P/B = ROE/10)
    if fundamentals.get('ROE') and fundamentals.get('PB'):
        fair_pb = fundamentals['ROE'] / 10
        if fundamentals['PB'] <= fair_pb * 1.3:  # Allow 30% premium
            checks['pb_ok'] = True
    
    # Check market cap
    if fundamentals.get('MarketCap') and fundamentals['MarketCap'] >= min_market_cap:
        checks['cap_ok'] = True
    
    return checks

def screen_complete():
    """Complete screener with technical + fundamental filters"""
    
    print("="*80)
    print(f"COMPLETE STOCK SCREENER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Technical: Multi-timeframe EMA | Fundamental: ROE, P/B, Debt/Equity")
    print("="*80)
    print(f"\nScanning {len(STOCKS)} stocks...\n")
    
    results = []
    
    for i, stock_symbol in enumerate(STOCKS, 1):
        print(f"\n[{i}/{len(STOCKS)}] {stock_symbol.replace('.NS', '')}:")
        
        try:
            ticker = yf.Ticker(stock_symbol)
            
            # Technical analysis
            print("  📊 Technical...", end=' ')
            ema_results = check_ema_slope_mtf(ticker)
            bullish_count = sum(1 for v in ema_results.values() if v == True)
            
            status_1d = "✅" if ema_results.get('1D') else "❌"
            status_1w = "✅" if ema_results.get('1W') else "❌"
            status_1m = "✅" if ema_results.get('1M') else "❌"
            
            print(f"1D:{status_1d} 1W:{status_1w} 1M:{status_1m}")
            
            # Only check fundamentals if at least 2/3 timeframes bullish
            if bullish_count >= 2:
                print("  💰 Fundamentals...", end=' ')
                fundamentals = get_fundamentals(ticker)
                fund_checks = passes_fundamental_filters(fundamentals)
                
                # Display fundamentals
                roe = fundamentals.get('ROE', 'N/A')
                pb = fundamentals.get('PB', 'N/A')
                de = fundamentals.get('DE', 'N/A')
                
                if isinstance(roe, float):
                    roe_str = f"{roe:.1f}%"
                else:
                    roe_str = "N/A"
                
                if isinstance(pb, float):
                    pb_str = f"{pb:.2f}"
                else:
                    pb_str = "N/A"
                
                if isinstance(de, float):
                    de_str = f"{de:.2f}"
                else:
                    de_str = "N/A"
                
                print(f"ROE:{roe_str} P/B:{pb_str} D/E:{de_str}")
                
                # Check if passes all filters
                fund_pass_count = sum(1 for v in fund_checks.values() if v == True)
                
                results.append({
                    'stock': stock_symbol,
                    'bullish_tf': bullish_count,
                    'ema_results': ema_results,
                    'fundamentals': fundamentals,
                    'fund_checks': fund_checks,
                    'fund_pass_count': fund_pass_count,
                    'all_tf_bullish': bullish_count == 3,
                    'fund_ok': fund_pass_count >= 3
                })
                
                # Show status
                if bullish_count == 3 and fund_pass_count >= 3:
                    print("  🎯 STRONG BUY CANDIDATE!")
                elif bullish_count == 3:
                    print("  ⚠️  Good technical, check fundamentals manually")
                elif fund_pass_count >= 3:
                    print("  ⚠️  Good fundamentals, wait for technical alignment")
            else:
                print("  ⏭️  Skipped (technical not bullish)")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Final results
    print("\n" + "="*80)
    print("FINAL RESULTS:")
    print("="*80)
    
    # Best candidates (all timeframes + good fundamentals)
    best = [r for r in results if r['all_tf_bullish'] and r['fund_ok']]
    
    print(f"\n🎯 STRONG BUY CANDIDATES (All TF Bullish + Good Fundamentals): {len(best)}")
    if best:
        for item in best:
            stock_name = item['stock'].replace('.NS', '')
            roe = item['fundamentals'].get('ROE', 'N/A')
            pb = item['fundamentals'].get('PB', 'N/A')
            
            roe_str = f"{roe:.1f}%" if isinstance(roe, float) else "N/A"
            pb_str = f"{pb:.2f}" if isinstance(pb, float) else "N/A"
            
            print(f"  • {stock_name:15} ROE:{roe_str:8} P/B:{pb_str}")
    else:
        print("  None found")
    
    # Good technical, need to verify fundamentals
    good_tech = [r for r in results if r['all_tf_bullish'] and not r['fund_ok']]
    
    print(f"\n⚠️  GOOD TECHNICAL, CHECK FUNDAMENTALS MANUALLY: {len(good_tech)}")
    if good_tech:
        for item in good_tech:
            print(f"  • {item['stock'].replace('.NS', '')}")
    
    # Partial signals
    partial = [r for r in results if r['bullish_tf'] == 2 and r['fund_ok']]
    
    print(f"\n📋 WATCH LIST (2/3 TF + Good Fundamentals): {len(partial)}")
    if partial:
        for item in partial:
            print(f"  • {item['stock'].replace('.NS', '')}")
    
    print("\n" + "="*80)
    print(f"Total analyzed: {len(results)} stocks")
    print("="*80)

# Run
if __name__ == "__main__":
    screen_complete()
