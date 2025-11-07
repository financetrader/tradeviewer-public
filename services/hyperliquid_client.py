"""Hyperliquid read-only client.

This client provides minimal read-only access for:
- Testing connectivity via clearinghouseState
- Fetching balances and open positions
- Fetching historical user fills (trades)

Authentication is wallet-address based for read-only operations.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx


BASE_URL = "https://api.hyperliquid.xyz"


class HyperliquidClient:
    """Lightweight synchronous client for Hyperliquid read-only endpoints."""

    def __init__(self, wallet_address: str, timeout_seconds: float = 15.0) -> None:
        if not wallet_address or not wallet_address.startswith("0x") or len(wallet_address) != 42:
            raise ValueError(
                "Invalid Hyperliquid wallet address (must start with 0x and be 42 characters)"
            )
        self.wallet_address = wallet_address
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def _post_info(self, payload: Dict[str, Any]) -> httpx.Response:
        return self._client.post("/info", json=payload)

    def test_connection(self) -> bool:
        """Return True if clearinghouseState returns a valid JSON body."""
        resp = self._post_info({"type": "clearinghouseState", "user": self.wallet_address})
        if resp.status_code != 200:
            return False
        try:
            data = resp.json()
        except Exception:
            return False
        return isinstance(data, dict)

    def fetch_clearinghouse_state(self) -> Dict[str, Any]:
        resp = self._post_info({"type": "clearinghouseState", "user": self.wallet_address})
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def fetch_balances(self) -> List[Dict[str, Any]]:
        """Return a list of balances derived from clearinghouse state."""
        state = self.fetch_clearinghouse_state()
        balances: List[Dict[str, Any]] = []

        margin = state.get("marginSummary", {}) if isinstance(state, dict) else {}
        account_value = float(margin.get("accountValue", 0) or 0)
        
        # Calculate total unrealized PnL from positions
        positions = state.get("assetPositions", []) if isinstance(state, dict) else []
        total_unrealized_pnl = 0.0
        for p in positions:
            pos = p.get("position", {}) if isinstance(p, dict) else {}
            total_unrealized_pnl += float(pos.get("unrealizedPnl", 0) or 0)
        
        if account_value:
            balances.append(
                {
                    "asset": "USDC",
                    "amount": account_value,
                    "value_usd": account_value,
                    "unrealized_pnl": total_unrealized_pnl,  # Use sum of position unrealized PnL, not totalNtlPos
                }
            )

        for p in positions:
            pos = p.get("position", {}) if isinstance(p, dict) else {}
            coin = pos.get("coin", "")
            position_value = float(pos.get("positionValue", 0) or 0)
            if position_value != 0:
                balances.append(
                    {
                        "asset": coin,
                        "amount": float(pos.get("szi", 0) or 0),
                        "value_usd": abs(position_value),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0) or 0),
                    }
                )

        return balances

    def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """Return a list of open positions derived from clearinghouse state."""
        state = self.fetch_clearinghouse_state()
        out: List[Dict[str, Any]] = []
        positions = state.get("assetPositions", []) if isinstance(state, dict) else []
        for p in positions:
            pos = p.get("position", {}) if isinstance(p, dict) else {}
            size = float(pos.get("szi", 0) or 0)
            if size:
                out.append(
                    {
                        "asset": pos.get("coin", ""),
                        "side": "long" if size > 0 else "short",
                        "quantity": abs(size),
                        "price": float(pos.get("entryPx", 0) or 0),
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0) or 0),
                        "position_value": float(pos.get("positionValue", 0) or 0),  # Add positionValue
                        "timestamp": datetime.now(),
                    }
                )
        return out

    def fetch_trades(self, since_ms: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return a list of fills for the wallet via userFills.

        Args:
            since_ms: Optional epoch milliseconds to filter from.
            limit: Optional maximum number of fills to return.
        """
        payload: Dict[str, Any] = {"type": "userFills", "user": self.wallet_address}
        if since_ms is not None:
            payload["startTime"] = int(since_ms)
        if limit is not None:
            payload["n"] = int(limit)

        resp = self._post_info(payload)
        resp.raise_for_status()
        data = resp.json()
        out: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for t in data:
                if not isinstance(t, dict):
                    continue
                ts_ms = int(t.get("time", 0) or 0)
                ts = datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.now()
                out.append(
                    {
                        "asset": t.get("coin", ""),
                        "side": str(t.get("side", "")).lower(),
                        "quantity": float(t.get("sz", 0) or 0),
                        "price": float(t.get("px", 0) or 0),
                        "fee": abs(float(t.get("fee", 0) or 0)),
                        "realized_pnl": float(t.get("closedPnl", 0) or 0),
                        "timestamp": ts,
                    }
                )
                if limit and len(out) >= limit:
                    break
        return out


