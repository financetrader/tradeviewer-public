# Leverage Calculation Strategy

## Overview
This document outlines how to calculate leverage for each exchange when the API doesn't provide sufficient data.

## Apex Omni

### Available Data
- **Per Position**: `customInitialMarginRate` (but sometimes returns 0)
- **Account Level**: `initialMargin` (total margin across all positions)
- **Account Level**: `totalEquityValue`, `availableBalance`
- **No Per-Position Margin/Equity Field**

### Calculation Approach

**PRIMARY METHOD: Initial Margin Delta Tracking (IMPLEMENTED ✅)**

Track changes in `initialMargin` over time. When a position opens, the increase in `initialMargin` equals the equity used by that position.

```python
# Algorithm:
1. Detect new position (first snapshot with size > 0)
2. Get previous initialMargin from last equity snapshot
3. Calculate delta: equity_used = current_margin - previous_margin
4. Calculate leverage: leverage = position_size_usd / equity_used

# Example:
Time T1: Initial Margin = $0
Time T2: Open BTC position, Initial Margin = $162.05
  → BTC equity used = $162.05
  → If position size = $810.27, leverage = 5x

Time T3: Open SOL position, Initial Margin = $166.05
  → SOL equity used = $4.00 ($166.05 - $162.05)
  → If position size = $77.91, leverage = 20x
```

**Key Insight**: Leverage is set at position open and remains fixed. By tracking the margin delta when each position opens, we can determine the exact equity allocated to each position, even when they have different leverage settings.

**FALLBACK METHOD: Margin Rate**

When margin delta cannot be calculated (e.g., existing positions, no historical data):
```python
if customInitialMarginRate > 0:
    leverage = 1 / customInitialMarginRate
else:
    leverage = None  # Mark as unknown
```

**Implementation**: See [APEX_LEVERAGE_CALCULATION.md](./APEX_LEVERAGE_CALCULATION.md) for detailed documentation.

### Rejected Approaches

❌ **Proportional Allocation** - Tried allocating total `initialMargin` proportionally based on position sizes. Failed because it assumes uniform leverage across all positions.

❌ **Default Leverage Mapping** - Mapping symbols to typical leverage values. Fails when user changes leverage settings.

❌ **Historical Rate Lookup** - Using last known margin rate for symbol. Fails when user changes leverage between positions.

## Hyperliquid

### Available Data
- **Per Position**: `positionValue`, `unrealizedPnl`
- **Account Level**: `accountValue`, `totalMarginUsed` ✅
- **Account Level**: `withdrawable` (available balance)
- **Cross-margin only** (all positions share margin pool)

### Calculation Approach

**PRIMARY METHOD: Total Margin Delta Tracking (IMPLEMENTED ✅)**

Hyperliquid provides `totalMarginUsed` in the `marginSummary` object, enabling the same margin delta approach as Apex!

```python
# Algorithm (identical to Apex):
1. Detect new position (first snapshot with size > 0)
2. Get previous totalMarginUsed from last equity snapshot  
3. Calculate delta: equity_used = current_margin - previous_margin
4. Calculate leverage: leverage = position_size_usd / equity_used

# Example:
Time T1: Total Margin Used = $0
Time T2: Open ETH position, Total Margin Used = $2,000
  → ETH equity used = $2,000
  → If position size = $20,000, leverage = 10x
```

**Key Insight**: Cross-margin works perfectly with margin delta! When you open a position, `totalMarginUsed` increases by exactly the margin for that position, making it trivial to isolate per-position leverage.

**FALLBACK METHOD: Old Estimation (DEPRECATED)**

Previous estimation-based approach is deprecated but retained for existing positions opened before tracking:
```python
# Old method - no longer used for new positions
if position_value >= account_equity:
    equity_used = account_equity × 0.6  # Assumption
else:
    equity_used = position_value × 0.8  # Assumption
```

**Implementation**: See [HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md](./HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md) for detailed documentation.

## Implementation Status

### Apex Omni
- ✅ Initial margin delta tracking (primary method)
- ✅ Using `customInitialMarginRate` as fallback
- ✅ Logging calculation method used
- ✅ Storing raw API data
- ✅ Tracking `calculation_method` in database
- ⚠️ Only works for NEW positions (existing positions use fallback)

### Hyperliquid  
- ✅ Total margin delta tracking (primary method)
- ✅ Using `totalMarginUsed` from marginSummary
- ✅ Identical algorithm to Apex
- ✅ Works perfectly with cross-margin
- ⚠️ Only works for NEW positions (existing positions use fallback)

## Recommendations

1. **For Apex Omni:**
   - ✅ Implemented: Initial margin delta tracking
   - ✅ Store calculation method for each position
   - Future: Backfill leverage for existing positions using historical data
   - Future: Handle position size changes (add to position)

2. **For Hyperliquid:**
   - Document that leverage is estimated
   - Consider allowing user to manually input leverage
   - Monitor for API updates that might provide per-position margin
   - Consider adapting margin delta approach if WebSocket provides order fill data

3. **General:**
   - ✅ Always store raw API responses
   - ✅ Log calculation methods used
   - Future: Provide UI indicators when values are estimated vs exact
   - Future: Add manual override option for leverage

## Adaptability to Other Exchanges

The **Initial Margin Delta Tracking** approach can be adapted to other exchanges that:

1. Provide total margin/equity used at account level
2. Don't provide per-position margin data
3. Allow snapshot-based monitoring

**Requirements:**
- Historical snapshots of account equity/margin
- Ability to detect when positions open
- API provides total margin used across all positions

**Exchanges where this could work:**
- Binance Futures (provides `totalInitialMargin` in account endpoint)
- Bybit (provides `usedMargin` in account endpoint)
- OKX (provides `imr` - initial margin requirement)

**Key principle:** When you can't get per-position data directly, track the total over time and infer individual values from changes.
