#!/usr/bin/env python3
"""
Backfill position_id for existing position snapshots.

This script:
1. Identifies unique position "sessions" (continuous periods with size > 0)
2. Creates Position records for each session
3. Updates position_snapshots with the corresponding position_id

A new position starts when:
- It's the first snapshot for this wallet+symbol+side, OR
- The previous snapshot had size = 0 (position was closed and reopened)

Positions are processed in order of first opened (oldest first).

Run with: python3 scripts/backfill_position_ids.py [db_path]
Default db_path: data/wallet.db
"""

import sqlite3
import sys
from datetime import datetime
from collections import defaultdict


def backfill_position_ids(db_path='data/wallet.db'):
    """Backfill position_id for existing position snapshots."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("Backfill Position IDs")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Started at: {datetime.now()}")
    print()
    
    try:
        # Get all unique wallet_id + symbol + side combinations (excluding NO_POSITIONS marker)
        cursor.execute("""
            SELECT DISTINCT wallet_id, symbol, side
            FROM position_snapshots
            WHERE wallet_id IS NOT NULL
              AND symbol != 'NO_POSITIONS'
              AND size > 0
            ORDER BY wallet_id, symbol, side
        """)
        
        combinations = cursor.fetchall()
        total_combinations = len(combinations)
        print(f"Found {total_combinations} wallet+symbol+side combinations to process\n")
        
        # Track all position sessions with their first timestamp
        # Structure: [(first_opened_at, wallet_id, symbol, side, [snapshot_ids])]
        all_sessions = []
        
        # Process each combination to find position sessions
        for wallet_id, symbol, side in combinations:
            # Get all snapshots for this combination, ordered by timestamp
            cursor.execute("""
                SELECT id, timestamp, size
                FROM position_snapshots
                WHERE wallet_id = ? AND symbol = ? AND side = ?
                ORDER BY timestamp ASC
            """, (wallet_id, symbol, side))
            
            snapshots = cursor.fetchall()
            
            # Track sessions (continuous periods where size > 0)
            current_session = None  # (first_timestamp, [snapshot_ids])
            
            for snap_id, timestamp, size in snapshots:
                if size > 0:
                    if current_session is None:
                        # New session starts
                        current_session = (timestamp, [snap_id])
                    else:
                        # Continue existing session
                        current_session[1].append(snap_id)
                else:
                    # Position closed, save current session if exists
                    if current_session is not None:
                        all_sessions.append((
                            current_session[0],  # first_opened_at
                            wallet_id,
                            symbol,
                            side,
                            current_session[1]  # snapshot_ids
                        ))
                        current_session = None
            
            # Don't forget the last session if position is still open
            if current_session is not None:
                all_sessions.append((
                    current_session[0],
                    wallet_id,
                    symbol,
                    side,
                    current_session[1]
                ))
        
        print(f"Found {len(all_sessions)} position sessions to create\n")
        
        # Sort sessions by first_opened_at (oldest first) to assign IDs in order
        all_sessions.sort(key=lambda x: x[0])
        
        # Create Position records and update snapshots
        positions_created = 0
        snapshots_updated = 0
        
        for first_opened_at, wallet_id, symbol, side, snapshot_ids in all_sessions:
            # Get entry price from first snapshot
            cursor.execute("""
                SELECT entry_price FROM position_snapshots WHERE id = ?
            """, (snapshot_ids[0],))
            entry_price_row = cursor.fetchone()
            entry_price = entry_price_row[0] if entry_price_row else None
            
            # Check if position was closed (look for a size=0 snapshot after the last one)
            last_snapshot_id = snapshot_ids[-1]
            cursor.execute("""
                SELECT timestamp FROM position_snapshots WHERE id = ?
            """, (last_snapshot_id,))
            last_ts_row = cursor.fetchone()
            last_timestamp = last_ts_row[0] if last_ts_row else None
            
            # Check if there's a zero-size snapshot or no more snapshots
            # (meaning position is closed)
            closed_at = None
            exit_price = None
            realized_pnl = None
            
            if last_timestamp:
                cursor.execute("""
                    SELECT timestamp FROM position_snapshots
                    WHERE wallet_id = ? AND symbol = ? AND side = ?
                      AND timestamp > ?
                      AND (size = 0 OR size IS NULL OR symbol = 'NO_POSITIONS')
                    ORDER BY timestamp ASC
                    LIMIT 1
                """, (wallet_id, symbol, side, last_timestamp))
                close_row = cursor.fetchone()
                if close_row:
                    closed_at = close_row[0]
                    
                    # Try to get exit price and PnL from aggregated_trades
                    cursor.execute("""
                        SELECT avg_exit_price, total_pnl FROM aggregated_trades
                        WHERE wallet_id = ? AND symbol = ? AND side = ?
                          AND timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (wallet_id, symbol, side, first_opened_at, closed_at))
                    trade_row = cursor.fetchone()
                    if trade_row:
                        exit_price = trade_row[0]
                        realized_pnl = trade_row[1]
            
            # Create Position record
            cursor.execute("""
                INSERT INTO positions (wallet_id, symbol, side, opened_at, closed_at, entry_price, exit_price, realized_pnl, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (wallet_id, symbol, side, first_opened_at, closed_at, entry_price, exit_price, realized_pnl, datetime.utcnow()))
            
            position_id = cursor.lastrowid
            positions_created += 1
            
            # Update all snapshots in this session with the position_id
            for snap_id in snapshot_ids:
                cursor.execute("""
                    UPDATE position_snapshots
                    SET position_id = ?, opened_at = ?
                    WHERE id = ?
                """, (position_id, first_opened_at, snap_id))
                snapshots_updated += 1
            
            # Progress update
            if positions_created % 10 == 0:
                print(f"  Progress: {positions_created}/{len(all_sessions)} positions created...")
        
        conn.commit()
        
        print("\n" + "=" * 80)
        print("Backfill completed successfully!")
        print("=" * 80)
        print(f"  Positions created: {positions_created}")
        print(f"  Snapshots updated: {snapshots_updated}")
        print(f"  Wallet+Symbol+Side combinations: {total_combinations}")
        
        # Show summary of positions
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN closed_at IS NULL THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN closed_at IS NOT NULL THEN 1 ELSE 0 END) as closed_count
            FROM positions
        """)
        summary = cursor.fetchone()
        print(f"\nPosition Summary:")
        print(f"  Total positions: {summary[0]}")
        print(f"  Open positions: {summary[1]}")
        print(f"  Closed positions: {summary[2]}")
        
        return positions_created, snapshots_updated
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/wallet.db'
    backfill_position_ids(db_path)

