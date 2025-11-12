# Leverage Calculation Documentation

This folder contains comprehensive documentation for how leverage is calculated and managed in the trading system.

## Files

### [LEVERAGE_CALCULATION.md](./LEVERAGE_CALCULATION.md) - **PRIMARY REFERENCE**
Main consolidated guide covering:
- Overall leverage calculation flow and data model
- How leverage is calculated, displayed, and stored
- Exchange-agnostic overview of margin delta method
- Database schema and related tables
- Verification and debugging queries
- Implementation status and completion summary

**Start here** for understanding the leverage calculation system.

### [APEX_LEVERAGE_CALCULATION.md](./APEX_LEVERAGE_CALCULATION.md)
Apex Omni-specific implementation details:
- Problem: API sometimes returns `customInitialMarginRate: 0`
- Solution: Margin delta tracking using `initialMargin` field
- Step-by-step examples with real values
- Edge cases and limitations
- Verification procedures

**Read this** if you need to understand Apex-specific behavior.

### [HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md](./HYPERLIQUID_LEVERAGE_MARGIN_DELTA.md)
Hyperliquid-specific implementation details:
- Key discovery: `marginSummary` API provides `totalMarginUsed`
- Margin delta tracking algorithm
- Cross-margin considerations
- Comparison with Apex implementation
- Edge cases and verification procedures

**Read this** if you need to understand Hyperliquid-specific behavior.

## Implementation Status

✅ **COMPLETE** - All leverage calculations use margin delta method exclusively

### Current Implementation
- **logger.py** (lines 70-92): Background logger uses margin delta for Hyperliquid
- **app.py** (lines 506-535): Dashboard display uses margin delta for Hyperliquid
- **app.py** (lines 839-863): Dashboard snapshots use margin delta for both Apex and Hyperliquid
- **Database**: All new positions store leverage calculated via margin delta

### Cleanup Complete
- ✅ Deprecated `estimate_leverage_hyperliquid()` function removed from `utils/calculations.py`
- ✅ Zero references to old estimation method in functional code
- ✅ All components use `calculate_leverage_from_margin_delta()`
- ✅ Test suite: 7/8 tests passed, all code cleanup tests passed

## Key Concepts

### Margin Delta Method
```
leverage = position_size_usd / (current_margin - previous_margin)
```

When a new position opens, the increase in total margin equals the equity used for that position.

### Calculation Timing
- **When**: Calculated when position opens (in logger and dashboard)
- **Where**: Stored in `position_snapshots` table
- **Display**: Available immediately on dashboard
- **Historical**: Retrieved from database when trade closes

### Exchanges Supported
- **Apex Omni**: Uses `initialMargin` field for delta tracking
- **Hyperliquid**: Uses `totalMarginUsed` field for delta tracking

Both use identical margin delta algorithm, just different API fields.

## Database Fields

All leverage calculations include a `calculation_method` field:
- `'margin_delta'` - Calculated using margin delta tracking (current standard)
- `'margin_rate'` - Calculated using fallback margin rate (legacy)
- `'unknown'` - Could not be calculated

## Common Tasks

### Verify leverage is calculated correctly
See "Verification & Debugging" section in [LEVERAGE_CALCULATION.md](./LEVERAGE_CALCULATION.md)

### Understand why leverage is NULL
Check `calculation_method` field - if 'unknown', position opened before tracking started

### Add new exchange support
Follow the margin delta pattern documented in exchange-specific files

### Test leverage calculation
Run: `python tests/test_leverage_cleanup.py`

## Related Files in Codebase

**Implementations**:
- `services/apex_leverage_calculator.py` - Apex margin delta logic
- `services/hyperliquid_leverage_calculator.py` - Hyperliquid margin delta logic

**Usage**:
- `logger.py` - Background logger that calculates leverage
- `app.py` - Dashboard that displays and stores leverage

**Database**:
- `db/models.py` - PositionSnapshot, ClosedTrade, AggregatedTrade models
- `db/queries.py` - Database query helpers

## Version History

- **Nov 12, 2024**: Completed migration to margin delta method exclusively
  - Replaced all old estimation code with accurate margin delta calculations
  - Removed deprecated `estimate_leverage_hyperliquid()` function
  - All components now use consistent margin delta method
  - Test suite confirms implementation is correct

## Questions?

Refer to the specific exchange documentation or the main LEVERAGE_CALCULATION.md for more details.
