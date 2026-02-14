"""
Complete Stock Screener
Reads stock list from: nse_stocks_filtered.txt
Applies technical + fundamental filters
"""

import yfinance as yf
from datetime import datetime
import time

def load_stock_list(filename='nse_stocks_filtered.txt'):
    """Load stock list from file"""
    try:
        with open(filename, 'r') as f:
            stocks = [line.strip() for line in f if line.strip()]
        
        print(f"✅ Loaded {len(stocks)} stocks from {filename}\n")
        return stocks
        
    except FileNotFoundError:
        print(f"❌ Error: {filename} not found!")
        print(f"   Please run 'python get_nse_stocks_fast.py' first")
        return []

def check_ema_slope_mtf(ticker, ema_period=20):
    """Check EMA slope across multiple timeframes"""
    try:
        data_1d = ticker.history(period='3mo', interval='1d')
        data_1w = ticker.history(period='1y', interval='1wk')
        data_1m = ticker.history(period='2y', interval='1mo')
        
        results = {}
        
        # Daily
        if len(data_1d) >= ema_period + 3:
            data_1d['EMA'] = data_1d['Close'].ewm(span=ema_period, adjust=False).mean()
            results['1D'] = data_1d['EMA'].iloc[-1] > data_1d['EMA'].iloc[-4]
        
        # Weekly
        if len(data_1w) >= ema_period + 3:
            data_1w['EMA'] = data_1w['Close'].ewm(span=ema_period, adjust=False).mean()
            results['1W'] = data_1w['EMA'].iloc[-1] > data_1w['EMA'].iloc[-3]
        
        # Monthly
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
        
        # Convert Debt/Equity if in percentage
        if fundamentals['DE'] and fundamentals['DE'] > 100:
            fundamentals['DE'] = fundamentals['DE'] / 100
        
        return fundamentals
    except:
        return {}

def passes_fundamental_filters(fundamentals):
    """Check if stock passes fundamental criteria"""
    
    min_roe = 12
    max_de = 1.5
    min_market_cap = 10000000000
    
    checks = {
        'roe_ok': False,
        'de_ok': False,
        'pb_ok': False,
        'cap_ok': False
    }
    
    # ROE check
    if fundamentals.get('ROE') and fundamentals['ROE'] >= min_roe:
        checks['roe_ok'] = True
    
    # Debt/Equity check
    if fundamentals.get('DE') is not None:
        if fundamentals['DE'] <= max_de:
            checks['de_ok'] = True
    else:
        checks['de_ok'] = True  # Accept if no debt data
    
    # P/B vs ROE check
    if fundamentals.get('ROE') and fundamentals.get('PB'):
        fair_pb = fundamentals['ROE'] / 10
        if fundamentals['PB'] <= fair_pb * 1.3:  # 30% premium allowed
            checks['pb_ok'] = True
    
    # Market cap check
    if fundamentals.get('MarketCap') and fundamentals['MarketCap'] >= min_market_cap:
        checks['cap_ok'] = True
    
    return checks

