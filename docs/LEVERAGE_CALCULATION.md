# Leverage Calculation Flow

## Overview

The application calculates and stores leverage for trades in two ways:
1. **Position Snapshots**: Leverage estimated when positions are open (every 30 minutes)
2. **Closed Trades**: Leverage copied from position snapshots when trades close

## Current Implementation

### Step 1: Background Logger Runs (Every 30 Minutes)

**File**: `logger.py` (lines 70-122)

The background logger periodically fetches current positions from Hyperliquid API:

```
Logger runs every 30 minutes
    ↓
Fetch current open positions from Hyperliquid API
    ↓
For each position:
    ├─ Get account_equity (total wallet equity)
    ├─ Calculate position_size_usd = size × entry_price
    ├─ Call: estimate_leverage_hyperliquid(
    │   position_size_usd,
    │   account_equity,
    │   position_value (from API)
    │ )
    ├─ Create position_data dict with leverage value
    └─ Insert into position_snapshots table
    ↓
Also stores equity snapshot:
    ├─ timestamp
    └─ total_equity (account_equity)
```

### Step 2: Leverage Estimation Algorithm

**File**: `utils/calculations.py` (lines 69-144)

Function: `estimate_leverage_hyperliquid(position_size_usd, account_equity, position_value)`

#### Method 1: Using position_value (from Hyperliquid API)

```
If position_value >= account_equity:
    # Position is at least as large as account equity = leveraged
    estimated_equity_used = account_equity × 0.6  (assume 60% of equity used)
    leverage = position_size_usd / estimated_equity_used

Else:
    # Position smaller than account equity
    estimated_equity_used = position_value × 0.8  (assume 80% of position_value)
    leverage = position_size_usd / estimated_equity_used
```

#### Method 2: Fallback (when position_value not available)

```
position_ratio = position_size_usd / account_equity

If position_ratio >= 1.0:
    # Position larger than equity = leveraged
    estimated_equity_used = account_equity × 0.5
    leverage = position_size_usd / estimated_equity_used

Else:
    # Position smaller than equity
    equity_used_ratio = max(0.1, position_ratio × 0.7)
    estimated_equity_used = account_equity × equity_used_ratio
    leverage = position_size_usd / estimated_equity_used
```

**Result**: Capped at 50.0x max, rounded to 1 decimal place

**Storage**: `position_snapshots.leverage`

### Step 3: Trade Closes (User Executes Trade on Exchange)

The trade fill is executed on the exchange immediately, but not synced to our database until the background logger runs again.

### Step 4: Background Logger Syncs Closed Trade

**File**: `services/sync_service.py` (lines 12-56)

Function: `sync_closed_trades_from_fills(session, fills, wallet_id)`

```
For each closed trade fill from exchange:
    ├─ Extract: timestamp, symbol, size, entry_price, closed_pnl, fees
    │
    ├─ Resolve strategy_id:
    │   └─ Call: resolve_strategy_id(wallet_id, symbol, timestamp)
    │
    ├─ Look up leverage from position snapshots:
    │   └─ Call: get_leverage_at_timestamp(wallet_id, symbol, timestamp)
    │       ├─ Query PositionSnapshot where:
    │       │   • symbol matches
    │       │   • timestamp <= trade_timestamp
    │       │   • leverage IS NOT NULL
    │       │   • size > 0
    │       └─ Return: Most recent leverage value (order by timestamp DESC)
    │
    ├─ Create closed_trade record with:
    │   ├─ timestamp
    │   ├─ symbol
    │   ├─ size
    │   ├─ entry_price
    │   ├─ exit_price
    │   ├─ closed_pnl
    │   ├─ leverage (from step above)
    │   └─ strategy_id
    │
    └─ Store in closed_trades table
```

**File**: `db/queries.py` (lines 322-359)

Function: `get_leverage_at_timestamp(wallet_id, symbol, timestamp)`

```
SELECT leverage FROM position_snapshots
WHERE:
    symbol = normalized_symbol
    timestamp <= trade_timestamp
    leverage IS NOT NULL
    size > 0
    wallet_id = wallet_id
ORDER BY timestamp DESC
LIMIT 1
```

### Step 5: Aggregated Trades Get Leverage

**File**: `services/aggregation_service.py` (lines 10-114)

Function: `sync_aggregated_trades(session, wallet_id)`

When fills are aggregated by (wallet_id, timestamp, symbol):
```
For each group of fills:
    ├─ Sum up sizes, fees, PnL
    ├─ Calculate weighted average entry/exit prices
    ├─ Use leverage from primary (first) fill
    └─ Store in aggregated_trades table
```

