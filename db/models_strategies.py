"""Strategy models.

Defines strategy catalog and time-bounded assignments per wallet and symbol.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship

from db.models import Base


class Strategy(Base):
    __tablename__ = 'strategies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Strategy(id={self.id}, name='{self.name}')>"


class StrategyAssignment(Base):
    __tablename__ = 'strategy_assignments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, nullable=False)
    symbol = Column(String(50), nullable=False)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    start_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    is_current = Column(Boolean, default=True)  # Whether pair is currently in use
    notes = Column(String(500), nullable=True)  # User comments/notes
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    strategy = relationship("Strategy")

    __table_args__ = (
        Index('idx_assign_wallet_symbol_time', 'wallet_id', 'symbol', 'start_at', 'end_at'),
        Index('idx_assign_active', 'active'),
    )


