#!/usr/bin/env python3
"""Insert mock BTC positions into database for leverage calculation testing.

This script simulates what the Apex API would return for 2 BTC positions
opened at different times, using ONLY fields that come from the actual API.

IMPORTANT: This does NOT calculate leverage - that's what the logger does!
After running this script, you must run the logger to calculate leverage.
"""

from datetime import datetime, timedelta
from db.database import get_session
from db.models import EquitySnapshot, PositionSnapshot

# Test data - simulates 2 BTC positions opened 10 minutes apart
WALLET_ID = 4

# Position 1: Opened at a specific time
POSITION_1_OPENED_AT = datetime.utcnow() - timedelta(minutes=30)
POSITION_1_DATA = {
    'symbol': 'BTC-USDT',
    'side': 'SHORT',
    'size': 0.001,  # Small test size
    'entryPrice': 89000.00,
    'markPrice': 89050.00,
    'positionValue': 89.00,  # 0.001 * 89000
    'unrealizedPnl': -0.05,
    'customInitialMarginRate': 0.0,  # Apex returns 0 for some positions
}

# Position 2: Opened 10 minutes after position 1
POSITION_2_OPENED_AT = datetime.utcnow() - timedelta(minutes=20)
POSITION_2_DATA = {
    'symbol': 'BTC-USDT',
    'side': 'LONG',
    'size': 0.002,  # Different size
    'entryPrice': 89100.00,
    'markPrice': 89080.00,
    'positionValue': 178.20,  # 0.002 * 89100
    'unrealizedPnl': -0.04,
    'customInitialMarginRate': 0.0,
}

# Equity snapshots to support leverage calculation
# These simulate the available_balance changes when positions open

# Baseline equity (before any positions)
EQUITY_BASELINE = {
    'timestamp': datetime.utcnow() - timedelta(minutes=40),
    'total_equity': 500.00,
    'available_balance': 500.00,
    'unrealized_pnl': 0.00,
    'realized_pnl': 0.00,
    'initial_margin': None,  # None when no positions open
}

# After position 1 opens (available balance decreases)
EQUITY_AFTER_POS1 = {
    'timestamp': POSITION_1_OPENED_AT + timedelta(seconds=5),
    'total_equity': 499.95,
    'available_balance': 495.55,  # Decreased by ~$4.45 (5% margin for 20x leverage)
    'unrealized_pnl': -0.05,
    'realized_pnl': 0.00,
    'initial_margin': 4.45,  # Now has value since position is open
}

# After position 2 opens (available balance decreases further)
EQUITY_AFTER_POS2 = {
    'timestamp': POSITION_2_OPENED_AT + timedelta(seconds=5),
    'total_equity': 499.91,
    'available_balance': 486.65,  # Decreased by ~$8.90 (5% margin for 20x leverage)
    'unrealized_pnl': -0.09,
    'realized_pnl': 0.00,
    'initial_margin': 13.35,  # Total margin for both positions
}


