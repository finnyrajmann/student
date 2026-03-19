"""
NSE Backtest — Entry/Exit Simulation v3
=========================================
Changes from v2:
- Added multi-timeframe EMA slope check at entry
  (daily + weekly EMA20 must both be sloping up)
- This prevents entering stocks in downtrend

Input  : watchlist.csv
Output : backtest_trades.csv
         backtest_summary.csv
         capital_curve.csv
"""

import yfinance as yf
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
from math import floor


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
INPUT_FILE        = "watchlist.csv"
TRADES_FILE       = "backtest_trades.csv"
SUMMARY_FILE      = "backtest_summary.csv"
CACHE_DIR         = "data"

START_DATE        = "2025-01-01"
END_DATE          = "2025-12-31"

# Capital management
STARTING_CAPITAL  = 50000
CAPITAL_PER_TRADE = 10000
MAX_POSITIONS     = 5

# Minimum hold before exit can trigger
MIN_HOLD_DAYS     = 3

# Indicators
RSI_PERIOD        = 14
EMA_PERIOD        = 20
BB_PERIOD         = 20
BB_STD            = 2
VOLUME_PERIOD     = 125

# Entry thresholds
RSI_MIN           = 40
RSI_MAX           = 55
EMA_DIST_MAX      = 3.0
RVOL_MIN          = 0.75

# Exit thresholds
RSI_OVERBOUGHT    = 75
RSI_OVERSOLD      = 35
RVOL_SELL         = 1.5
EMA_BREACH_PCT    = 1.0


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def nse(symbol):
    return f"{symbol.upper().strip()}.NS"


def load_watchlist(filepath):
    df = pd.read_csv(filepath)
    print(f"Loaded {len(df)} stocks from {filepath}")
    return df['Symbol'].tolist()


# ─────────────────────────────────────────────
# DATA CACHE
# ─────────────────────────────────────────────
def fetch_all_data(symbols):
    os.makedirs(CACHE_DIR, exist_ok=True)
    all_data = {}

    print(f"\nFetching data for {len(symbols)} stocks...")

    fetch_start = str(
        (datetime.strptime(START_DATE, "%Y-%m-%d")
         - timedelta(days=365)).date()
    )

    for symbol in symbols:
        cache_file = os.path.join(CACHE_DIR, f"{symbol}.csv")
        use_cache  = False

        if os.path.exists(cache_file):
            age = datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(cache_file)
            )
            if age.total_seconds() < 86400:
                use_cache = True

        if use_cache:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            print(f"  {symbol}: loaded from cache ({len(df)} days)")
        else:
            try:
                ticker = yf.Ticker(nse(symbol))
                df     = ticker.history(start=fetch_start, end=END_DATE)
                if df.empty or len(df) < 250:
                    print(f"  {symbol}: insufficient data — skipping")
                    continue
                df.index = df.index.tz_localize(None)
                df.to_csv(cache_file)
                print(f"  {symbol}: fetched {len(df)} days")
                time.sleep(0.3)
            except Exception as e:
                print(f"  {symbol}: error — {e}")
                continue

        all_data[symbol] = df

    print(f"Data ready for {len(all_data)} stocks")
    return all_data


