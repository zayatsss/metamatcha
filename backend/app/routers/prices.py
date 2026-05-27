from fastapi import APIRouter, Query

from app.brokers.manager import broker_manager

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("")
async def get_prices(symbols: str = Query(..., description="через запятую, напр. EURUSD,GBPUSD")) -> list[dict]:
    """Живые котировки Bid/Ask напрямую с подключённых MT5/MatchTrader.

    Символы без доступной цены (нет подключённого брокера / нет инструмента)
    просто опускаются из ответа."""
    requested = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    out: list[dict] = []
    for symbol in requested:
        quote = await broker_manager.get_quote(symbol)
        if quote is not None:
            out.append({"symbol": quote.symbol, "bid": quote.bid, "ask": quote.ask, "mid": quote.mid})
    return out