def screen_stocks(stock_list):
    """
    Two-stage screening:
    Stage 1: Technical (all stocks)
    Stage 2: Fundamentals (only technical winners)
    """
    
    print("="*70)
    print(f"STOCK SCREENER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    print(f"Scanning {len(stock_list)} stocks...")
    print()
    
    # STAGE 1: Technical screening
    print("STAGE 1: Technical Analysis (Multi-timeframe EMA)")
    print("-"*70)
    
    technical_pass = []
    start_time = time.time()
    
    for i, stock in enumerate(stock_list, 1):
        # Progress every 50 stocks
        if i % 50 == 0:
            elapsed = (time.time() - start_time) / 60
            rate = i / (time.time() - start_time)
            remaining = (len(stock_list) - i) / rate / 60
            print(f"[{i}/{len(stock_list)}] {len(technical_pass)} passed | ~{int(remaining)}min left")
        
        try:
            ticker = yf.Ticker(stock)
            ema_results = check_ema_slope_mtf(ticker)
            
            bullish_count = sum(1 for v in ema_results.values() if v == True)
            
            # Pass stocks with 2+ timeframes bullish
            if bullish_count >= 2:
                technical_pass.append({
                    'stock': stock,
                    'ticker': ticker,
                    'ema_results': ema_results,
                    'bullish_count': bullish_count,
                    'all_tf_bullish': bullish_count == 3
                })
        except:
            pass
        
        # Rate limit
        if i % 10 == 0:
            time.sleep(0.3)
    
    stage1_time = (time.time() - start_time) / 60
    
    print(f"\n✅ Stage 1 Complete in {stage1_time:.1f} minutes")
    print(f"   {len(technical_pass)}/{len(stock_list)} stocks passed technical filters\n")
    
    # STAGE 2: Fundamental screening
    print("="*70)
    print("STAGE 2: Fundamental Analysis")
    print("-"*70)
    
    results = []
    
    for i, item in enumerate(technical_pass, 1):
        stock_name = item['stock'].replace('.NS', '')
        print(f"[{i}/{len(technical_pass)}] {stock_name:15}...", end=' ')
        
        try:
            fundamentals = get_fundamentals(item['ticker'])
            fund_checks = passes_fundamental_filters(fundamentals)
            fund_pass_count = sum(1 for v in fund_checks.values() if v == True)
            
            results.append({
                'stock': item['stock'],
                'bullish_count': item['bullish_count'],
                'all_tf_bullish': item['all_tf_bullish'],
                'ema_results': item['ema_results'],
                'fundamentals': fundamentals,
                'fund_checks': fund_checks,
                'fund_pass_count': fund_pass_count,
                'strong_buy': item['all_tf_bullish'] and fund_pass_count >= 3
            })
            
            # Status
            if item['all_tf_bullish'] and fund_pass_count >= 3:
                print("🎯 STRONG BUY")
            elif item['all_tf_bullish']:
                print("⚠️  Check fundamentals")
            else:
                print("📋 Watch list")
                
        except Exception as e:
            print(f"❌ Error")
        
        time.sleep(0.2)
    
    total_time = (time.time() - start_time) / 60
    
    # FINAL RESULTS
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"Completed in {total_time:.1f} minutes")
    print("="*70)
    
    # Strong Buy
    strong_buy = [r for r in results if r['strong_buy']]
    print(f"\n🎯 STRONG BUY (All 3 TF + Good Fundamentals): {len(strong_buy)}")
    if strong_buy:
        for r in strong_buy:
            name = r['stock'].replace('.NS', '')
            roe = r['fundamentals'].get('ROE', 'N/A')
            pb = r['fundamentals'].get('PB', 'N/A')
            de = r['fundamentals'].get('DE', 'N/A')
            
            roe_str = f"{roe:.1f}%" if isinstance(roe, (int, float)) else "N/A"
            pb_str = f"{pb:.2f}" if isinstance(pb, (int, float)) else "N/A"
            de_str = f"{de:.2f}" if isinstance(de, (int, float)) else "N/A"
            
            print(f"  • {name:15} ROE:{roe_str:8} P/B:{pb_str:6} D/E:{de_str}")
    else:
        print("  None found")
    
    # Good Technical
    good_tech = [r for r in results if r['all_tf_bullish'] and not r['strong_buy']]
    print(f"\n⚠️  GOOD TECHNICAL (Review Fundamentals Manually): {len(good_tech)}")
    if good_tech:
        for r in good_tech[:10]:  # Show first 10
            print(f"  • {r['stock'].replace('.NS', '')}")
        if len(good_tech) > 10:
            print(f"  ... and {len(good_tech) - 10} more")
    
    # Watch List
    watch_list = [r for r in results if r['bullish_count'] == 2 and r['fund_pass_count'] >= 3]
    print(f"\n📋 WATCH LIST (2/3 TF + Good Fundamentals): {len(watch_list)}")
    if watch_list:
        for r in watch_list[:10]:  # Show first 10
            print(f"  • {r['stock'].replace('.NS', '')}")
        if len(watch_list) > 10:
            print(f"  ... and {len(watch_list) - 10} more")
    
    print(f"\n{'='*70}")
    print(f"Summary: {len(stock_list)} scanned → {len(strong_buy)} Strong Buy | "
          f"{len(good_tech)} Good Tech | {len(watch_list)} Watch List")
    print("="*70)
    
    return results

# Main
if __name__ == "__main__":
    print("\n")
    
    # Load stocks
    stocks = load_stock_list('nse_stocks_filtered.txt')
    
    if not stocks:
        print("\n❌ No stocks to scan. Exiting.\n")
        exit()
    
    # Run screener
    results = screen_stocks(stocks)
    
    print("\n✅ Screening complete!\n")