# ─────────────────────────────────────────────
# CALCULATE INDICATORS
# ─────────────────────────────────────────────
def calc_indicators(df, date):
    try:
        sub    = df[df.index <= date].copy()
        if len(sub) < BB_PERIOD + RSI_PERIOD + 5:
            return None

        close  = sub['Close']
        volume = sub['Volume']

        # RSI
        delta  = close.diff()
        gain   = delta.where(delta > 0, 0).ewm(span=RSI_PERIOD, adjust=False).mean()
        loss   = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
        rs     = gain / loss
        sub['RSI'] = 100 - (100 / (1 + rs))

        # EMA20
        sub['EMA20'] = close.ewm(span=EMA_PERIOD, adjust=False).mean()

        # Bollinger Bands
        sub['BB_Mid']   = close.rolling(BB_PERIOD).mean()
        sub['BB_Std']   = close.rolling(BB_PERIOD).std()
        sub['BB_Upper'] = sub['BB_Mid'] + BB_STD * sub['BB_Std']
        sub['BB_Lower'] = sub['BB_Mid'] - BB_STD * sub['BB_Std']

        # RVOL
        sub['AvgVol'] = volume.rolling(VOLUME_PERIOD).mean()
        sub['RVOL']   = volume / sub['AvgVol']

        # ── EMA slope — daily ──
        ema_slope_daily = bool(
            sub['EMA20'].iloc[-1] > sub['EMA20'].iloc[-2]
        )

        # ── EMA slope — weekly ──
        # Resample daily close to weekly and compute EMA20 on weekly
        try:
            weekly_close    = sub['Close'].resample('W').last().dropna()
            if len(weekly_close) >= EMA_PERIOD + 2:
                weekly_ema      = weekly_close.ewm(
                    span=EMA_PERIOD, adjust=False
                ).mean()
                ema_slope_weekly = bool(
                    weekly_ema.iloc[-1] > weekly_ema.iloc[-2]
                )
            else:
                ema_slope_weekly = False
        except Exception:
            ema_slope_weekly = False

        latest = sub.iloc[-1]
        prev   = sub.iloc[-2]

        price    = float(latest['Close'])
        ema20    = float(latest['EMA20'])
        rsi      = float(latest['RSI'])
        bb_upper = float(latest['BB_Upper'])
        bb_mid   = float(latest['BB_Mid'])
        bb_lower = float(latest['BB_Lower'])
        rvol     = float(latest['RVOL'])
        ema_dist = abs(price - ema20) / ema20 * 100
        change   = (price - float(prev['Close'])) / float(prev['Close']) * 100

        return {
            'price':             price,
            'change':            change,
            'rsi':               rsi,
            'ema20':             ema20,
            'ema_dist':          ema_dist,
            'bb_upper':          bb_upper,
            'bb_mid':            bb_mid,
            'bb_lower':          bb_lower,
            'rvol':              rvol,
            'ema_slope_daily':   ema_slope_daily,
            'ema_slope_weekly':  ema_slope_weekly,
        }

    except Exception:
        return None


# ─────────────────────────────────────────────
# ENTRY CONDITIONS
# ─────────────────────────────────────────────
def check_entry(ind):
    # Trend filter — both daily and weekly EMA must slope up
    if not ind['ema_slope_daily']:
        return False
    if not ind['ema_slope_weekly']:
        return False

    # Entry zone conditions
    rsi_pass  = RSI_MIN <= ind['rsi'] <= RSI_MAX
    ema_pass  = ind['ema_dist'] <= EMA_DIST_MAX
    bb_pass   = ind['price'] <= ind['bb_mid']
    rvol_pass = ind['rvol'] >= RVOL_MIN

    return rsi_pass and ema_pass and bb_pass and rvol_pass


# ─────────────────────────────────────────────
# EXIT CONDITIONS
# ─────────────────────────────────────────────
def check_exit(ind, days_held):
    if days_held < MIN_HOLD_DAYS:
        return None, None

    # Profit exits
    if ind['rsi'] > RSI_OVERBOUGHT:
        return 'PROFIT', f"RSI overbought ({ind['rsi']:.1f})"
    if ind['price'] >= ind['bb_upper']:
        return 'PROFIT', f"Price at BB Upper ({ind['bb_upper']:.2f})"

    # Loss exits
    if ind['price'] < ind['ema20'] * (1 - EMA_BREACH_PCT / 100):
        return 'LOSS', f"Price {EMA_BREACH_PCT}%+ below EMA ({ind['ema20']:.2f})"
    if ind['rsi'] < RSI_OVERSOLD:
        return 'LOSS', f"RSI oversold ({ind['rsi']:.1f})"
    if ind['change'] < 0 and ind['rvol'] > RVOL_SELL:
        return 'LOSS', f"Heavy selling volume (RVOL {ind['rvol']:.2f})"

    return None, None


