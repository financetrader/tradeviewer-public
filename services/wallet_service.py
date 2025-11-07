"""Centralized wallet service for managing wallet connections."""
from typing import Optional, Tuple, List, Dict, Any
from apexomni.http_private_v3 import HttpPrivate_v3
from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_OMNI_MAIN_ARB
from db.database import get_session
from db.models import WalletConfig
from services.apex_client import LoggingApexClient
from services.hyperliquid_client import HyperliquidClient
from exceptions import WalletNotFoundError, WalletConfigurationError
from utils.logging_utils import get_app_logger


class WalletService:
    """Service for managing wallet connections and operations."""
    
    @staticmethod
    def get_connected_apex_wallet(session) -> Optional[WalletConfig]:
        """Get the first connected Apex Omni wallet from database."""
        return session.query(WalletConfig).filter(
            WalletConfig.provider == 'apex_omni',
            WalletConfig.status == 'connected'
        ).first()
    
    @staticmethod
    def create_apex_client(wallet: WalletConfig) -> HttpPrivate_v3:
        """Create Apex Omni API client from wallet config."""
        # Validate that credentials were successfully decrypted
        api_key = wallet.api_key
        api_secret = wallet.api_secret
        api_passphrase = wallet.api_passphrase

        if not api_key or not api_secret or not api_passphrase:
            raise WalletConfigurationError(
                "apex_omni",
                f"Failed to decrypt wallet credentials. The encryption key may have changed. "
                f"Please re-enter the API credentials for wallet '{wallet.name}' in the wallets page."
            )

        return HttpPrivate_v3(
            APEX_OMNI_HTTP_MAIN,
            network_id=NETWORKID_OMNI_MAIN_ARB,
            api_key_credentials={
                "key": api_key,
                "secret": api_secret,
                "passphrase": api_passphrase
            },
        )
    
    @staticmethod
    def get_admin_wallet_client(with_logging: bool = True) -> HttpPrivate_v3:
        """Get Apex Omni client from wallets page wallet configuration."""
        logger = get_app_logger()
        
        with get_session() as session:
            wallet = WalletService.get_connected_apex_wallet(session)
            if not wallet:
                logger.log_wallet_operation("get_client", "apex_omni", False, "No connected wallet found")
                raise WalletNotFoundError("apex_omni", "No connected Apex Omni wallet found. Please add and connect a wallet in the wallets page.")
            
            try:
                client = WalletService.create_apex_client(wallet)
                logger.log_wallet_operation("get_client", "apex_omni", True)
                return LoggingApexClient(client) if with_logging else client
            except Exception as e:
                logger.log_wallet_operation("get_client", "apex_omni", False, f"Client creation failed: {str(e)}")
                raise WalletConfigurationError("apex_omni", f"Failed to create client: {str(e)}")
    
    @staticmethod
    def get_admin_wallet_client_and_id() -> Tuple[HttpPrivate_v3, Optional[int]]:
        """Get client and wallet ID for admin wallet."""
        logger = get_app_logger()
        
        with get_session() as session:
            wallet = WalletService.get_connected_apex_wallet(session)
            if not wallet:
                logger.log_wallet_operation("get_client_and_id", "apex_omni", False, "No connected wallet found")
                raise WalletNotFoundError("apex_omni", "No connected Apex Omni wallet found")
            
            try:
                client = WalletService.create_apex_client(wallet)
                logger.log_wallet_operation("get_client_and_id", "apex_omni", True, f"Wallet ID: {wallet.id}")
                return client, wallet.id
            except Exception as e:
                logger.log_wallet_operation("get_client_and_id", "apex_omni", False, f"Client creation failed: {str(e)}")
                raise WalletConfigurationError("apex_omni", f"Failed to create client: {str(e)}")
    
    @staticmethod
    def get_wallet_by_id(wallet_id: int) -> Optional[WalletConfig]:
        """Get wallet by ID."""
        with get_session() as session:
            return session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
    
    @staticmethod
    def get_wallet_client_by_id(wallet_id: int, with_logging: bool = True):
        """Get client for specific wallet ID.

        Returns an Apex HttpPrivate_v3 or a HyperliquidClient depending on provider.
        """
        logger = get_app_logger()
        
        with get_session() as session:
            wallet = session.query(WalletConfig).filter(WalletConfig.id == wallet_id).first()
            if not wallet:
                logger.log_wallet_operation("get_client_by_id", "apex_omni", False, f"Wallet {wallet_id} not found")
                raise WalletNotFoundError("apex_omni", f"Wallet ID {wallet_id} not found")
            
            if wallet.status != 'connected':
                logger.log_wallet_operation("get_client_by_id", "apex_omni", False, f"Wallet {wallet_id} not connected")
                raise WalletConfigurationError("apex_omni", f"Wallet {wallet.name} is not connected")
            
            try:
                if wallet.provider == 'apex_omni':
                    client = WalletService.create_apex_client(wallet)
                    logger.log_wallet_operation("get_client_by_id", "apex_omni", True, f"Wallet ID: {wallet.id}")
                    return LoggingApexClient(client) if with_logging else client
                elif wallet.provider == 'hyperliquid':
                    logger.log_wallet_operation("get_client_by_id", "hyperliquid", True, f"Wallet ID: {wallet.id}")
                    return HyperliquidClient(wallet.wallet_address)
                else:
                    logger.log_wallet_operation("get_client_by_id", wallet.provider, False, f"Provider not supported")
                    raise WalletConfigurationError(wallet.provider, f"Provider {wallet.provider} not supported")
            except Exception as e:
                logger.log_wallet_operation("get_client_by_id", wallet.provider, False, f"Client creation failed: {str(e)}")
                raise WalletConfigurationError(wallet.provider, f"Failed to create client: {str(e)}")
    
    @staticmethod
    def get_all_connected_wallets() -> List[Dict[str, Any]]:
        """Get all connected wallets."""
        with get_session() as session:
            wallets = session.query(WalletConfig).filter(
                WalletConfig.status == 'connected'
            ).order_by(WalletConfig.name).all()
            # Return as list of dicts to avoid session issues
            return [{
                'id': w.id,
                'name': w.name,
                'provider': w.provider,
                'wallet_type': w.wallet_type,
                'status': w.status
            } for w in wallets]
