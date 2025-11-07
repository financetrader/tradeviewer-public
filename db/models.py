"""SQLAlchemy models for wallet database."""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Index, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class WalletConfig(Base):
    """Wallet configuration storage."""
    __tablename__ = 'wallet_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    # Optional friendly name for the API credential
    api_name = Column(String(255), nullable=True)
    provider = Column(String(50), nullable=False)  # 'apex_omni', 'hyperliquid', 'property'
    wallet_type = Column(String(50), nullable=False)  # 'crypto', 'stocks', 'property'
    
    # Credentials (encrypted)
    _api_key_encrypted = Column('api_key', String(1000), nullable=True)
    _api_secret_encrypted = Column('api_secret', String(1000), nullable=True)
    _api_passphrase_encrypted = Column('api_passphrase', String(1000), nullable=True)
    wallet_address = Column(String(500), nullable=True)
    
    # Property-specific fields
    asset_name = Column(String(255), nullable=True)
    asset_value = Column(Float, nullable=True)
    asset_currency = Column(String(10), nullable=True)
    
    # Status tracking
    status = Column(String(50), default='not_tested')  # 'not_tested', 'connected', 'error'
    last_test = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def api_key(self):
        """Decrypt and return API key."""
        if not self._api_key_encrypted:
            return None
        from utils.encryption import decrypt_credential
        return decrypt_credential(self._api_key_encrypted)

    @api_key.setter
    def api_key(self, value):
        """Encrypt and store API key."""
        if value is None:
            self._api_key_encrypted = None
        else:
            from utils.encryption import encrypt_credential
            self._api_key_encrypted = encrypt_credential(value)

    @property
    def api_secret(self):
        """Decrypt and return API secret."""
        if not self._api_secret_encrypted:
            return None
        from utils.encryption import decrypt_credential
        return decrypt_credential(self._api_secret_encrypted)

    @api_secret.setter
    def api_secret(self, value):
        """Encrypt and store API secret."""
        if value is None:
            self._api_secret_encrypted = None
        else:
            from utils.encryption import encrypt_credential
            self._api_secret_encrypted = encrypt_credential(value)

    @property
    def api_passphrase(self):
        """Decrypt and return API passphrase."""
        if not self._api_passphrase_encrypted:
            return None
        from utils.encryption import decrypt_credential
        return decrypt_credential(self._api_passphrase_encrypted)

    @api_passphrase.setter
    def api_passphrase(self, value):
        """Encrypt and store API passphrase."""
        if value is None:
            self._api_passphrase_encrypted = None
        else:
            from utils.encryption import encrypt_credential
            self._api_passphrase_encrypted = encrypt_credential(value)

    def __repr__(self):
        return f"<WalletConfig(id={self.id}, name='{self.name}', provider='{self.provider}', status='{self.status}')>"


class EquitySnapshot(Base):
    """Historical equity and P&L snapshots."""
    __tablename__ = 'equity_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, nullable=True)  # Legacy: use wallet_address instead
    wallet_address = Column(String(500), nullable=True)  # Primary key for wallet association
    timestamp = Column(DateTime, nullable=False, index=True)
    total_equity = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    available_balance = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    initial_margin = Column(Float, nullable=True)  # Track total margin used (Apex only)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_equity_wallet_timestamp', 'wallet_address', 'timestamp'),
        Index('idx_equity_wallet_id_timestamp', 'wallet_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<EquitySnapshot(timestamp={self.timestamp}, total_equity={self.total_equity})>"


class PositionSnapshot(Base):
    """Historical position snapshots with metrics."""
    __tablename__ = 'position_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, nullable=True)  # Legacy: use wallet_address instead
    wallet_address = Column(String(500), nullable=True)  # Primary key for wallet association
    timestamp = Column(DateTime, nullable=False)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # LONG or SHORT
    size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    position_size_usd = Column(Float, nullable=False)
    leverage = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    funding_fee = Column(Float, nullable=True)
    equity_used = Column(Float, nullable=True)
    strategy_id = Column(Integer, nullable=True)  # Foreign key to Strategy
    raw_data = Column(JSON, nullable=True)  # Store complete API response
    initial_margin_at_open = Column(Float, nullable=True)  # Total margin when position opened
    calculation_method = Column(String(20), nullable=True)  # How leverage was calculated
    created_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)  # When position was first opened (calculated from first snapshot with size > 0)

    __table_args__ = (
        Index('idx_position_wallet_symbol_timestamp', 'wallet_address', 'symbol', 'timestamp'),
        Index('idx_position_wallet_timestamp', 'wallet_address', 'timestamp'),
        Index('idx_position_wallet_id_symbol_timestamp', 'wallet_id', 'symbol', 'timestamp'),
        Index('idx_position_wallet_id_timestamp', 'wallet_id', 'timestamp'),
        Index('idx_position_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_position_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<PositionSnapshot(timestamp={self.timestamp}, symbol={self.symbol}, side={self.side})>"


class ClosedTrade(Base):
    """Historical closed trades with P&L."""
    __tablename__ = 'closed_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, nullable=True)  # Legacy: use wallet_address instead
    wallet_address = Column(String(500), nullable=True)  # Primary key for wallet association
    timestamp = Column(DateTime, nullable=False)
    side = Column(String(10), nullable=False)  # LONG or SHORT
    symbol = Column(String(50), nullable=False)
    size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    trade_type = Column(String(10), nullable=False)  # BUY or SELL
    closed_pnl = Column(Float, nullable=False)
    close_fee = Column(Float, nullable=True)
    open_fee = Column(Float, nullable=True)
    liquidate_fee = Column(Float, nullable=True)
    exit_type = Column(String(20), nullable=True)  # Trade or Liquidation
    equity_used = Column(Float, nullable=True)
    leverage = Column(Float, nullable=True)  # Estimated leverage from position snapshots
    strategy_id = Column(Integer, nullable=True)  # Foreign key to Strategy
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_closed_wallet_symbol_timestamp', 'wallet_address', 'symbol', 'timestamp'),
        Index('idx_closed_wallet_timestamp', 'wallet_address', 'timestamp'),
        Index('idx_closed_wallet_id_symbol_timestamp', 'wallet_id', 'symbol', 'timestamp'),
        Index('idx_closed_wallet_id_timestamp', 'wallet_id', 'timestamp'),
        Index('idx_closed_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_closed_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<ClosedTrade(timestamp={self.timestamp}, symbol={self.symbol}, closed_pnl={self.closed_pnl})>"
