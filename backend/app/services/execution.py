"""Исполнение сделки в один клик на всех выбранных аккаунтах.

Каждый аккаунт обслуживается НЕЗАВИСИМО и тянет свои данные со своего же
подключения к брокеру:
  1) живой баланс счёта,
  2) спецификацию инструмента (contract_size / tick_value зависят от валюты
     счёта и потому у каждого аккаунта свои),
  3) свою рыночную цену (для market-ордера — дистанция SL считается от цены
     именно этого брокера; цены у разных брокеров могут отличаться),
  4) считает индивидуальный лот по риску аккаунта,
  5) отправляет ордер.
Аккаунты обрабатываются параллельно (asyncio.gather), чтобы вход был
максимально одновременным.

Важно: внутри gather мы НЕ трогаем БД-сессию (она не предназначена для
конкурентного использования) — живые балансы возвращаем наружу и пишем в БД
последовательно уже после сбора результатов.
"""

import asyncio
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.brokers.manager import broker_manager
from app.models import Account, OrderSide, OrderType, TradeGroup
from app.risk import calculate_lot_from_prices


@dataclass
class AccountExecution:
    account_id: int
    label: str
    ok: bool
    lot: float | None = None
    balance: float | None = None        # живой баланс, подтянутый с брокера
    reference_price: float | None = None  # цена, от которой считалась дистанция SL
    risk_amount: float | None = None
    ticket: str | None = None
    message: str = ""


async def _execute_on_account(
    account: Account,
    *,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    entry_price: float | None,
    sl_price: float,
    tp_price: float | None,
) -> AccountExecution:
    try:
        adapter = await broker_manager.get_adapter(account)
        if not await adapter.is_connected():
            return AccountExecution(account.id, account.label, ok=False, message="not connected")

        # 1) Все исходные данные тянем отдельно с этого аккаунта.
        balance = await adapter.get_balance()
        spec = await adapter.get_symbol_spec(symbol)
        if order_type == OrderType.LIMIT:
            reference_price = entry_price
        else:
            reference_price = await adapter.get_price(symbol)

        # 2) Лот считаем из индивидуальных данных аккаунта.
        calc = calculate_lot_from_prices(
            balance=balance,
            risk_percent=account.risk_percent,
            entry_price=reference_price,
            sl_price=sl_price,
            spec=spec,
        )

        # 3) Отправляем ордер.
        result = await adapter.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=calc.lot,
            price=reference_price if order_type == OrderType.LIMIT else None,
            sl=sl_price,
            tp=tp_price,
        )
        return AccountExecution(
            account_id=account.id,
            label=account.label,
            ok=result.ok,
            lot=calc.lot,
            balance=round(balance, 2),
            reference_price=reference_price,
            risk_amount=round(calc.risk_amount_effective, 2),
            ticket=result.ticket,
            message=result.message,
        )
    except Exception as exc:  # noqa: BLE001 — на уровне аккаунта изолируем сбой
        return AccountExecution(account.id, account.label, ok=False, message=str(exc))


async def execute_trade(
    db: Session,
    *,
    account_ids: list[int],
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    entry_price: float | None,
    sl_price: float,
    tp_price: float | None,
) -> tuple[TradeGroup, list[dict]]:
    accounts = db.query(Account).filter(Account.id.in_(account_ids), Account.is_active.is_(True)).all()

    results = await asyncio.gather(
        *[
            _execute_on_account(
                acc,
                symbol=symbol,
                side=side,
                order_type=order_type,
                entry_price=entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
            )
            for acc in accounts
        ]
    )

    # Освежаем балансы в БД из живых значений (последовательно, после gather).
    by_id = {acc.id: acc for acc in accounts}
    for r in results:
        if r.balance is not None and r.account_id in by_id:
            by_id[r.account_id].balance = r.balance

    group = TradeGroup(
        symbol=symbol,
        side=side,
        order_type=order_type,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    return group, [asdict(r) for r in results]