def insert_test_data():
    """Insert mock equity snapshots and position snapshots."""

    with get_session() as session:
        print("=== Inserting Test Data ===\n")

        # 1. Insert baseline equity snapshot
        print("1. Inserting baseline equity snapshot...")
        equity_baseline = EquitySnapshot(
            wallet_id=WALLET_ID,
            timestamp=EQUITY_BASELINE['timestamp'],
            total_equity=EQUITY_BASELINE['total_equity'],
            available_balance=EQUITY_BASELINE['available_balance'],
            unrealized_pnl=EQUITY_BASELINE['unrealized_pnl'],
            realized_pnl=EQUITY_BASELINE['realized_pnl'],
            initial_margin=EQUITY_BASELINE['initial_margin'],
        )
        session.add(equity_baseline)
        print(f"   Timestamp: {EQUITY_BASELINE['timestamp']}")
        print(f"   Available Balance: ${EQUITY_BASELINE['available_balance']:.2f}\n")

        # 2. Insert equity snapshot after position 1
        print("2. Inserting equity snapshot after Position 1...")
        equity_after_pos1 = EquitySnapshot(
            wallet_id=WALLET_ID,
            timestamp=EQUITY_AFTER_POS1['timestamp'],
            total_equity=EQUITY_AFTER_POS1['total_equity'],
            available_balance=EQUITY_AFTER_POS1['available_balance'],
            unrealized_pnl=EQUITY_AFTER_POS1['unrealized_pnl'],
            realized_pnl=EQUITY_AFTER_POS1['realized_pnl'],
            initial_margin=EQUITY_AFTER_POS1['initial_margin'],
        )
        session.add(equity_after_pos1)
        print(f"   Timestamp: {EQUITY_AFTER_POS1['timestamp']}")
        print(f"   Available Balance: ${EQUITY_AFTER_POS1['available_balance']:.2f}")
        print(f"   (We will calculate equity_used from delta: ${EQUITY_BASELINE['available_balance'] - EQUITY_AFTER_POS1['available_balance']:.2f})\n")

        # 3. Insert equity snapshot after position 2
        print("3. Inserting equity snapshot after Position 2...")
        equity_after_pos2 = EquitySnapshot(
            wallet_id=WALLET_ID,
            timestamp=EQUITY_AFTER_POS2['timestamp'],
            total_equity=EQUITY_AFTER_POS2['total_equity'],
            available_balance=EQUITY_AFTER_POS2['available_balance'],
            unrealized_pnl=EQUITY_AFTER_POS2['unrealized_pnl'],
            realized_pnl=EQUITY_AFTER_POS2['realized_pnl'],
            initial_margin=EQUITY_AFTER_POS2['initial_margin'],
        )
        session.add(equity_after_pos2)
        print(f"   Timestamp: {EQUITY_AFTER_POS2['timestamp']}")
        print(f"   Available Balance: ${EQUITY_AFTER_POS2['available_balance']:.2f}")
        print(f"   (We will calculate equity_used from delta: ${EQUITY_AFTER_POS1['available_balance'] - EQUITY_AFTER_POS2['available_balance']:.2f})\n")

        # 4. Insert position 1 snapshot (SHORT)
        print("4. Inserting Position 1 snapshot (SHORT)...")
        position_1 = PositionSnapshot(
            wallet_id=WALLET_ID,
            timestamp=POSITION_1_OPENED_AT,
            symbol=POSITION_1_DATA['symbol'],
            side=POSITION_1_DATA['side'],
            size=POSITION_1_DATA['size'],
            entry_price=POSITION_1_DATA['entryPrice'],
            current_price=POSITION_1_DATA['markPrice'],
            position_size_usd=POSITION_1_DATA['positionValue'],
            unrealized_pnl=POSITION_1_DATA['unrealizedPnl'],
            leverage=None,  # Will be calculated
            equity_used=None,  # Will be calculated
            calculation_method=None,  # Will be set by calculator
            raw_data={
                'symbol': POSITION_1_DATA['symbol'],
                'side': POSITION_1_DATA['side'],
                'size': str(POSITION_1_DATA['size']),
                'entryPrice': str(POSITION_1_DATA['entryPrice']),
                'markPrice': str(POSITION_1_DATA['markPrice']),
                'positionValue': str(POSITION_1_DATA['positionValue']),
                'unrealizedPnl': str(POSITION_1_DATA['unrealizedPnl']),
                'customInitialMarginRate': str(POSITION_1_DATA['customInitialMarginRate']),
            }
        )
        session.add(position_1)
        print(f"   Symbol: {POSITION_1_DATA['symbol']}")
        print(f"   Side: {POSITION_1_DATA['side']}")
        print(f"   Size: {POSITION_1_DATA['size']} BTC")
        print(f"   Entry: ${POSITION_1_DATA['entryPrice']:.2f}")
        print(f"   Position Size: ${POSITION_1_DATA['positionValue']:.2f}")
        print(f"   Opened at: {POSITION_1_OPENED_AT}\n")

        # 5. Insert position 2 snapshot (LONG)
        print("5. Inserting Position 2 snapshot (LONG)...")
        position_2 = PositionSnapshot(
            wallet_id=WALLET_ID,
            timestamp=POSITION_2_OPENED_AT,
            symbol=POSITION_2_DATA['symbol'],
            side=POSITION_2_DATA['side'],
            size=POSITION_2_DATA['size'],
            entry_price=POSITION_2_DATA['entryPrice'],
            current_price=POSITION_2_DATA['markPrice'],
            position_size_usd=POSITION_2_DATA['positionValue'],
            unrealized_pnl=POSITION_2_DATA['unrealizedPnl'],
            leverage=None,  # Will be calculated
            equity_used=None,  # Will be calculated
            calculation_method=None,  # Will be set by calculator
            raw_data={
                'symbol': POSITION_2_DATA['symbol'],
                'side': POSITION_2_DATA['side'],
                'size': str(POSITION_2_DATA['size']),
                'entryPrice': str(POSITION_2_DATA['entryPrice']),
                'markPrice': str(POSITION_2_DATA['markPrice']),
                'positionValue': str(POSITION_2_DATA['positionValue']),
                'unrealizedPnl': str(POSITION_2_DATA['unrealizedPnl']),
                'customInitialMarginRate': str(POSITION_2_DATA['customInitialMarginRate']),
            }
        )
        session.add(position_2)
        print(f"   Symbol: {POSITION_2_DATA['symbol']}")
        print(f"   Side: {POSITION_2_DATA['side']}")
        print(f"   Size: {POSITION_2_DATA['size']} BTC")
        print(f"   Entry: ${POSITION_2_DATA['entryPrice']:.2f}")
        print(f"   Position Size: ${POSITION_2_DATA['positionValue']:.2f}")
        print(f"   Opened at: {POSITION_2_OPENED_AT}\n")

        # Commit all changes
        session.commit()

        print("✓ Test data inserted successfully!\n")
        print("=== Expected Leverage Calculations ===")
        print(f"Position 1 (SHORT):")
        print(f"  Equity delta: ${EQUITY_BASELINE['available_balance'] - EQUITY_AFTER_POS1['available_balance']:.2f}")
        print(f"  Position size: ${POSITION_1_DATA['positionValue']:.2f}")
        print(f"  Expected leverage: {POSITION_1_DATA['positionValue'] / (EQUITY_BASELINE['available_balance'] - EQUITY_AFTER_POS1['available_balance']):.1f}x\n")

        print(f"Position 2 (LONG):")
        print(f"  Equity delta: ${EQUITY_AFTER_POS1['available_balance'] - EQUITY_AFTER_POS2['available_balance']:.2f}")
        print(f"  Position size: ${POSITION_2_DATA['positionValue']:.2f}")
        print(f"  Expected leverage: {POSITION_2_DATA['positionValue'] / (EQUITY_AFTER_POS1['available_balance'] - EQUITY_AFTER_POS2['available_balance']):.1f}x\n")

        return {
            'position_1_timestamp': POSITION_1_OPENED_AT,
            'position_2_timestamp': POSITION_2_OPENED_AT,
            'equity_baseline_timestamp': EQUITY_BASELINE['timestamp'],
            'equity_after_pos1_timestamp': EQUITY_AFTER_POS1['timestamp'],
            'equity_after_pos2_timestamp': EQUITY_AFTER_POS2['timestamp'],
        }


if __name__ == '__main__':
    timestamps = insert_test_data()

    print("\nTest data inserted. Timestamps:")
    for key, value in timestamps.items():
        print(f"  {key}: {value}")
