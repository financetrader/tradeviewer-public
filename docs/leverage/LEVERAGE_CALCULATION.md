# Leverage Calculation Guide

**Status**: Margin delta tracking implemented for Apex Omni in both logger and dashboard. Hyperliquid margin delta implemented in dashboard (`wallet_dashboard()` route). ISSUE: Hyperliquid background logger still uses old estimation method - should be updated to use margin delta like dashboard does.

## Overview

Leverage is **calculated once when positions OPEN** and stored in `position_snapshots`. This is when leverage becomes **available for display** on open positions. When positions close and trades are synced, the leverage is **retrieved** from the position_snapshots (where it was already calculated) and stored in `closed_trades` for historical record. Leverage is then propagated to `aggregated_trades`.

```
Position Opens
    ↓
Logger runs while position is OPEN
├─ Stores PositionSnapshot with calculated leverage
└─ Leverage NOW AVAILABLE for display (open position)

(Position remains open - leverage displayed from position_snapshots)
    ↓
Position Closes (trade executed on exchange)
    ↓
Logger syncs closed trade
├─ Retrieves leverage from PositionSnapshot (calculated at open)
└─ Stores in ClosedTrade for historical record

Aggregated Trades are created
    ↓
Takes leverage from primary fill's ClosedTrade
```

**Key Distinction**: Leverage is displayed on open positions as soon as it's calculated (stored in position_snapshots). It's not waiting until the trade closes - it's available for the entire duration the position is open.

## Data Flow

### Step 1: Position Opens
User opens a position on the exchange.

### Step 2: Leverage Calculation & Logging
Two pathways calculate and store leverage:

**Dashboard View** (when user loads wallet page):
- **File**: `app.py` lines 769-865 (`wallet_dashboard()` function)
- Fetches positions and balance data
- **For Apex Omni**: Calls `calculate_leverage_from_margin_delta()` (margin delta method)
- **For Hyperliquid**: Calls `calculate_leverage_from_margin_delta()` (margin delta method)
- Writes fresh equity snapshot and position snapshot with calculated leverage
- This is the **primary/most accurate** leverage calculation path

**Background Logger** (every 30 minutes):
- **File**: `logger.py` lines 25-122 (`log_positions_for_all_wallets()` function)
- **For Apex Omni**: Does NOT calculate leverage (no leverage field stored)
- **For Hyperliquid**: Calls `estimate_leverage_hyperliquid()` (OLD estimation method - 0.6/0.8 ratios)
- **NOTE**: Hyperliquid logger should use margin delta like dashboard does (issue to fix)

Result: Position snapshots are created with leverage when either dashboard is loaded or logger runs.

### Step 3: Position Closes
User closes the position on the exchange. Trade is executed immediately.

### Step 4: Logger Syncs Closed Trade
**File**: `services/sync_service.py` (lines 12-56)

When logger syncs closed trade fills:
1. Extracts trade details from exchange API
2. **Looks up leverage** from `position_snapshots` using `get_leverage_at_timestamp()`
   - Finds most recent PositionSnapshot for same symbol before trade timestamp
   - Retrieves its leverage value (which was calculated at position open time)
3. Stores result in `closed_trades` table with leverage

### Step 5: Aggregated Trades Inherit Leverage
**File**: `services/aggregation_service.py` (lines 10-114)

When fills are aggregated by (wallet_id, timestamp, symbol):
1. Groups multiple fills from same trade
2. Takes leverage from primary fill's `closed_trades.leverage`
3. Stores in `aggregated_trades` table

**Result**: `aggregated_trades.leverage` = same as `closed_trades.leverage` = calculated at position open time

## Leverage Calculation Methods by Exchange

### Apex Omni

**Method**: Initial Margin Delta Tracking

**Data Available**:
- `initialMargin` (total account margin across all positions)
- `customInitialMarginRate` (per-position, but sometimes returns 0)
- `totalEquityValue` (account equity)

**Algorithm**:
```
1. Detect NEW position (first snapshot with size > 0 for symbol)
2. Get previous initialMargin from last EquitySnapshot
3. Calculate: equity_used = current_initial_margin - previous_initial_margin
4. Calculate: leverage = position_size_usd / equity_used
5. Cap at 50.0x, round to 1 decimal
```

**Example**:
```
Time T1: Total Margin = $0
Time T2: Open BTC (0.008 BTC @ $101,284 = $810.27)
  Current Margin: $162.22
  Margin Delta: $162.22 - $0 = $162.22
  Leverage: $810.27 / $162.22 = 5.0x ✓

Time T3: Open SOL (0.5 SOL @ $155.82 = $77.91) - still have BTC
  Current Margin: $166.12
  Margin Delta: $166.12 - $162.22 = $3.90
  Leverage: $77.91 / $3.90 = 20.0x ✓
```