# ─────────────────────────────────────────────
# RUN BACKTEST
# ─────────────────────────────────────────────
def run_backtest(symbols, all_data):
    start  = datetime.strptime(START_DATE, "%Y-%m-%d")
    end    = datetime.strptime(END_DATE,   "%Y-%m-%d")

    sample     = list(all_data.values())[0]
    trade_days = sample[
        (sample.index >= start) &
        (sample.index <= end)
    ].index.tolist()

    print(f"\nSimulating {len(trade_days)} trading days "
          f"({START_DATE} to {END_DATE})...")
    print(f"Starting capital : ₹{STARTING_CAPITAL:,}")
    print(f"Capital/trade    : ₹{CAPITAL_PER_TRADE:,}")
    print(f"Max positions    : {MAX_POSITIONS}")
    print(f"Min hold days    : {MIN_HOLD_DAYS}")
    print(f"Trend filter     : Daily + Weekly EMA20 slope up required")

    capital        = STARTING_CAPITAL
    open_positions = {}
    closed_trades  = []
    capital_curve  = []
    skipped_trades = 0

    for day in trade_days:
        day_str = day.strftime('%Y-%m-%d')

        # ── Check exits first ──
        for symbol in list(open_positions.keys()):
            if symbol not in all_data:
                continue

            ind = calc_indicators(all_data[symbol], day)
            if ind is None:
                continue

            pos       = open_positions[symbol]
            days_held = (day - pos['buy_date']).days

            exit_type, exit_reason = check_exit(ind, days_held)

            if exit_type:
                sell_price = ind['price']
                qty        = pos['quantity']
                pnl        = round((sell_price - pos['buy_price']) * qty, 2)
                pnl_pct    = round(
                    (sell_price - pos['buy_price'])
                    / pos['buy_price'] * 100, 2
                )
                capital += pos['capital'] + pnl

                closed_trades.append({
                    'Symbol':      symbol,
                    'Buy Date':    pos['buy_date'].strftime('%Y-%m-%d'),
                    'Buy Price':   round(pos['buy_price'], 2),
                    'Sell Date':   day_str,
                    'Sell Price':  round(sell_price, 2),
                    'Quantity':    qty,
                    'Capital':     pos['capital'],
                    'PnL':         pnl,
                    'PnL%':        pnl_pct,
                    'Exit Type':   exit_type,
                    'Exit Reason': exit_reason,
                    'Days Held':   days_held,
                })

                del open_positions[symbol]

        # ── Check entries ──
        for symbol in symbols:
            if symbol not in all_data:
                continue
            if symbol in open_positions:
                continue
            if len(open_positions) >= MAX_POSITIONS:
                break
            if capital < CAPITAL_PER_TRADE:
                skipped_trades += 1
                continue

            ind = calc_indicators(all_data[symbol], day)
            if ind is None:
                continue

            if check_entry(ind):
                qty = floor(CAPITAL_PER_TRADE / ind['price'])
                if qty > 0:
                    allocated = round(qty * ind['price'], 2)
                    capital  -= allocated

                    open_positions[symbol] = {
                        'buy_date':  day,
                        'buy_price': ind['price'],
                        'quantity':  qty,
                        'capital':   allocated,
                    }

        # ── Capital curve ──
        open_value = 0
        for symbol, pos in open_positions.items():
            ind = calc_indicators(all_data[symbol], day)
            if ind:
                open_value += ind['price'] * pos['quantity']

        capital_curve.append({
            'Date':           day_str,
            'Cash':           round(capital, 2),
            'Open Positions': len(open_positions),
            'Open Value':     round(open_value, 2),
            'Total Value':    round(capital + open_value, 2),
        })

    # ── Force close remaining positions ──
    last_day = trade_days[-1]
    for symbol, pos in list(open_positions.items()):
        ind = calc_indicators(all_data[symbol], last_day)
        if ind:
            sell_price = ind['price']
            qty        = pos['quantity']
            pnl        = round((sell_price - pos['buy_price']) * qty, 2)
            pnl_pct    = round(
                (sell_price - pos['buy_price'])
                / pos['buy_price'] * 100, 2
            )
            capital   += pos['capital'] + pnl
            days_held  = (last_day - pos['buy_date']).days

            closed_trades.append({
                'Symbol':      symbol,
                'Buy Date':    pos['buy_date'].strftime('%Y-%m-%d'),
                'Buy Price':   round(pos['buy_price'], 2),
                'Sell Date':   last_day.strftime('%Y-%m-%d'),
                'Sell Price':  round(sell_price, 2),
                'Quantity':    qty,
                'Capital':     pos['capital'],
                'PnL':         pnl,
                'PnL%':        pnl_pct,
                'Exit Type':   'FORCE CLOSE',
                'Exit Reason': 'End of backtest period',
                'Days Held':   days_held,
            })

    return closed_trades, capital_curve, skipped_trades, capital


