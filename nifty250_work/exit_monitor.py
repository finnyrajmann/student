"""
NSE Exit Monitor
=================
Reads positions.csv and checks each open position daily
for exit signals based on technical conditions.

Exit conditions:
    PROFIT EXIT  : RSI > 75  OR  Price >= BB Upper
    LOSS EXIT    : Price < 20 EMA  OR  RSI < 35
                   OR  20 EMA slope down  OR  RVOL > 1.5 on down day

Warning flags:
    RVOL < 0.5 for 3+ consecutive days (momentum dying)

Run every morning before market opens (9:00-9:15 AM IST).

positions.csv format:
    Symbol, EntryDate, EntryPrice, Quantity
    NMDC, 2026-03-18, 79.49, 125
"""

import yfinance as yf
import pandas as pd
import time
import os
from datetime import datetime


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
POSITIONS_FILE = "positions.csv"
SLEEP_SECONDS  = 0.3

# Indicator periods
RSI_PERIOD     = 14
EMA_PERIOD     = 20
BB_PERIOD      = 20
BB_STD         = 2
VOLUME_PERIOD  = 20

# Exit thresholds
RSI_OVERBOUGHT = 75
RSI_OVERSOLD   = 35
RVOL_SELL      = 1.5    # high volume on down day = danger
RVOL_DRY       = 0.5    # low volume = momentum dying
RVOL_DRY_DAYS  = 3      # consecutive days of low volume = warning


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def nse(symbol):
    return f"{symbol.upper().strip()}.NS"


def load_positions(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"'{filepath}' not found.\n"
            f"Create it with columns: Symbol, EntryDate, EntryPrice, Quantity"
        )
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    df['Symbol']     = df['Symbol'].str.strip()
    df['EntryPrice'] = df['EntryPrice'].astype(float)
    df['Quantity']   = df['Quantity'].astype(int)
    print(f"Loaded {len(df)} open positions from {filepath}")
    return df


# ─────────────────────────────────────────────
# FETCH AND CALCULATE INDICATORS
# ─────────────────────────────────────────────
def get_indicators(symbol):
    try:
        ticker = yf.Ticker(nse(symbol))
        df     = ticker.history(period='1y', interval='1d')

        if df.empty or len(df) < BB_PERIOD + RSI_PERIOD + 5:
            return None

        close  = df['Close']
        volume = df['Volume']

        # RSI
        delta  = close.diff()
        gain   = delta.where(delta > 0, 0).ewm(span=RSI_PERIOD, adjust=False).mean()
        loss   = (-delta.where(delta < 0, 0)).ewm(span=RSI_PERIOD, adjust=False).mean()
        rs     = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 20 EMA
        df['EMA20'] = close.ewm(span=EMA_PERIOD, adjust=False).mean()

        # Bollinger Bands
        df['BB_Mid']   = close.rolling(BB_PERIOD).mean()
        df['BB_Std']   = close.rolling(BB_PERIOD).std()
        df['BB_Upper'] = df['BB_Mid'] + BB_STD * df['BB_Std']
        df['BB_Lower'] = df['BB_Mid'] - BB_STD * df['BB_Std']

        # Volume — RVOL
        df['AvgVol'] = volume.rolling(VOLUME_PERIOD).mean()
        df['RVOL']   = volume / df['AvgVol']

        # EMA slope — is today's EMA above yesterday's?
        ema_slope_up = bool(df['EMA20'].iloc[-1] > df['EMA20'].iloc[-2])

        # Consecutive low volume days
        recent_rvol     = df['RVOL'].iloc[-RVOL_DRY_DAYS:]
        consec_low_vol  = bool((recent_rvol < RVOL_DRY).all())

        latest   = df.iloc[-1]
        prev     = df.iloc[-2]

        price    = round(float(latest['Close']), 2)
        ema20    = round(float(latest['EMA20']), 2)
        rsi      = round(float(latest['RSI']), 2)
        bb_upper = round(float(latest['BB_Upper']), 2)
        bb_mid   = round(float(latest['BB_Mid']), 2)
        bb_lower = round(float(latest['BB_Lower']), 2)
        rvol     = round(float(latest['RVOL']), 2)
        change   = round((price - float(prev['Close'])) / float(prev['Close']) * 100, 2)

        return {
            'price':           price,
            'change':          change,
            'rsi':             rsi,
            'ema20':           ema20,
            'ema_slope_up':    ema_slope_up,
            'bb_upper':        bb_upper,
            'bb_mid':          bb_mid,
            'bb_lower':        bb_lower,
            'rvol':            rvol,
            'consec_low_vol':  consec_low_vol,
        }

    except Exception:
        return None


# ─────────────────────────────────────────────
# EVALUATE EXIT CONDITIONS
# ─────────────────────────────────────────────
def evaluate_exit(ind):
    signals  = []
    warnings = []
    exit_type = None

    # ── Profit exits ──
    if ind['rsi'] > RSI_OVERBOUGHT:
        signals.append(f"RSI overbought ({ind['rsi']})")
        exit_type = 'PROFIT'

    if ind['price'] >= ind['bb_upper']:
        signals.append(f"Price at BB Upper ({ind['bb_upper']})")
        exit_type = 'PROFIT'

    # ── Loss/weakness exits ──
    if ind['price'] < ind['ema20']:
        signals.append(f"Price below 20 EMA ({ind['ema20']})")
        if exit_type != 'PROFIT':
            exit_type = 'LOSS'

    if ind['rsi'] < RSI_OVERSOLD:
        signals.append(f"RSI oversold ({ind['rsi']})")
        if exit_type != 'PROFIT':
            exit_type = 'LOSS'

    if not ind['ema_slope_up']:
        signals.append("20 EMA slope turning down")
        if exit_type != 'PROFIT':
            exit_type = 'LOSS'

    if ind['change'] < 0 and ind['rvol'] > RVOL_SELL:
        signals.append(f"Heavy selling volume (RVOL {ind['rvol']})")
        if exit_type != 'PROFIT':
            exit_type = 'LOSS'

    # ── Warnings (not exit triggers) ──
    if ind['consec_low_vol']:
        warnings.append(f"Volume drying up ({RVOL_DRY_DAYS} consecutive low volume days)")

    return exit_type, signals, warnings