**Fallback**: If not a new position or no previous data, use `customInitialMarginRate`:
```
leverage = 1 / customInitialMarginRate
```

**Implementation**: See [APEX_LEVERAGE_CALCULATION.md](./APEX_LEVERAGE_CALCULATION.md)

### Hyperliquid

**Method**: Total Margin Delta Tracking (identical to Apex)

**Data Available**:
- `totalMarginUsed` (total account margin across all positions)
- `positionValue` (notional position value)
- `accountValue` (account equity)

**Algorithm**:
```
1. Detect NEW position (first snapshot with size > 0 for symbol)
2. Get previous totalMarginUsed from last EquitySnapshot
3. Calculate: equity_used = current_total_margin - previous_total_margin
4. Calculate: leverage = position_size_usd / equity_used
5. Cap at 50.0x, round to 1 decimal
```

**Why This Works with Cross-Margin**:
Hyperliquid uses cross-margin (all positions share margin pool). When you open a position, `totalMarginUsed` increases by exactly the margin for that position. The delta isolates that specific position's margin perfectly.

**Example**:
```
Time T1: Total Margin Used = $0
Time T2: Open ETH (10 ETH @ $2,000 = $20,000)
  Current Margin: $2,000 (for 10x leverage)
  Margin Delta: $2,000 - $0 = $2,000
  Leverage: $20,000 / $2,000 = 10x ✓
```

**Fallback**: Old estimation method (deprecated, only for existing positions):
```
if position_value >= account_equity:
    equity_used = account_equity × 0.6
else:
    equity_used = position_value × 0.8
leverage = position_size_usd / equity_used
```

**Implementation**: See [HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md](./HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md)

## Database Schema

### position_snapshots
```sql
├─ wallet_id
├─ timestamp          -- When position snapshot was taken
├─ symbol            -- Position symbol (e.g., SOL, BTC, ETH)
├─ side              -- LONG or SHORT
├─ size              -- Amount held
├─ entry_price
├─ leverage          -- CALCULATED when position is OPEN
├─ equity_used       -- Equity allocated to this position
├─ initial_margin_at_open  -- Total margin when position opened
├─ calculation_method -- 'margin_delta', 'margin_rate', or 'unknown'
└─ other fields...
```

**When filled**: Every 30 minutes when logger runs (if position is open)
**Key field**: `leverage` - calculated at this moment when position exists

### closed_trades
```sql
├─ wallet_id
├─ timestamp          -- When trade was executed
├─ symbol
├─ side
├─ size
├─ entry_price
├─ exit_price
├─ closed_pnl
├─ leverage          -- RETRIEVED from position_snapshots
├─ calculation_method
└─ strategy_id
```

**When filled**: When trade is synced from exchange fills
**Key field**: `leverage` - looked up from position snapshot (calculated at open time)

### aggregated_trades
```sql
├─ wallet_id
├─ timestamp          -- When the aggregate trade occurred
├─ symbol
├─ side
├─ size              -- Sum of all fills
├─ avg_entry_price   -- Weighted average
├─ avg_exit_price    -- Weighted average
├─ total_pnl         -- Sum of all fills' PnL
├─ leverage          -- From primary fill's closed_trade
├─ fill_count        -- Number of fills in this group
└─ other fields...
```

**When filled**: When closed_trades are aggregated
**Key field**: `leverage` - copied from primary fill

### equity_snapshots
```sql
├─ wallet_id
├─ timestamp         -- When snapshot was taken
├─ total_equity      -- Account equity at this moment
├─ initial_margin    -- For Apex: initialMargin; For Hyperliquid: totalMarginUsed
└─ other fields...
```

**When filled**: Every time API is queried (every 30 minutes)
**Purpose**: Track account-level metrics for leverage delta calculations

## Current Limitations & Edge Cases

### 1. Existing Positions (Opened Before Tracking Started)
- **Problem**: No previous margin snapshot to calculate delta
- **Current**: Uses fallback method (margin rate if available, else "unknown")
- **Future**: Could backfill using historical analysis

### 2. Multiple Positions Opened Simultaneously
- **Problem**: Cannot determine which position used which portion of margin increase
- **Current**: Logs warning, calculates with total delta (may be slightly inaccurate)
- **Future**: Better heuristics for attribution

### 3. No Historical Data for Old Trades
- **Problem**: Trades from Aug-Nov 7 have no leverage (logger not running then)
- **Current**: These trades show `leverage: NULL`
- **Note**: EquitySnapshots only exist from Nov 11 onwards

### 4. Position Size Changes (Adding to Position)
- **Problem**: When user adds to existing position, treated as existing (not new)
- **Current**: Margin delta not recalculated
- **Future**: Could detect and recalculate

