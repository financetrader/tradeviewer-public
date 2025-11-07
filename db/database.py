"""Database connection and session management."""
from pathlib import Path
from contextlib import contextmanager
import os
import stat
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from db.models import Base

# Database file location
DB_PATH = Path(__file__).parent.parent / "data" / "wallet.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Scoped session - lives for the request lifetime
session_scope = scoped_session(SessionLocal)


def set_database_permissions():
    """Set secure file permissions on database file (600 = owner read/write only)."""
    if DB_PATH.exists():
        try:
            # Skip chmod in Docker (permissions handled by volume mounts)
            if os.getenv('DOCKER_ENV') != 'true':
                DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
                print(f"✓ Database permissions set to 600 (owner read/write only)")
        except Exception as e:
            print(f"Warning: Could not set database permissions: {e}")


def create_all_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print(f"✓ Database tables created at: {DB_PATH}")
    set_database_permissions()


@contextmanager
def get_session() -> Session:
    """
    Context manager for database sessions using scoped_session.
    Sessions live for the request lifetime and are automatically cleaned up.

    Usage:
        with get_session() as session:
            # Use session here
            session.query(...)
    """
    session = session_scope()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    # Note: Don't close here - scoped_session is cleaned up in Flask teardown


def cleanup_session():
    """Clean up scoped session. Call this in Flask teardown."""
    session_scope.remove()


