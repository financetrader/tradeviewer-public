# Hyperliquid Leverage Calculation

## Overview

This document describes how leverage is calculated and stored for Hyperliquid positions. Unlike Apex Omni which provides margin rates directly, Hyperliquid does not expose margin rate or leverage information in their API. Therefore, we estimate leverage using account equity and position value data.

**Key Principle**: Leverage is calculated when positions are **OPEN** and logged to position snapshots. When positions close and become closed trades, the leverage is looked up from the position snapshots where it was already calculated.

## API Limitations

Hyperliquid API provides:
- `accountValue` (total account equity) from `marginSummary`
- `positionValue` (notional position value) from position data
- Position size and entry price

Hyperliquid API does **NOT** provide:
- Margin rate
- Leverage
- Available balance (in the same sense as Apex)
- Per-position equity used

## Calculation Methodology

### Formula

```
leverage = position_size_usd / equity_used
```

Where:
- `position_size_usd` = position size × entry price
- `equity_used` = estimated equity locked in the position

### Estimation Methods

#### Method 1: Using Position Value (Most Accurate)

When `positionValue` is available from the API:

1. **If position_value >= account_equity**:
   - Position is leveraged (larger than account equity)
   - Estimate: `equity_used = account_equity × 0.6` (assumes 60% of equity used)
   - `leverage = position_size_usd / equity_used`

2. **If position_value < account_equity**:
   - Position smaller than account equity
   - Estimate: `equity_used = position_value × 0.8` (assumes 80% of position_value)
   - `leverage = position_size_usd / equity_used`

#### Method 2: Using Position Size (Fallback)

When `positionValue` is not available:

1. **If position_size_usd >= account_equity**:
   - Position is leveraged
   - Estimate: `equity_used = account_equity × 0.5` (conservative estimate)
   - `leverage = position_size_usd / equity_used`

2. **If position_size_usd < account_equity**:
   - Calculate position ratio: `position_ratio = position_size_usd / account_equity`
   - Estimate equity used ratio: `equity_used_ratio = position_ratio × 0.7`
   - `equity_used = account_equity × equity_used_ratio`
   - `leverage = position_size_usd / equity_used`

### Cross-Margin Considerations

Hyperliquid uses **cross-margin**, meaning:
- Equity is shared across all positions
- Multiple positions can share the same equity pool
- Per-position leverage estimates may be less accurate with multiple positions

The estimation assumes typical equity usage ratios for cross-margin accounts. Actual leverage may vary based on:
- Number of concurrent positions
- Total account exposure
- Risk management settings

### Capping

Estimated leverage is capped at **50x** to avoid unrealistic values.

## Data Flow

1. **Position Opens**:
   - Position is logged via `log_positions_for_all_wallets()`
   - Account equity is retrieved from `equity_snapshots`
   - `positionValue` is extracted from Hyperliquid API (if available)
   - Leverage is calculated using `estimate_leverage_hyperliquid()`
   - Leverage is stored in `position_snapshots` table

2. **Position Closes**:
   - Trade is synced via `sync_closed_trades_from_fills()`
   - Leverage is looked up from `position_snapshots` using `get_leverage_at_timestamp()`
   - Leverage is stored in `closed_trades` table

## Implementation Details

### Functions

#### `estimate_leverage_hyperliquid()`
**Location**: `utils/calculations.py`

Estimates leverage from position size, account equity, and optional position value.

**Parameters**:
- `position_size_usd`: Position size in USD
- `account_equity`: Total account equity
- `position_value`: Position value from API (optional)
- `total_position_values`: Sum of all position values (optional, not currently used)

**Returns**: Estimated leverage (rounded to 1 decimal) or None

#### `get_account_equity_at_timestamp()`
**Location**: `db/queries.py`

Retrieves account equity from equity snapshots at or before a given timestamp.

**Parameters**:
- `session`: Database session
- `wallet_id`: Wallet ID
- `timestamp`: Timestamp to look up equity at

**Returns**: Total equity value or None

#### `get_leverage_at_timestamp()`
**Location**: `db/queries.py`

Looks up leverage from position snapshots for a symbol/wallet at a specific timestamp.

**Parameters**:
- `session`: Database session
- `wallet_id`: Wallet ID
- `symbol`: Symbol
- `timestamp`: Timestamp to look up leverage at

**Returns**: Leverage value or None

### Database Schema

#### `position_snapshots` table
- `leverage`: Float, nullable - Stores calculated leverage for open positions

#### `closed_trades` table
- `leverage`: Float, nullable - Stores leverage looked up from position snapshots

## Accuracy Notes

### Limitations

1. **Estimation-based**: Leverage is estimated, not exact, since Hyperliquid doesn't provide margin rates
2. **Cross-margin complexity**: With multiple positions, per-position leverage estimates may be less accurate
3. **Equity snapshot timing**: Equity snapshots are taken every 30 minutes, so exact timing may not match position opening
4. **Assumption-based ratios**: Uses fixed ratios (0.6, 0.8, 0.7) which may not match actual usage

### When Estimates Are Most Accurate

- Single position accounts
- Recent positions (equity snapshot is recent)
- Positions with `positionValue` available from API
- Positions where `position_size_usd` is close to `positionValue`

### When Estimates May Be Less Accurate

- Multiple concurrent positions
- Very old positions (equity snapshot may be stale)
- Positions without `positionValue` data
- Accounts with complex margin usage patterns

## Future Improvements

1. **Store position_value in snapshots**: Currently `positionValue` is only used at calculation time. Storing it would improve historical accuracy.

2. **Refine estimation ratios**: Based on analysis of actual leverage patterns, refine the equity usage ratios.

3. **Account for multiple positions**: When multiple positions exist, consider total exposure when estimating per-position leverage.

4. **Real-time equity**: Use real-time equity from API instead of snapshots for more accurate calculations.

## Usage

### For Open Positions

Leverage is automatically calculated when positions are logged (every 30 minutes via scheduler).

### For Closed Trades

Leverage is automatically looked up from position snapshots when trades are synced from fills.

### Querying Leverage

```python
from db import queries
from db.database import get_session

with get_session() as session:
    # Get closed trades with leverage
    trades = queries.get_closed_trades(session, wallet_id=1)
    for trade in trades:
        leverage = trade.get('leverage')
        if leverage:
            print(f"Trade {trade['symbol']}: {leverage}x leverage")
```

## Related Files

- `utils/calculations.py` - Leverage calculation function
- `db/queries.py` - Database query functions
- `logger.py` - Position logging with leverage calculation
- `services/sync_service.py` - Closed trade syncing with leverage lookup
- `services/hyperliquid_client.py` - Hyperliquid API client

