# Leverage Calculation Guide

**Status**: ✅ **COMPLETE** - All leverage calculations use margin delta method exclusively.

**Implementation Status**:
- ✅ logger.py: Uses margin delta for Hyperliquid positions (lines 70-92)
- ✅ app.py dashboard display: Uses margin delta for Hyperliquid (lines 506-535)
- ✅ app.py snapshot storage: Uses margin delta for both Apex and Hyperliquid (lines 820-870)
- ✅ Deprecated function: `estimate_leverage_hyperliquid()` removed from utils/calculations.py
- ✅ Code cleanup: Zero references to old estimation method in functional code

**All leverage calculations now use the accurate margin delta method consistently across the entire system.**

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

## Data Flow (Current Implementation - All Margin Delta)

### Step 1: Position Opens
User opens a position on the exchange.

### Step 2: Leverage Calculation (Margin Delta Method)
When positions are logged/monitored, both components use margin delta:

**Dashboard** (`app.py`):
- Lines 506-535: Position display uses `calculate_leverage_from_margin_delta()` for Hyperliquid
- Lines 820-870: Position snapshot storage uses `calculate_leverage_from_margin_delta()` for both Apex (821-844) and Hyperliquid (847-870)
- Calculates and stores in position_snapshots

**Background Logger** (`logger.py` lines 70-92):
- Calls `calculate_leverage_from_margin_delta()` for Hyperliquid positions
- Fetches clearinghouse state and extracts `totalMarginUsed`
- Stores leverage with `calculation_method` field for verification

**Result**: ✅ ALL leverage uses margin delta method consistently across both components.

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

**Core Margin Delta Calculators** (Used everywhere):
- `services/apex_leverage_calculator.py` - Apex Omni margin delta calculations
- `services/hyperliquid_leverage_calculator.py` - Hyperliquid margin delta calculations

**Active Usage of Margin Delta** (✅ All components):
- `logger.py` lines 70-92 - Background logger calculates leverage using margin delta for Hyperliquid
- `app.py` lines 506-535 - Dashboard position display uses margin delta for Hyperliquid
- `app.py` lines 820-870 - Dashboard position snapshot storage uses margin delta for both Apex and Hyperliquid

**Deprecated Code** (✅ Removed):
- ~~`utils/calculations.py` lines 69-144 - `estimate_leverage_hyperliquid()`~~ - **DELETED**
  - ~~Used in `app.py` lines 500-515~~ - **REPLACED with margin delta**
  - ~~Used in `logger.py` lines 81-86~~ - **REPLACED with margin delta**

**Trade Synchronization** (No changes):
- `services/sync_service.py` (lines 12-56) - Syncs closed trades, looks up leverage from position_snapshots
- `db/queries.py` (lines 322-359) - `get_leverage_at_timestamp()` function

**Database Models & Migrations**:
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

**Implementation Status**: ✅ **COMPLETE**

**Method Used**: Margin delta tracking - leverage calculated once when position opens

**Current State (Achieved)**:
- ✅ All leverage calculations use margin delta method exclusively
- ✅ Leverage calculated when position opens and stored in position_snapshots
- ✅ Leverage displayed immediately on dashboard
- ✅ Leverage retrieved from position_snapshots when trade closes
- ✅ Consistent behavior everywhere (dashboard, logger, database)
- ✅ `calculation_method` field tracks how each leverage was calculated ('margin_delta', 'margin_rate', or 'unknown')

**Completed Actions**:
1. ✅ Replaced app.py lines 506-535 (display) and 820-870 (snapshots) with margin delta calculation
2. ✅ Replaced logger.py lines 70-92 with margin delta for Hyperliquid background logging
3. ✅ Deleted deprecated `estimate_leverage_hyperliquid()` function from utils/calculations.py
4. ✅ Verified: Zero references to old estimation method in functional code
5. ✅ Verified: All leverage calculations use `calculate_leverage_from_margin_delta()`
