# Jesse Server Integration Plan

**Status**: 📋 **PLANNING** - Next steps for real-time position tracking integration

**Last Updated**: 2025-11-18

---

## Overview

This plan outlines the integration of Jesse server for real-time position notifications and enhanced position tracking. Jesse will push notifications when positions change (opened/closed/updated), and this app will immediately fetch snapshots and actual information from exchanges.

---

## Phase 1: Jesse API Integration - Query for Positions

**Goal**: Query Jesse server to detect new positions and extract all information from API responses.

### Tasks

1. **Create Jesse Client Service**
   - File: `services/jesse_client.py`
   - Implement client to connect to Jesse server API
   - Methods:
     - `get_active_positions()` - Query current open positions
     - `get_position_history()` - Get historical position data
     - `get_position_details(position_id)` - Get full position details

2. **Position Data Extraction**
   - Extract all fields from Jesse API response:
     - Position ID, symbol, side, size, entry price
     - Timestamps (opened_at, updated_at)
     - Strategy name/ID
     - Exchange/wallet information
     - Any custom metadata Jesse provides
   - Store complete raw API response in `raw_data` JSON field

3. **Database Schema Updates**
   - Add `jesse_position_id` field to `position_snapshots` table (optional)
   - Add `source` field to track if position came from Jesse vs direct exchange query
   - Ensure `raw_data` field can store complete Jesse API response

4. **Integration Point**
   - Add Jesse position query to `refresh_wallet_data()` or create separate `refresh_jesse_positions()` function
   - Match Jesse positions to wallet_id based on exchange/wallet address
   - Store positions in `position_snapshots` with Jesse metadata

---

## Phase 2: Real-Time Notifications - Webhook Endpoint

**Goal**: Receive push notifications from Jesse when positions change (opened/closed/updated).

### Tasks

1. **Create Webhook Endpoint**
   - File: `app.py` - Add new route: `POST /api/jesse/webhook`
   - Accept JSON payload from Jesse server
   - Validate webhook signature/authentication
   - Handle rate limiting and security

2. **Webhook Payload Structure** (to be defined with Jesse)
   ```json
   {
     "event_type": "position_opened" | "position_closed" | "position_updated",
     "position_id": "...",
     "wallet_id": 123,
     "symbol": "BTC-USDT",
     "timestamp": "2025-11-18T12:00:00Z",
     "data": { /* full position data */ }
   }
   ```

3. **Event Handler**
   - File: `services/jesse_webhook_handler.py`
   - Process different event types:
     - `position_opened`: Fetch full position data, create snapshot
     - `position_closed`: Mark position as closed, sync final data
     - `position_updated`: Update existing position snapshot
   - Queue processing for async handling (avoid blocking webhook)

4. **Immediate Exchange Snapshot**
   - When notification received:
     - Immediately call `refresh_wallet_data(wallet_id)` to get latest exchange data
     - Or create targeted snapshot function that only fetches position data
   - Store both:
     - Jesse's position data (from webhook)
     - Exchange's actual position data (from API call)

---

## Phase 3: Data Synchronization & Conflict Resolution

**Goal**: Ensure Jesse data and exchange data stay synchronized.

### Tasks

1. **Dual Source Tracking**
   - Track positions from both sources:
     - Jesse notifications (real-time, strategy-driven)
     - Exchange API queries (scheduled, actual state)
   - Merge/reconcile when both sources have data

2. **Conflict Resolution Strategy**
   - Exchange API is source of truth for actual position state
   - Jesse data provides strategy context and metadata
   - When conflicts occur:
     - Log warning with both values
     - Prefer exchange data for position size/price
     - Keep Jesse data for strategy assignment

3. **Position Matching Logic**
   - Match Jesse positions to exchange positions by:
     - Symbol + Wallet ID
     - Timestamp proximity
     - Position size similarity
   - Handle edge cases:
     - Jesse reports position but exchange doesn't (position closed between notification and query)
     - Exchange has position but Jesse doesn't (manual trade or external position)

---

## Phase 4: Enhanced Position Tracking

**Goal**: Leverage Jesse data to improve position tracking and analytics.

### Tasks

1. **Strategy Assignment**
   - Use Jesse's strategy information to auto-assign strategies
   - Link Jesse strategy IDs to our `strategies` table
   - Auto-create strategy assignments when positions open

2. **Position Lifecycle Tracking**
   - Track complete position lifecycle:
     - Opened via Jesse notification
     - Updates via Jesse notifications
     - Closed via Jesse notification
   - Compare with exchange data for validation

3. **Analytics Enhancement**
   - Add Jesse-specific metrics:
     - Strategy performance from Jesse
     - Position entry/exit signals
     - Custom Jesse metadata analysis

---

## Implementation Priority

### High Priority (Immediate)
1. ✅ Enhanced logging (COMPLETED)
2. Phase 1: Jesse API client and position querying
3. Phase 2: Webhook endpoint for real-time notifications

### Medium Priority
4. Phase 3: Data synchronization and conflict resolution
5. Phase 4: Enhanced analytics

### Low Priority
6. Advanced features (strategy auto-assignment, custom metrics)

---

## Technical Considerations

### Security
- Webhook authentication (API key, signature validation)
- Rate limiting on webhook endpoint
- Input validation and sanitization

### Performance
- Async webhook processing (don't block Jesse's request)
- Efficient position matching algorithms
- Database indexing for fast lookups

### Reliability
- Webhook retry logic if exchange API call fails
- Queue system for webhook processing
- Fallback to scheduled queries if webhooks fail

---

## Questions to Resolve with Jesse Integration

1. What is Jesse's API endpoint URL and authentication method?
2. What is the exact webhook payload structure?
3. How do we authenticate webhook requests from Jesse?
4. What fields does Jesse provide in position data?
5. How do we map Jesse's wallet/exchange identifiers to our wallet_id?
6. What is the expected notification frequency?
7. Should we store Jesse position data separately or merge with exchange data?

---

## Related Documentation

- [Enhanced Logging Implementation](./README.md#enhanced-logging) - Completed logging improvements
- [Position Snapshots Schema](../README.md#position_snapshots) - Database structure for positions
- [Wallet Refresh Service](../services/wallet_refresh.py) - Current refresh implementation

---

## Notes

- This integration will complement the existing 30-minute scheduled refresh
- Real-time notifications will trigger immediate snapshots, reducing gaps in equity history
- Jesse data provides strategy context that exchange APIs don't provide
- Exchange API remains source of truth for actual position state

