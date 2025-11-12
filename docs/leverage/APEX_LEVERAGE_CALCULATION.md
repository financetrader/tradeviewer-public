# Apex Omni Leverage Calculation via Initial Margin Tracking

## Problem

The Apex Omni API sometimes returns `customInitialMarginRate: 0` for open positions, making it impossible to calculate leverage using the standard formula: `leverage = 1 / customInitialMarginRate`.

Example from logs:
```json
{"exchange": "ApexOmni", "method": "positions_snapshot", "symbol": "SOL-USDT", 
 "side": "SHORT", "size": "0.5", "entryPrice": "155.82", 
 "customInitialMarginRate": "0", "computedLeverage": null}
```

## Solution: Margin Delta Tracking

Instead of relying on the `customInitialMarginRate` field, we track changes in the total `initialMargin` value from the Apex balance API. When a position opens, the increase in `initialMargin` equals the equity used by that position.

### Algorithm

1. **Detect New Position**: Check if this is the first snapshot with size > 0 for this symbol
2. **Get Previous Margin**: Retrieve the most recent `initialMargin` value before position opened
3. **Calculate Delta**: `equity_used = current_initial_margin - previous_initial_margin`
4. **Calculate Leverage**: `leverage = position_size_usd / equity_used`

### Step-by-Step Example

**Scenario**: Opening a SOL SHORT position with 20x leverage

```
Time T1: No open positions
├─ Total Equity: $400.00
├─ Available Balance: $400.00
└─ Initial Margin: $0.00

Time T2: Open SOL SHORT (0.5 SOL @ $155.82)
├─ Position Size: $77.91
├─ Total Equity: $400.00
├─ Available Balance: $396.10
└─ Initial Margin: $3.90  ← Increased from $0

Calculation:
├─ Previous Initial Margin: $0.00
├─ Current Initial Margin: $3.90
├─ Margin Delta (Equity Used): $3.90
├─ Position Size USD: $77.91
└─ Leverage: $77.91 / $3.90 = 19.97x ≈ 20x ✓
```

**Scenario 2**: Opening a second position (BTC)

```
Time T3: Already have SOL position
├─ Total Equity: $400.00
├─ Available Balance: $396.10
└─ Initial Margin: $3.90

Time T4: Open BTC SHORT (0.008 BTC @ $101,284)
├─ Position Size: $810.27
├─ Total Equity: $400.00
├─ Available Balance: $233.88
└─ Initial Margin: $166.12  ← Increased from $3.90

Calculation for BTC:
├─ Previous Initial Margin: $3.90
├─ Current Initial Margin: $166.12
├─ Margin Delta (Equity Used): $162.22
├─ Position Size USD: $810.27
└─ Leverage: $810.27 / $162.22 = 4.99x ≈ 5x ✓
```

## Implementation

### Database Schema

**EquitySnapshot** - Track total initial margin over time:
```sql
CREATE TABLE equity_snapshots (
    ...
    initial_margin FLOAT,  -- Total margin used across all positions
    ...
);
```

**PositionSnapshot** - Track margin at position open:
```sql
CREATE TABLE position_snapshots (
    ...
    initial_margin_at_open FLOAT,  -- Total margin when this position opened
    calculation_method VARCHAR(20),  -- How leverage was calculated
    ...
);
```

### Code Flow

**File**: `app.py` lines 813-837 (`wallet_dashboard()` function)

1. **Equity Snapshot** (app.py line 769-789):
   ```python
   snapshot_data = {
       'initial_margin': float(balance.get('initialMargin', 0) or 0)
   }
   ```

2. **Position Leverage Calculation** (app.py lines 821-824):
   ```python
   from services.apex_leverage_calculator import calculate_leverage_from_margin_delta

   leverage, equity_used, method = calculate_leverage_from_margin_delta(
       session, wallet_id, symbol, position_size_usd,
       current_initial_margin, timestamp, pos
   )
   ```

