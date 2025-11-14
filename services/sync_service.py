"""Synchronization helpers for importing closed trades from exchange fills."""
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from db import queries
from db.queries_strategies import resolve_strategy_id
from utils.data_utils import normalize_symbol


def sync_closed_trades_from_fills(session: Session, fills: List[Dict[str, Any]], wallet_id: Optional[int]) -> int:
    """Upsert closed trades from a list of FILLED orders (fills).

    Returns number of upserts attempted.
    """
    count = 0
    for o in (fills or []):
        try:
            created_ms = o.get('createdAt') or o.get('createdTime')
            if not created_ms:
                continue
            ts = datetime.fromtimestamp(int(created_ms) / 1000)
            sym = normalize_symbol(o.get('symbol') or o.get('symbolName') or '')

            # Resolve strategy_id at the time of the trade
            strategy_id = None
            if wallet_id and sym:
                strategy_id = resolve_strategy_id(session, wallet_id, sym, ts)

            # Look up leverage and equity_used from position snapshots (calculated when position was open)
            leverage, equity_used = queries.get_leverage_at_timestamp(session, wallet_id, sym, ts)

            data = {
                'timestamp': ts,
                'side': (o.get('positionSide') or o.get('side') or '').upper(),
                'symbol': sym,
                'size': float(o.get('size') or o.get('executedQty') or 0) or 0.0,
                'entry_price': float(o.get('latestMatchFillPrice') or o.get('avgFillPrice') or o.get('price') or o.get('avgPrice') or 0) or 0.0,
                'exit_price': float(o.get('latestMatchFillPrice') or o.get('avgFillPrice') or o.get('price') or o.get('avgPrice') or 0) or 0.0,
                'trade_type': (o.get('type') or o.get('orderType') or '').upper() or 'MARKET',
                'closed_pnl': float(o.get('totalPnl') or o.get('pnl') or 0) or 0.0,
                'close_fee': float(o.get('cumMatchFillFee') or o.get('fee') or 0) or None,
                'open_fee': None,
                'liquidate_fee': None,
                'exit_type': o.get('status'),
                'equity_used': equity_used,
                'leverage': leverage,
                'strategy_id': strategy_id,  # Add resolved strategy_id
                'reduce_only': o.get('reduceOnly'),  # True if closing position, False if opening
            }
            if data['symbol'] and data['timestamp']:
                queries.upsert_closed_trade(session, data, wallet_id)
                count += 1
        except Exception:
            continue
    return count