**Result**: `aggregated_trades.leverage` = same as `closed_trades.leverage`

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────┐
│ OPEN POSITION                                           │
│ (User opens trade on Hyperliquid)                       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ BACKGROUND LOGGER RUNS (every 30 min)                   │
├─────────────────────────────────────────────────────────┤
│ • Fetches open positions from API                       │
│ • Calculates leverage (estimated)                       │
│ • Stores in: position_snapshots (with leverage)         │
│ • Stores in: equity_snapshots (total equity)            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ POSITION SNAPSHOTS TABLE                                │
│ ├─ timestamp                                            │
│ ├─ symbol (SOL, ETH, BTC, etc)                         │
│ ├─ size (amount held)                                  │
│ ├─ leverage (ESTIMATED from formula)                    │
│ └─ entry_price                                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ USER CLOSES TRADE                                       │
│ (Trade executed on Hyperliquid)                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ BACKGROUND LOGGER SYNCS CLOSED TRADE                    │
├─────────────────────────────────────────────────────────┤
│ • Fetches closed fills from API                         │
│ • Looks up leverage from position_snapshots             │
│ • Stores in: closed_trades (with leverage)             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ CLOSED TRADES TABLE                                     │
│ ├─ timestamp                                            │
│ ├─ symbol                                              │
│ ├─ size                                                │
│ ├─ entry_price / exit_price                            │
│ ├─ closed_pnl                                          │
│ ├─ leverage (from position_snapshots)                   │
│ └─ strategy_id                                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ AGGREGATED TRADES (group by timestamp+symbol)           │
│ ├─ total_size (sum of fills)                            │
│ ├─ total_pnl (sum of PnLs)                             │
│ ├─ leverage (from primary fill)                         │
│ └─ fill_count (how many fills grouped)                  │
└─────────────────────────────────────────────────────────┘
```

## Current Limitations

1. **Estimation Not Actual**: Leverage is estimated using percentage-based formulas, not actual margin data
   - 60% and 80% are guesses
   - May be inaccurate for cross-margin with multiple positions

2. **Position Value Dependency**: Only as good as Hyperliquid's `position_value` field
   - Hyperliquid doesn't provide margin rate or actual leverage
   - Falls back to rough estimation if position_value not available

3. **No Historical Leverage for Old Trades**:
   - Trades from before logger was running have no leverage data
   - Can only look up leverage from position snapshots that exist

4. **Cross-Margin Complexity**:
   - For accounts with multiple positions, leverage calculation is less accurate
   - One position's margin affects others' available equity

## Alternative Approach: Equity Delta Method

### Concept

Calculate leverage from actual account equity movement:

```
leverage = position_size_usd / equity_delta

Where:
  equity_delta = account_equity_at_position_open - account_equity_at_position_close
```

### Example

```
Position opened at 10:00 AM → Equity: $1,500
Position closed at 10:30 AM → Equity: $1,350
Equity delta: $150 (margin used)

Position size: 2.5 SOL × $160 = $400
Leverage: $400 / $150 = 2.67x
```

### Advantages

- ✅ Uses **actual equity movement**, not estimates
- ✅ Automatically accounts for:
  - Trading fees
  - Funding fees
  - Liquidation penalties
  - Cross-margin effects
- ✅ More accurate over time
- ✅ Simple calculation

### Requirements

- Must have equity snapshots both before and after trade timestamp
- Background logger must be running regularly
- Needs at least 2 equity snapshots around trade

### Implementation

Would replace leverage lookup in `sync_service.py`:

```python
# Current (line 32):
leverage = queries.get_leverage_at_timestamp(session, wallet_id, sym, ts)

# Alternative:
leverage = queries.get_leverage_from_equity_delta(session, wallet_id, ts, position_size_usd)
```

New function would:
1. Find equity snapshot before or at trade timestamp
2. Find equity snapshot after trade timestamp
3. Calculate equity_delta = before - after
4. Return: position_size_usd / equity_delta (if delta > 0)

## Database Schema

### position_snapshots
```
├─ id (primary key)
├─ wallet_id
├─ timestamp
├─ symbol
├─ side (LONG/SHORT)
├─ size (amount held)
├─ entry_price
├─ current_price
├─ position_size_usd
├─ leverage ← Calculated when position is open
├─ unrealized_pnl
├─ equity_used
└─ calculation_method (how leverage was calculated)
```

### closed_trades
```
├─ id (primary key)
├─ wallet_id
├─ timestamp
├─ symbol
├─ side
├─ size
├─ entry_price
├─ exit_price
├─ closed_pnl
├─ leverage ← Copied from position_snapshots
├─ close_fee
├─ open_fee
├─ strategy_id
└─ calculation_method
```

### aggregated_trades
```
├─ id (primary key)
├─ wallet_id
├─ timestamp
├─ symbol
├─ side
├─ size (sum of fills)
├─ avg_entry_price (weighted)
├─ avg_exit_price (weighted)
├─ total_pnl (sum of fills)
├─ leverage ← From primary fill
├─ fill_count (how many fills aggregated)
└─ calculation_method
```

### equity_snapshots
```
├─ id (primary key)
├─ wallet_id
├─ timestamp
└─ total_equity ← Actual account equity at this moment
```

## Future Improvements

1. **Implement equity delta method** for more accurate leverage
2. **Store calculation_method** to track which method was used
3. **Add margin_rate from API** when Hyperliquid exposes it
4. **Retroactively calculate** leverage for old trades when new equity data becomes available
5. **Cross-margin analysis** to show how positions interact
