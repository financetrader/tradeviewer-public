"""Calculation utilities for position and P&L analysis."""
from typing import List, Dict, Any, Optional
from datetime import datetime


def estimate_equity_used(position_size_usd: float, leverage: Optional[float]) -> float:
    """Calculate equity used for a position given its size and leverage.
    
    Args:
        position_size_usd: Position size in USD
        leverage: Leverage multiplier
        
    Returns:
        Estimated equity used (position_size / leverage)
    """
    if not leverage or leverage == 0:
        return 0.0
    try:
        return round(float(position_size_usd) / float(leverage), 2)
    except Exception:
        return 0.0


def annotate_closed_pnl_equity_used(
    closed_pnl: List[Dict[str, Any]], 
    lev_history: Dict[str, List[Dict[str, Any]]]
) -> None:
    """Annotate each closed_pnl item with equityUsed using historical leverage data.
    
    We pick the latest leverage value for the symbol at or before the trade's close time.
    
    Args:
        closed_pnl: List of closed trade dicts to annotate (modified in-place)
        lev_history: Dict mapping symbol -> list of {timestamp, leverage} entries
    """
    def parse_ts(ts: str) -> Optional[datetime]:
        """Parse timestamp string to datetime object."""
        try:
            # createdAtFormatted is '%Y-%m-%d %H:%M'
            return datetime.strptime(ts, "%Y-%m-%d %H:%M")
        except Exception:
            try:
                return datetime.fromtimestamp(int(ts) / 1000)
            except Exception:
                return None

    for e in closed_pnl or []:
        sym: Optional[str] = e.get('symbol')
        ts: str = e.get('createdAtFormatted') or str(e.get('createdAt') or '')
        size: float = float(e.get('size', 0) or 0)
        price: float = float(e.get('price', 0) or 0)
        position_usd: float = round(abs(size) * price, 2)
        lev: Optional[float] = None
        series: List[Dict[str, Any]] = lev_history.get(sym) or [] if sym else []
        if series:
            t: Optional[datetime] = parse_ts(ts)
            latest: Optional[Dict[str, Any]] = None
            for item in series:
                it: Optional[datetime] = parse_ts(item.get('timestamp') or '')
                if t and it and it <= t:
                    latest = item
                elif t and it and it > t:
                    break
            if latest and latest.get('leverage'):
                lev = latest.get('leverage')
        e['equityUsed'] = estimate_equity_used(position_usd, lev if lev else 0)


