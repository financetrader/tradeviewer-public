# Hyperliquid Leverage Calculation via Margin Delta Tracking

## Overview

Hyperliquid leverage **can be** calculated using the **margin delta tracking** approach, identical to the Apex Omni implementation. This provides accurate per-position leverage for new positions.

**Current Implementation Status:**
- ✅ **Dashboard** (`app.py` lines 839-863): Uses margin delta tracking
- ❌ **Background Logger** (`logger.py` lines 78-86): Still uses old estimation method (should be updated)

## Key Discovery

Hyperliquid's `marginSummary` API provides `totalMarginUsed` - the exact field we need for margin delta tracking!

```json
{
  "marginSummary": {
    "accountValue": 596.71,
    "totalMarginUsed": 0.0,
    "totalNtlPos": 0.0,
    "totalRawUsd": 596.71
  }
}
```

## Algorithm

### Margin Delta Tracking

1. **Track margin over time**: Store `totalMarginUsed` in `equity_snapshots`
2. **Detect new positions**: Check if this is the first snapshot with size > 0
3. **Calculate delta**: `equity_used = current_margin - previous_margin`
4. **Calculate leverage**: `leverage = position_size_usd / equity_used`

### Example

```
Time T1: No positions
├─ Account Value: $600.00
├─ Total Margin Used: $0.00
└─ Available: $600.00

Time T2: Open ETH LONG (10 ETH @ $2,000)
├─ Position Size: $20,000
├─ Account Value: $600.00
├─ Total Margin Used: $60.00  ← Increased from $0
├─ Margin Delta: $60.00
└─ Leverage: $20,000 / $60 = 333x ❌ Too high!

Actually with 10x leverage:
├─ Total Margin Used: $2,000.00
├─ Margin Delta: $2,000.00
└─ Leverage: $20,000 / $2,000 = 10x ✅
```

## Implementation

### Database Schema

Uses the same schema as Apex:
- `equity_snapshots.initial_margin` - Stores `totalMarginUsed`
- `position_snapshots.initial_margin_at_open` - Total margin when position opened
- `position_snapshots.calculation_method` - How leverage was calculated

### Code Flow (Dashboard Implementation)

**File**: `app.py` lines 839-863 (`wallet_dashboard()` function)

1. **Fetch clearinghouse state**:
   ```python
   state = client.fetch_clearinghouse_state()
   margin_summary = state.get('marginSummary', {})
   total_margin_used = margin_summary.get('totalMarginUsed', 0)
   ```

2. **Save to balance_data**:
   ```python
   balance_data = {
       'totalEquityValue': account_value,
       'totalMarginUsed': total_margin_used,  # Key field
       ...
   }
   ```

3. **Store in equity snapshot**:
   ```python
   snapshot_data = {
       'initial_margin': total_margin_used,  # Reuse same field as Apex
       ...
   }
   ```

4. **Calculate leverage for new positions**:
   ```python
   from services.hyperliquid_leverage_calculator import calculate_leverage_from_margin_delta as hl_calc_leverage

   leverage, equity_used, method = hl_calc_leverage(
       session, wallet_id, symbol, position_size_usd,
       current_margin_used, timestamp
   )
   ```

### Legacy Code Flow (Background Logger - Deprecated)

**File**: `logger.py` lines 78-86 (should be updated to use margin delta)

Currently uses old estimation method:
```python
from utils.calculations import estimate_leverage_hyperliquid

leverage = estimate_leverage_hyperliquid(
    position_size_usd=position_size_usd,
    account_equity=account_equity,
    position_value=position_value if position_value > 0 else None
)
```

**TODO**: Update logger to use `calculate_leverage_from_margin_delta()` like dashboard does.

## When It Works

✅ **NEW positions opened after tracking started**
- System has previous `totalMarginUsed` snapshot
- Can calculate margin delta accurately
- `calculation_method: "margin_delta"`

❌ **Existing positions**
- Opened before tracking started
- No previous margin data to compare
- `calculation_method: "unknown"`

## Advantages Over Previous Estimation Method

### Old Method (Estimation)
```python
# Guessed based on ratios
if position_value >= account_equity:
    equity_used = account_equity × 0.6  # Assumption!
else:
    equity_used = position_value × 0.8  # Assumption!
```

**Problems:**
- Based on assumptions, not facts
- Inaccurate with multiple positions
- No way to verify correctness

