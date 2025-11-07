#!/usr/bin/env python3
"""
Backfill opened_at for existing position snapshots.

For each wallet_id + symbol combination:
- Find continuous position sessions (where size > 0)
- For each session, set opened_at to the timestamp of the first snapshot
"""

import sqlite3
import sys
from datetime import datetime, timedelta

def backfill_opened_at(db_path='/app/data/wallet.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Starting backfill of opened_at for position_snapshots...")
    print("=" * 80)
    
    # Get all unique wallet_id + symbol combinations
    cursor.execute("""
        SELECT DISTINCT wallet_id, symbol
        FROM position_snapshots
        WHERE wallet_id IS NOT NULL
        ORDER BY wallet_id, symbol
    """)
    
    combinations = cursor.fetchall()
    total_combinations = len(combinations)
    print(f"Found {total_combinations} wallet+symbol combinations to process\n")
    
    total_updated = 0
    
    for idx, (wallet_id, symbol) in enumerate(combinations, 1):
        # Get all snapshots for this wallet+symbol, ordered by timestamp
        cursor.execute("""
            SELECT id, timestamp, size
            FROM position_snapshots
            WHERE wallet_id = ? AND symbol = ?
            ORDER BY timestamp ASC
        """, (wallet_id, symbol))
        
        snapshots = cursor.fetchall()
        
        # Track position sessions (continuous periods where size > 0)
        current_session_opened = None
        updates = []
        
        for snap_id, timestamp, size in snapshots:
            if size > 0:
                if current_session_opened is None:
                    # New position session starts
                    current_session_opened = timestamp
                
                # All snapshots in this session get the same opened_at
                updates.append((current_session_opened, snap_id))
            else:
                # Position closed, reset for next session
                current_session_opened = None
        
        # Apply updates for this wallet+symbol
        if updates:
            cursor.executemany("""
                UPDATE position_snapshots
                SET opened_at = ?
                WHERE id = ?
            """, updates)
            
            total_updated += len(updates)
            
            if idx % 10 == 0 or idx == total_combinations:
                print(f"Progress: {idx}/{total_combinations} combinations processed, {total_updated} snapshots updated")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"✓ Backfill completed!")
    print(f"  Total snapshots updated: {total_updated}")
    print(f"  Wallet+Symbol combinations: {total_combinations}")
    
    return total_updated

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else '/app/data/wallet.db'
    backfill_opened_at(db_path)