# ─────────────────────────────────────────────
# PRINT AND SAVE RESULTS
# ─────────────────────────────────────────────
def print_results(trades, capital_curve, skipped, final_capital):
    if not trades:
        print("\nNo trades were generated in this period.")
        print("The trend filter may be too strict for this universe.")
        print("Consider checking if stocks were in uptrend during 2025.")
        return

    df = pd.DataFrame(trades)

    # ── Per trade output ──
    print(f"\n{'═'*105}")
    print(f"  BACKTEST RESULTS v3 — {START_DATE} to {END_DATE}")
    print(f"{'═'*105}")
    print(f"\n  {'SYMBOL':<12} {'BUY DATE':<12} {'BUY':>8} "
          f"{'SELL DATE':<12} {'SELL':>8} {'QTY':>5} "
          f"{'PnL₹':>8} {'PnL%':>7} {'DAYS':>5} "
          f"{'EXIT TYPE':<12} {'REASON'}")
    print(f"  {'-'*100}")

    for _, row in df.sort_values(['Symbol', 'Buy Date']).iterrows():
        flag = '🟢' if row['PnL'] >= 0 else '🔴'
        print(
            f"  {flag} {row['Symbol']:<12} "
            f"{row['Buy Date']:<12} "
            f"₹{row['Buy Price']:>8.2f} "
            f"{row['Sell Date']:<12} "
            f"₹{row['Sell Price']:>8.2f} "
            f"{row['Quantity']:>5} "
            f"₹{row['PnL']:>8.2f} "
            f"{row['PnL%']:>+7.2f}% "
            f"{row['Days Held']:>5} "
            f"{row['Exit Type']:<12} "
            f"{row['Exit Reason']}"
        )

    # ── Per stock summary ──
    print(f"\n{'═'*105}")
    print(f"  PER STOCK SUMMARY")
    print(f"{'═'*105}")
    print(f"  {'SYMBOL':<12} {'TRADES':>7} {'WINS':>6} {'LOSSES':>8} "
          f"{'WIN%':>6} {'TOTAL PnL':>10} {'AVG PnL':>9} "
          f"{'BEST':>9} {'WORST':>9} {'AVG DAYS':>9}")
    print(f"  {'-'*95}")

    stock_summary = []
    for symbol, grp in df.groupby('Symbol'):
        wins     = (grp['PnL'] > 0).sum()
        losses   = (grp['PnL'] <= 0).sum()
        win_pct  = round(wins / len(grp) * 100, 1)
        total    = round(grp['PnL'].sum(), 2)
        avg      = round(grp['PnL'].mean(), 2)
        best     = round(grp['PnL'].max(), 2)
        worst    = round(grp['PnL'].min(), 2)
        avg_days = round(grp['Days Held'].mean(), 1)

        stock_summary.append({
            'Symbol':    symbol,
            'Trades':    len(grp),
            'Wins':      wins,
            'Losses':    losses,
            'Win%':      win_pct,
            'Total PnL': total,
            'Avg PnL':   avg,
            'Best':      best,
            'Worst':     worst,
            'Avg Days':  avg_days,
        })

        flag = '🟢' if total >= 0 else '🔴'
        print(
            f"  {flag} {symbol:<12} "
            f"{len(grp):>7} "
            f"{wins:>6} "
            f"{losses:>8} "
            f"{win_pct:>6.1f}% "
            f"₹{total:>10.2f} "
            f"₹{avg:>9.2f} "
            f"₹{best:>9.2f} "
            f"₹{worst:>9.2f} "
            f"{avg_days:>9.1f}"
        )

    # ── Capital curve highlights ──
    cc_df     = pd.DataFrame(capital_curve)
    max_value = cc_df['Total Value'].max()
    min_value = cc_df['Total Value'].min()
    max_date  = cc_df.loc[cc_df['Total Value'].idxmax(), 'Date']
    min_date  = cc_df.loc[cc_df['Total Value'].idxmin(), 'Date']
    max_dd    = round(
        (cc_df['Total Value'].cummax() - cc_df['Total Value']).max(), 2
    )

    # ── Overall summary ──
    total_trades = len(df)
    total_wins   = (df['PnL'] > 0).sum()
    total_losses = (df['PnL'] <= 0).sum()
    overall_win  = round(total_wins / total_trades * 100, 1)
    overall_pnl  = round(df['PnL'].sum(), 2)
    avg_pnl      = round(df['PnL'].mean(), 2)
    avg_days     = round(df['Days Held'].mean(), 1)
    best_trade   = df.loc[df['PnL'].idxmax()]
    worst_trade  = df.loc[df['PnL'].idxmin()]
    profit_exits = (df['Exit Type'] == 'PROFIT').sum()
    loss_exits   = (df['Exit Type'] == 'LOSS').sum()
    force_exits  = (df['Exit Type'] == 'FORCE CLOSE').sum()
    total_return = round(
        (final_capital - STARTING_CAPITAL) / STARTING_CAPITAL * 100, 2
    )

    flag = '🟢' if final_capital >= STARTING_CAPITAL else '🔴'

    print(f"\n{'═'*105}")
    print(f"  OVERALL SUMMARY")
    print(f"{'═'*105}")
    print(f"  Period             : {START_DATE} to {END_DATE}")
    print(f"  Starting capital   : ₹{STARTING_CAPITAL:,}")
    print(f"  {flag} Ending capital     : ₹{final_capital:,.2f}")
    print(f"  Total return       : {total_return:+.2f}%")
    print(f"  Max portfolio value: ₹{max_value:,.2f} on {max_date}")
    print(f"  Min portfolio value: ₹{min_value:,.2f} on {min_date}")
    print(f"  Max drawdown       : ₹{max_dd:,.2f}")
    print(f"  ─────────────────────────────────")
    print(f"  Total trades       : {total_trades}")
    print(f"  Winning trades     : {total_wins} ({overall_win}%)")
    print(f"  Losing trades      : {total_losses} ({100-overall_win}%)")
    print(f"  Profit exits       : {profit_exits}")
    print(f"  Loss exits         : {loss_exits}")
    print(f"  Force closes       : {force_exits}")
    print(f"  Skipped (no cap)   : {skipped}")
    print(f"  Avg days held      : {avg_days}")
    print(f"  Avg P&L/trade      : ₹{avg_pnl:+.2f}")
    print(f"  Best trade         : {best_trade['Symbol']} "
          f"₹{best_trade['PnL']:+.2f} ({best_trade['PnL%']:+.2f}%)")
    print(f"  Worst trade        : {worst_trade['Symbol']} "
          f"₹{worst_trade['PnL']:+.2f} ({worst_trade['PnL%']:+.2f}%)")
    print(f"{'═'*105}\n")

    # Save files
    df.to_csv(TRADES_FILE, index=False)
    print(f"Trade log saved to {TRADES_FILE}")

    pd.DataFrame(stock_summary).to_csv(SUMMARY_FILE, index=False)
    print(f"Summary saved to {SUMMARY_FILE}")

    cc_df.to_csv('capital_curve.csv', index=False)
    print(f"Capital curve saved to capital_curve.csv")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    print(f"\nNSE Backtest v3 — {START_DATE} to {END_DATE}")
    print(f"Starting capital  : ₹{STARTING_CAPITAL:,}")
    print(f"Capital per trade : ₹{CAPITAL_PER_TRADE:,}")
    print(f"Max positions     : {MAX_POSITIONS}")
    print(f"Min hold days     : {MIN_HOLD_DAYS}")
    print(f"Trend filter      : Daily + Weekly EMA20 slope up")

    symbols  = load_watchlist(INPUT_FILE)
    all_data = fetch_all_data(symbols)

    if not all_data:
        print("No data fetched — exiting.")
        exit(1)

    trades, curve, skipped, final_capital = run_backtest(symbols, all_data)
    print_results(trades, curve, skipped, final_capital)