### New Method (Margin Delta)
```python
# Facts from API
previous_margin = get_from_database()
current_margin = get_from_api()
equity_used = current_margin - previous_margin  # Actual!
```

**Benefits:**
- ✅ Based on actual API data
- ✅ Works with multiple positions
- ✅ Same accuracy as Apex method
- ✅ Verifiable against exchange

## API Fields Used

### marginSummary
- `accountValue` - Total account equity
- `totalMarginUsed` - **Key field** - total margin across positions
- `totalRawUsd` - Raw account balance
- `totalNtlPos` - Total notional position value

### crossMarginSummary
- Same fields as `marginSummary`
- Hyperliquid uses cross-margin by default

### Other Fields
- `withdrawable` - Available balance
- `crossMaintenanceMarginUsed` - Maintenance margin

## Cross-Margin Considerations

Hyperliquid uses **cross-margin**, meaning:
- All positions share the same margin pool
- When you open a new position, `totalMarginUsed` increases by the margin for that position
- This is PERFECT for margin delta tracking!

The margin delta approach works excellently with cross-margin because:
1. Each new position adds to `totalMarginUsed`
2. The delta isolates that specific position's margin
3. No need to estimate proportions

## Comparison with Apex

| Feature | Apex Omni | Hyperliquid |
|---------|-----------|-------------|
| **Margin Field** | `initialMargin` | `totalMarginUsed` |
| **API Endpoint** | `get_account_balance_v3()` | `fetch_clearinghouse_state()` |
| **Margin Type** | Cross-margin | Cross-margin |
| **Field Location** | `data.initialMargin` | `marginSummary.totalMarginUsed` |
| **Reliability** | Sometimes returns 0 | Always accurate |
| **Algorithm** | Margin delta | Margin delta (identical) |

## Edge Cases

### 1. Multiple Positions Opened Simultaneously
**Scenario**: Two positions opened in same snapshot period

**Behavior**:
- Total margin increase includes both positions
- Cannot determine individual split
- Both marked with total delta

**Solution**: Log warning, calculate conservatively

### 2. No Previous Margin Data
**Scenario**: First time tracking this wallet

**Behavior**:
- Cannot calculate margin delta
- Falls back to `calculation_method: "unknown"`

**Solution**: Starts working for next new position

### 3. Position Size Changes
**Scenario**: User adds to existing position

**Behavior**:
- Not detected as "new" position
- Margin delta not recalculated

**Future**: Could track size changes and recalculate

## Verification

### Check If Working

```sql
-- Check if margin is being tracked
SELECT timestamp, initial_margin 
FROM equity_snapshots 
WHERE wallet_id = X 
ORDER BY timestamp DESC 
LIMIT 10;

-- Check leverage calculations
SELECT symbol, leverage, calculation_method, initial_margin_at_open
FROM position_snapshots
WHERE wallet_id = X AND calculation_method = 'margin_delta'
ORDER BY timestamp DESC;
```

### Verify Calculation

When you open a new Hyperliquid position:
1. Note the position size and leverage from exchange UI
2. Check database:
   - `equity_used` should = position_size / leverage
   - `calculation_method` should = "margin_delta"
3. Verify: `position_size_usd / equity_used` ≈ exchange leverage

## Future Enhancements

1. **Backfill existing positions**: Analyze historical data to calculate leverage for open positions
2. **Real-time WebSocket**: Use WebSocket for instant margin updates
3. **Position size change detection**: Recalculate when positions are modified
4. **Multi-position optimization**: Better handling of simultaneous position opens

## Related Documentation

- [LEVERAGE_CALCULATION.md](./LEVERAGE_CALCULATION.md) - Primary consolidated reference for all exchanges
- [APEX_LEVERAGE_CALCULATION.md](./APEX_LEVERAGE_CALCULATION.md) - Apex Omni margin delta implementation

## Implementation Notes

**Margin Delta is Primary Method** (Dashboard):
- ✅ Dashboard uses margin delta tracking for accurate leverage calculation
- ✅ Only calculates for NEW positions (detects via first snapshot with size > 0)
- ✅ Fallback: "unknown" if no previous `totalMarginUsed` snapshot exists

**Old Estimation Method (Background Logger - Active but should be replaced)**:
- ⚠️ Logger still uses old estimation method with 0.6/0.8 ratios
- ⚠️ Should be updated to use margin delta like dashboard does
- ❌ Not as accurate as margin delta method
- Will be kept for backward compatibility until logger is updated

