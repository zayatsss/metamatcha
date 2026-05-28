"""Фоновый воркер сопровождения сделок.

Логика цикла:
  1) загрузить все «взведённые» триггеры (is_armed=True, is_fired=False);
  2) сгруппировать по символу, чтобы цену каждого символа тянуть один раз;
  3) сравнить текущую цену с target_price с учётом направления пересечения;
  4) при срабатывании — выполнить действие на нужных аккаунтах и пометить fired.

Определение пересечения: запоминаем последнюю виденную цену по символу и ловим
момент, когда линия target_price оказалась между прошлой и текущей ценой
(переход через уровень в любую сторону). Это надёжнее простого «price >= target»,
потому что не зависит от того, сверху или снизу подошла цена.

Воркер запускается как asyncio.Task на старте приложения (lifespan в main.py).
Один процесс = один воркер. Для отказоустойчивости используем БД как источник
правды о состоянии триггеров (is_fired), поэтому перезапуск не повторит действие.
"""

import asyncio
import logging

from app.brokers.manager import broker_manager
from app.config import settings
from app.database import SessionLocal
from app.models import Account, OrderSide, Trigger, TriggerAction

logger = logging.getLogger("trigger_monitor")


class TriggerMonitor:
    def __init__(self, poll_interval: float | None = None) -> None:
        self._interval = poll_interval or settings.trigger_poll_interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_price: dict[str, float] = {}

    def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._loop(), name="trigger-monitor")
            logger.info("TriggerMonitor started (interval=%.2fs)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001 — воркер не должен падать целиком
                logger.exception("trigger monitor tick failed")
            await asyncio.sleep(self._interval)

    def _crossed(self, symbol: str, target: float, price: float) -> bool:
        prev = self._last_price.get(symbol)
        self._last_price[symbol] = price
        if prev is None:
            return False
        lo, hi = sorted((prev, price))
        return lo <= target <= hi

    async def _tick(self) -> None:
        db = SessionLocal()
        try:
            triggers = (
                db.query(Trigger)
                .filter(Trigger.is_armed.is_(True), Trigger.is_fired.is_(False))
                .all()
            )
            if not triggers:
                return

            symbols = {t.symbol for t in triggers}
            prices = await self._fetch_prices(symbols)

            for trig in triggers:
                price = prices.get(trig.symbol)
                if price is None:
                    continue
                if self._crossed(trig.symbol, trig.target_price, price):
                    await self._fire(db, trig)
        finally:
            db.close()

    async def _fetch_prices(self, symbols: set[str]) -> dict[str, float]:
        """Берём цену по каждому символу у первого доступного подключённого адаптера."""
        prices: dict[str, float] = {}
        adapters = list(broker_manager.active_adapters().values())
        for symbol in symbols:
            for adapter in adapters:
                try:
                    if await adapter.is_connected():
                        prices[symbol] = await adapter.get_price(symbol)
                        break
                except Exception:  # noqa: BLE001
                    continue
        return prices

    async def _fire(self, db, trig: Trigger) -> None:
        targets = self._resolve_accounts(db, trig)
        logger.info("Trigger %s fired (%s @ %.5f) on %d accounts", trig.id, trig.action, trig.target_price, len(targets))

        results = await asyncio.gather(
            *[self._apply_action(acc, trig) for acc in targets],
            return_exceptions=True,
        )
        for acc, res in zip(targets, results):
            if isinstance(res, Exception):
                logger.error("trigger %s on account %s failed: %s", trig.id, acc.id, res)

        trig.is_fired = True
        from app.models import utcnow

        trig.fired_at = utcnow()
        db.commit()

    def _resolve_accounts(self, db, trig: Trigger) -> list[Account]:
        # account_id=None => действие на ВСЕ активные аккаунты сделки.
        if trig.account_id is not None:
            acc = db.get(Account, trig.account_id)
            return [acc] if acc and acc.is_active else []
        return db.query(Account).filter(Account.is_active.is_(True)).all()

    async def _apply_action(self, account: Account, trig: Trigger) -> None:
        adapter = await broker_manager.get_adapter(account)
        positions = await adapter.get_positions(trig.symbol)
        if not positions:
            return

        for pos in positions:
            if trig.action == TriggerAction.BREAK_EVEN:
                await adapter.modify_sl(pos.ticket, pos.entry_price)

            elif trig.action == TriggerAction.CUSTOM_SL_MOVE:
                if trig.new_sl_price is not None:
                    await adapter.modify_sl(pos.ticket, trig.new_sl_price)

            elif trig.action == TriggerAction.PARTIAL_TP:
                pct = (trig.partial_percent or 0) / 100.0
                close_volume = round(pos.volume * pct, 2)
                if close_volume > 0:
                    await adapter.close_partial(pos.ticket, close_volume)


trigger_monitor = TriggerMonitor()
