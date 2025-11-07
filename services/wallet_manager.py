"""Wallet connection testing functions for different providers."""
import os
import httpx
from typing import Tuple
from apexomni.http_private_v3 import HttpPrivate_v3
from apexomni.constants import (
    APEX_OMNI_HTTP_MAIN,
    NETWORKID_OMNI_MAIN_ARB,
)


def test_apex_connection(api_key: str, api_secret: str, api_passphrase: str) -> Tuple[bool, str]:
    """Test Apex Omni connection."""
    try:
        if not all([api_key, api_secret, api_passphrase]):
            return False, "Missing required credentials (API Key, Secret, or Passphrase)"
        
        client = HttpPrivate_v3(
            APEX_OMNI_HTTP_MAIN,
            network_id=NETWORKID_OMNI_MAIN_ARB,
            api_key_credentials={"key": api_key, "secret": api_secret, "passphrase": api_passphrase},
        )
        
        account_info = client.get_account_v3()
        
        if account_info and isinstance(account_info, dict):
            # Check if we have valid account data
            if 'contractWallets' in account_info or 'spotWallets' in account_info:
                return True, "Successfully connected to Apex Omni"
            else:
                return False, "Connection failed - invalid account data"
        else:
            return False, "Connection failed - invalid response from Apex API"
            
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def test_hyperliquid_connection(wallet_address: str) -> Tuple[bool, str]:
    """Test Hyperliquid connection."""
    try:
        if not wallet_address:
            return False, "Wallet address is required"
        
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return False, "Invalid wallet address format (must start with 0x and be 42 characters)"
        
        base_url = "https://api.hyperliquid.xyz"
        endpoint = "/info"
        payload = {
            "type": "clearinghouseState",
            "user": wallet_address
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{base_url}{endpoint}", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    if 'marginSummary' in data or 'assetPositions' in data:
                        return True, f"Successfully connected to Hyperliquid (Wallet: {wallet_address[:10]}...)"
                    else:
                        return False, "Wallet address not found or has no activity on Hyperliquid"
                else:
                    return False, "Invalid response format from Hyperliquid API"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
    except httpx.TimeoutException:
        return False, "Connection timeout - Hyperliquid API may be slow"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def test_property_wallet(asset_name: str, asset_value: float, asset_currency: str = "USD") -> Tuple[bool, str]:
    """Validate property wallet data."""
    try:
        if not asset_name or not asset_name.strip():
            return False, "Asset name is required"
        
        if asset_value is None or asset_value <= 0:
            return False, "Asset value must be greater than 0"
        
        if not asset_currency or len(asset_currency) != 3:
            return False, "Currency must be a 3-letter code (e.g., USD)"
        
        return True, f"Property wallet validated: {asset_name} worth {asset_currency} {asset_value:,.2f}"
        
    except Exception as e:
        return False, f"Validation failed: {str(e)}"


def get_provider_instructions(provider: str) -> dict:
    """Get setup instructions for each provider."""
    instructions = {
        'apex_omni': {
            'title': 'Apex Omni Setup',
            'description': 'Connect your Apex Omni trading account',
            'fields': [
                {
                    'name': 'api_key',
                    'label': 'API Key',
                    'type': 'text',
                    'required': True,
                    'help': 'Your Apex Omni API key'
                },
                {
                    'name': 'api_secret',
                    'label': 'API Secret',
                    'type': 'password',
                    'required': True,
                    'help': 'Your Apex Omni API secret'
                },
                {
                    'name': 'api_passphrase',
                    'label': 'API Passphrase',
                    'type': 'password',
                    'required': True,
                    'help': 'Your Apex Omni API passphrase'
                },
                {
                    'name': 'network',
                    'label': 'Network',
                    'type': 'select',
                    'required': True,
                    'options': [('main', 'Mainnet'), ('test', 'Testnet')],
                    'help': 'Choose mainnet for live trading or testnet for testing'
                }
            ],
            'setup_steps': [
                '1. Log into your Apex Omni account',
                '2. Go to API Management section',
                '3. Create a new API key with read permissions',
                '4. Copy your API Key, Secret, and Passphrase',
                '5. Select Mainnet for live trading or Testnet for testing'
            ]
        },
        'hyperliquid': {
            'title': 'Hyperliquid Setup',
            'description': 'Connect your Hyperliquid wallet',
            'fields': [
                {
                    'name': 'wallet_address',
                    'label': 'Wallet Address',
                    'type': 'text',
                    'required': True,
                    'help': 'Your Ethereum wallet address (starts with 0x)'
                }
            ],
            'setup_steps': [
                '1. Go to https://app.hyperliquid.xyz',
                '2. Connect your wallet',
                '3. Copy your wallet address from the top-right corner',
                '4. Paste the wallet address below (starts with 0x)',
                '5. No API keys needed - Hyperliquid uses wallet addresses for read access'
            ]
        },
        'property': {
            'title': 'Property/Fixed Assets Setup',
            'description': 'Add fixed assets like real estate, vehicles, equipment',
            'fields': [
                {
                    'name': 'asset_name',
                    'label': 'Asset Name',
                    'type': 'text',
                    'required': True,
                    'help': 'Name or description of the asset (e.g., "123 Main St, Apartment")'
                },
                {
                    'name': 'asset_value',
                    'label': 'Current Value',
                    'type': 'number',
                    'required': True,
                    'help': 'Current estimated value of the asset'
                },
                {
                    'name': 'asset_currency',
                    'label': 'Currency',
                    'type': 'text',
                    'required': True,
                    'default': 'USD',
                    'help': 'Currency code (USD, EUR, etc.)'
                }
            ],
            'setup_steps': [
                '1. Enter a descriptive name for your asset',
                '2. Set the current estimated value',
                '3. Choose the currency (USD, EUR, etc.)',
                '4. This will be used for tracking your total net worth'
            ]
        }
    }
    
    return instructions.get(provider, {
        'title': 'Unknown Provider',
        'description': 'Provider not found',
        'fields': [],
        'setup_steps': ['Provider setup instructions not available']
    })