## Verification & Debugging

### Check If Working

```sql
-- Check equity snapshots are being created
SELECT COUNT(*), MAX(timestamp) FROM equity_snapshots WHERE wallet_id = X;

-- Check position snapshots have leverage values
SELECT COUNT(*), AVG(leverage), MAX(leverage)
FROM position_snapshots
WHERE wallet_id = X AND leverage IS NOT NULL;

-- Check closed trades received leverage from position snapshots
SELECT COUNT(*), AVG(leverage), MAX(leverage)
FROM closed_trades
WHERE wallet_id = X AND leverage IS NOT NULL;

-- Check aggregated trades have leverage
SELECT COUNT(*), AVG(leverage), MAX(leverage)
FROM aggregated_trades
WHERE wallet_id = X AND leverage IS NOT NULL;
```

### Find Leverage Calculation Method Used

```sql
-- For a specific symbol
SELECT symbol, leverage, calculation_method, timestamp
FROM position_snapshots
WHERE wallet_id = X AND symbol = 'SOL'
ORDER BY timestamp DESC
LIMIT 5;
```

### Verify Calculation Manually

For Apex with 5x leverage on 0.008 BTC @ $101,284:
- Position size: 0.008 × $101,284 = $810.27
- At 5x leverage: Equity used = $810.27 / 5 = $162.22
- Check database: `equity_used` should be ~$162.22

For Hyperliquid with 10x leverage on 10 ETH @ $2,000:
- Position size: 10 × $2,000 = $20,000
- At 10x leverage: Equity used = $20,000 / 10 = $2,000
- Check database: `equity_used` should be ~$2,000

## Related Files & Implementation

**Dashboard Leverage Calculation** (Primary - Margin Delta):
- `app.py` (lines 769-865 in `wallet_dashboard()`) - Dashboard calculates leverage for both exchanges
- `services/apex_leverage_calculator.py` - Apex Omni margin delta calculations
- `services/hyperliquid_leverage_calculator.py` - Hyperliquid margin delta calculations

**Background Logger** (Secondary - Inconsistent):
- `logger.py` (lines 25-122 in `log_positions_for_all_wallets()`)
  - Apex Omni: No leverage calculation
  - Hyperliquid: Uses old estimation method (NOT margin delta)

**Trade Synchronization**:
- `services/sync_service.py` (lines 12-56) - Syncs closed trades, looks up leverage
- `db/queries.py` (lines 322-359) - `get_leverage_at_timestamp()` function

**Deprecated - Still Active** (Should be removed/replaced):
- `utils/calculations.py` (lines 69-144) - `estimate_leverage_hyperliquid()` function - Used in logger.py for Hyperliquid (OLD estimation method)

**Models & Migrations**:
- `db/models.py` - Database models with `leverage`, `equity_used`, `calculation_method` fields
- `db/migrations/` - Schema changes

## Future Improvements

1. **Backfill historical positions**: Analyze equity snapshot history to calculate leverage for existing positions
2. **Track calculation method**: Use `calculation_method` field consistently across all tables
3. **Better simultaneous position handling**: Detect when multiple positions open in same period
4. **Position size change detection**: Recalculate when users add/reduce position size
5. **Real-time WebSocket**: Replace 30-minute polling with WebSocket for instant updates
6. **API rate exposure**: Track margin_rate directly when/if exchanges expose it
7. **Cross-margin optimization**: Account for how multiple positions interact

## Exchange-Specific Reference Files

For detailed implementation specifics by exchange:

- `APEX_LEVERAGE_CALCULATION.md` - Detailed Apex Omni margin delta implementation with edge cases
- `HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md` - Detailed Hyperliquid margin delta implementation with cross-margin architecture notes

**This file** (`LEVERAGE_CALCULATION.md`) is the primary consolidated reference for the overall implementation and both exchanges.

## Summary

**Current Implementation Status:**
- ✅ **Leverage is calculated** using margin delta when dashboard is loaded (for both Apex and Hyperliquid)
- ✅ **Leverage is DISPLAYED** immediately on dashboard (available for entire duration position is open)
- ✅ **Leverage is STORED** in `closed_trades` when trade closes (retrieved from position_snapshots)
- ⚠️ **Background logger** inconsistent: Apex skips leverage, Hyperliquid uses old estimation method
- ✅ **Dashboard is primary source** for accurate margin delta leverages
- ✅ **Calculation method tracked** in `calculation_method` field for debugging

**Issues to Address:**
1. Hyperliquid background logger should use margin delta method like the dashboard does
2. Apex Omni background logger should calculate leverage like the dashboard does
3. Remove dependency on old `estimate_leverage_hyperliquid()` once logger is updated
