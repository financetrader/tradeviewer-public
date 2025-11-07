"""SQLite migration to add leverage column to closed_trades table.

Adds leverage column to store estimated leverage from position snapshots.
Safe to run multiple times.
"""
from sqlalchemy import create_engine, text
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wallet.db"
engine = create_engine(f"sqlite:///{DB_PATH}")


def column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade():
    """Add leverage column to closed_trades table."""
    with engine.begin() as conn:
        if not column_exists(conn, 'closed_trades', 'leverage'):
            conn.execute(text("ALTER TABLE closed_trades ADD COLUMN leverage REAL NULL;"))
            print(f"✓ Added leverage column to closed_trades table")
        else:
            print(f"✓ leverage column already exists in closed_trades table")


def downgrade():
    """Remove leverage column from closed_trades table."""
    # SQLite doesn't support DROP COLUMN directly, so we'd need to recreate the table
    # For now, just print a warning
    print("⚠ SQLite doesn't support DROP COLUMN. Manual table recreation required for downgrade.")


if __name__ == "__main__":
    upgrade()
    print(f"Migration complete at: {DB_PATH}")