# ─────────────────────────────────────────────
# PRINT REPORT
# ─────────────────────────────────────────────
def print_report(results):
    print(f"\n{'═'*85}")
    print(f"  PORTFOLIO EXIT MONITOR — {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"{'═'*85}")

    exits   = [r for r in results if r['ExitType'] is not None]
    holds   = [r for r in results if r['ExitType'] is None]

    # ── EXIT signals first ──
    if exits:
        print(f"\n  ⚠  EXIT SIGNALS ({len(exits)} positions)")
        print(f"  {'-'*82}")
        for r in exits:
            pnl_flag = '🟢' if r['PnL%'] >= 0 else '🔴'
            print(f"\n  {pnl_flag} {r['Symbol']:<12} "
                  f"Entry: ₹{r['EntryPrice']:<10} "
                  f"Current: ₹{r['Price']:<10} "
                  f"P&L: {r['PnL%']:+.2f}%  (₹{r['PnL']:+.0f})")
            print(f"     Exit Type : {r['ExitType']}")
            for sig in r['Signals']:
                print(f"     → {sig}")
            if r['Warnings']:
                for w in r['Warnings']:
                    print(f"     ⚠ {w}")
            print(f"     RSI:{r['RSI']:.1f}  "
                  f"EMA20:₹{r['EMA20']:.2f}  "
                  f"BB Upper:₹{r['BBUpper']:.2f}  "
                  f"RVOL:{r['RVOL']:.2f}  "
                  f"Days Held:{r['DaysHeld']}")

    # ── HOLD positions ──
    if holds:
        print(f"\n  ✅ HOLD ({len(holds)} positions)")
        print(f"  {'SYMBOL':<12} {'ENTRY':>8} {'PRICE':>8} {'CHG%':>7} "
              f"{'P&L%':>7} {'P&L₹':>10} {'RSI':>6} "
              f"{'EMA20':>8} {'RVOL':>6} {'DAYS':>5} {'NOTE'}")
        print(f"  {'-'*82}")
        for r in holds:
            pnl_flag = '🟢' if r['PnL%'] >= 0 else '🔴'
            note     = ' | '.join(r['Warnings']) if r['Warnings'] else ''
            print(
                f"  {pnl_flag} {r['Symbol']:<12} "
                f"₹{r['EntryPrice']:>8.2f} "
                f"₹{r['Price']:>8.2f} "
                f"{r['Change%']:>7.2f} "
                f"{r['PnL%']:>+7.2f}% "
                f"₹{r['PnL']:>+10.0f} "
                f"{r['RSI']:>6.1f} "
                f"₹{r['EMA20']:>8.2f} "
                f"{r['RVOL']:>6.2f} "
                f"{r['DaysHeld']:>5} "
                f"{note}"
            )

    # ── Portfolio summary ──
    total_pnl = sum(r['PnL'] for r in results)
    pnl_flag  = '🟢' if total_pnl >= 0 else '🔴'
    print(f"\n{'═'*85}")
    print(f"  {pnl_flag} Total Portfolio P&L : ₹{total_pnl:+.0f}")
    print(f"  Positions monitored  : {len(results)}")
    print(f"  Exit signals         : {len(exits)}")
    print(f"  Holding              : {len(holds)}")
    print(f"{'═'*85}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    positions  = load_positions(POSITIONS_FILE)
    total      = len(positions)
    results    = []
    start_time = datetime.now()

    print(f"\nChecking {total} positions...\n")

    for _, pos in positions.iterrows():
        symbol      = pos['Symbol']
        entry_price = pos['EntryPrice']
        quantity    = pos['Quantity']
        entry_date  = pd.to_datetime(pos['EntryDate'])
        days_held   = (datetime.now() - entry_date).days

        print(f"  Checking {symbol}...", end='\r')

        ind = get_indicators(symbol)

        if ind is None:
            print(f"  {symbol}: Could not fetch data — skipping")
            continue

        exit_type, signals, warnings = evaluate_exit(ind)

        pnl_per_share = ind['price'] - entry_price
        pnl_total     = round(pnl_per_share * quantity, 2)
        pnl_pct       = round((pnl_per_share / entry_price) * 100, 2)

        results.append({
            'Symbol':     symbol,
            'EntryPrice': entry_price,
            'Quantity':   quantity,
            'Price':      ind['price'],
            'Change%':    ind['change'],
            'PnL':        pnl_total,
            'PnL%':       pnl_pct,
            'RSI':        ind['rsi'],
            'EMA20':      ind['ema20'],
            'BBUpper':    ind['bb_upper'],
            'RVOL':       ind['rvol'],
            'DaysHeld':   days_held,
            'ExitType':   exit_type,
            'Signals':    signals,
            'Warnings':   warnings,
        })

        time.sleep(SLEEP_SECONDS)

    print_report(results)
