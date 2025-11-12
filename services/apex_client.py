"""Apex Omni API client functions."""
import os
from typing import List, Dict, Any

from apexomni.http_private_v3 import HttpPrivate_v3
from apexomni.constants import (
    APEX_OMNI_HTTP_MAIN,
    APEX_OMNI_HTTP_TEST,
    NETWORKID_OMNI_MAIN_ARB,
    NETWORKID_TEST,
)

# Logging wrapper utilities
from services.exchange_logging import get_exchange_logger, jlog


class LoggingApexClient:
    """Proxy over HttpPrivate_v3 that logs requests and response summaries."""
    def __init__(self, inner: HttpPrivate_v3):
        self._inner = inner
        self._log = get_exchange_logger()
        self._exchange = "ApexOmni"

    def _log_call(self, method: str, params: Dict[str, Any], response: Any, extra: Dict[str, Any] = None):
        payload = {
            "exchange": self._exchange,
            "method": method,
            "params": params or {},
        }
        if isinstance(response, dict):
            payload["response_summary"] = {
                "keys": list(response.keys())[:20],
                "data_keys": list(response.get("data", {}).keys())[:20] if isinstance(response.get("data"), dict) else None,
                "data_len": len(response.get("data", [])) if isinstance(response.get("data"), list) else None,
            }
        else:
            payload["response_type"] = type(response).__name__
        if extra:
            payload.update(extra)
        jlog(self._log, payload)

    def get_account_v3(self, **kwargs):
        resp = self._inner.get_account_v3(**kwargs)
        levs = []
        try:
            for p in (resp or {}).get("positions", []):
                mr = float(p.get("customInitialMarginRate", 0) or 0)
                levs.append(1.0 / mr if mr > 0 else None)
        except Exception:
            pass
        self._log_call("get_account_v3", {}, resp, {"leverage_samples": [round(x, 2) if x else None for x in levs[:5]]})
        return resp

    def get_account_balance_v3(self, **kwargs):
        resp = self._inner.get_account_balance_v3(**kwargs)
        self._log_call("get_account_balance_v3", {}, resp)
        return resp

    def open_orders_v3(self, **kwargs):
        resp = self._inner.open_orders_v3(**kwargs)
        self._log_call("open_orders_v3", {}, resp)
        return resp

    def historical_pnl_v3(self, **kwargs):
        resp = self._inner.historical_pnl_v3(**kwargs)
        self._log_call("historical_pnl_v3", kwargs, resp)
        return resp

    def history_orders_v3(self, **kwargs):
        resp = self._inner.history_orders_v3(**kwargs)
        self._log_call("history_orders_v3", kwargs, resp)
        return resp

    def ticker_v3(self, **kwargs):
        resp = self._inner.ticker_v3(**kwargs)
        self._log_call("ticker_v3", kwargs, resp)
        return resp


def make_client(log_requests: bool = False) -> HttpPrivate_v3:
    """Create and return an authenticated Apex Omni API client.
    
    Returns:
        HttpPrivate_v3: Authenticated API client instance
        
    Raises:
        KeyError: If required environment variables are not set
    """
    key = os.environ["APEX_KEY"]
    secret = os.environ["APEX_SECRET"]
    passphrase = os.environ["APEX_PASSPHRASE"]
    network = os.getenv("APEX_NETWORK", "main").lower()

    if network == "test":
        base = HttpPrivate_v3(
            APEX_OMNI_HTTP_TEST,
            network_id=NETWORKID_TEST,
            api_key_credentials={"key": key, "secret": secret, "passphrase": passphrase},
            request_timeout=30,  # Increased from 10s to allow for paginated requests
        )
    else:
        base = HttpPrivate_v3(
            APEX_OMNI_HTTP_MAIN,
            network_id=NETWORKID_OMNI_MAIN_ARB,
            api_key_credentials={"key": key, "secret": secret, "passphrase": passphrase},
            request_timeout=30,  # Increased from 10s to allow for paginated requests
        )
    return LoggingApexClient(base) if log_requests else base


def get_all_fills(client: HttpPrivate_v3) -> List[Dict[str, Any]]:
    """Paginate through all trade history using history_orders_v3.
    
    Args:
        client: Authenticated Apex Omni API client
        
    Returns:
        List of filled orders (actual trades only)
    """
    all_orders = []
    page = 0
    page_limit = 100
    
    # Paginate through historical orders
    while True:
        result = client.history_orders_v3(limit=page_limit, page=page)
        
        # Parse response - expect {"data": {"orders": [...], "totalSize": N}}
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            orders = data.get("orders", [])
            
            if not orders:
                break
            
            # Only include FILLED orders (actual trades)
            filled_orders = [o for o in orders if isinstance(o, dict) and o.get("status") == "FILLED"]
            all_orders.extend(filled_orders)
            
            # Stop if we got fewer results than requested or reached totalSize
            total_size = data.get("totalSize", 0)
            if len(orders) < page_limit or len(all_orders) >= total_size:
                break
            
            page += 1
        else:
            break
    
    return all_orders