3. **Calculator Logic** (services/apex_leverage_calculator.py):
   ```python
   # Detect if new position
   if not is_new_position(session, wallet_id, symbol, current_timestamp):
       return calculate_from_margin_rate(position_raw)  # Fallback for existing

   # Get previous margin
   previous_margin = get_previous_initial_margin(session, wallet_id, current_timestamp)

   # Calculate delta
   margin_delta = current_initial_margin - previous_margin

   # Calculate leverage
   leverage = position_size_usd / margin_delta
   ```

**Note**: Apex Omni margin delta calculation only happens in the dashboard (`app.py`). The background logger (`logger.py`) does NOT calculate leverage for Apex positions.

## When It Works

✅ **Works well for:**
- New positions opened sequentially (one at a time)
- Positions with different leverage settings
- When `customInitialMarginRate` returns 0

✅ **Fallback chain:**
1. Try margin delta (primary method)
2. If not a new position, try `customInitialMarginRate`
3. If both fail, mark as "unknown"

## Limitations & Edge Cases

### 1. Existing Open Positions
- **Limitation**: Cannot calculate for positions already open before tracking started
- **Handling**: Leave existing positions unchanged, only calculate for NEW positions
- **Status**: `calculation_method: "unknown"` or `"margin_rate"` if available

### 2. Multiple Positions Opened Simultaneously
- **Limitation**: Cannot determine which position used which portion of the margin increase
- **Handling**: Log warning, but still calculate (may be inaccurate)
- **Detection**: If `margin_delta > position_size_usd`

### 3. No Historical Data
- **Limitation**: If no previous `initialMargin` snapshot exists
- **Handling**: Fallback to `customInitialMarginRate` or mark as "unknown"
- **Recovery**: Once tracking starts, subsequent positions will calculate correctly

### 4. Position Size Changes (Add to Position)
- **Limitation**: Adding to existing position increases margin, but position already exists
- **Handling**: Current logic treats as existing position, won't recalculate
- **Future**: Could track size changes and recalculate weighted average leverage

## Verification

### Check Calculation in Logs

Look for log entries like:
```
[BTC-USDT] Margin calculation:
  Previous margin: $3.90
  Current margin: $166.12
  Delta (equity used): $162.22
[BTC-USDT] RESULT:
  Equity used: $162.22
  Leverage: 5.0x
  Method: margin_delta
```

### Check Database

```sql
SELECT symbol, leverage, equity_used, calculation_method, initial_margin_at_open
FROM position_snapshots
WHERE wallet_id = 6 AND calculation_method = 'margin_delta'
ORDER BY timestamp DESC;
```

### Verify Against Exchange

1. Open a new position on Apex with known leverage (e.g., 20x)
2. Check the calculated leverage in database
3. Compare with exchange UI
4. Verify `equity_used = position_size / leverage`

## Troubleshooting

### Leverage Shows as `None`

**Possible causes:**
1. Position already existed before tracking started
2. No previous `initialMargin` snapshot
3. `customInitialMarginRate` also returns 0

**Check:**
```sql
SELECT * FROM position_snapshots 
WHERE symbol = 'SOL-USDT' 
ORDER BY timestamp DESC LIMIT 1;
```

Look at `calculation_method`:
- `"margin_delta"`: Successfully calculated ✓
- `"margin_rate"`: Used fallback method ✓
- `"unknown"`: Could not calculate ✗
- `"error"`: Exception occurred ✗

### Incorrect Leverage Value

**Possible causes:**
1. Multiple positions opened at same time
2. Missed a snapshot (data gap)
3. Position size was modified

**Check logs:**
```
grep "Margin calculation" logs/app.log
```

## Future Enhancements

1. **Backfill Historical Positions**: Analyze historical snapshots to calculate leverage for existing positions
2. **Handle Position Size Changes**: Track when user adds/reduces position size and recalculate
3. **Multi-Position Detection**: Better handling when multiple positions open simultaneously
4. **Manual Override**: Allow user to manually set leverage for positions that can't be auto-calculated

## Related Documentation

- [LEVERAGE_CALCULATION.md](./LEVERAGE_CALCULATION.md) - Primary consolidated reference for all exchanges
- [HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md](./HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md) - Hyperliquid implementation

