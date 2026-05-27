"""Расчёт размера позиции (лота) на основе индивидуального риска аккаунта.

Базовая идея ТЗ:
    Лот = (Баланс * %Риска) / (дистанция SL * стоимость движения цены на лот)

Ключевой момент: «стоимость пункта» — НЕ константа. У разных инструментов
разные свойства, и денежная цена движения цены складывается из них:

    contract_size  — размер контракта (FX: 100000, золото: 100, индекс: 1, ...)
    tick_size      — минимальный шаг цены, на котором задана tick_value
    tick_value     — денежная стоимость движения на один tick_size при 1.0 лоте,
                     в валюте счёта (брокер уже учёл здесь и contract_size, и
                     конвертацию валюты котировки в валюту счёта)

Отсюда универсально (для FX, металлов, индексов, крипты — одинаково):

    value_per_price_unit_per_lot = tick_value / tick_size
        # сколько денег приносит 1.0 лот при движении цены на 1.0 единицы котировки

    risk_money_per_lot = sl_distance_price * value_per_price_unit_per_lot
    lot = risk_amount / risk_money_per_lot

Если брокер не отдаёт tick_value напрямую, его можно вывести как
contract_size * tick_size (верно, когда валюта котировки == валюте счёта;
иначе нужен курс конвертации) — см. SymbolSpec.from_contract().
"""

from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True)
class SymbolSpec:
    """Спецификация инструмента в терминах конкретного брокера.

    Хранит сырые свойства; производные величины (стоимость пункта/движения)
    вычисляются свойствами ниже, чтобы любой тип инструмента считался корректно.
    """

    symbol: str
    digits: int               # знаков после запятой в котировке
    point: float              # минимальный шаг цены терминала (часто == tick_size)
    contract_size: float      # размер контракта (лота): FX 100000, XAUUSD 100, индекс 1...
    tick_size: float          # шаг цены, на котором задана tick_value
    tick_value: float         # ден. стоимость движения на tick_size при 1.0 лоте, в валюте счёта
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    # Размер пункта; если не задан — выводится из point/digits (для FX-стиля котировок).
    pip_size_override: float | None = None

    @property
    def pip_size(self) -> float:
        if self.pip_size_override is not None:
            return self.pip_size_override
        # 5/3-значные котировки: пункт = 10 пойнтов; иначе пункт = пойнт.
        return self.point * (10 if self.digits in (3, 5) else 1)

    @property
    def value_per_price_unit_per_lot(self) -> float:
        """Деньги на 1.0 лот при движении цены на 1.0 единицы котировки."""
        if self.tick_size <= 0:
            raise ValueError(f"{self.symbol}: tick_size must be positive")
        return self.tick_value / self.tick_size

    @property
    def pip_value_per_lot(self) -> float:
        """Стоимость одного пункта на 1.0 лот (для FX-инструментов/отображения)."""
        return self.value_per_price_unit_per_lot * self.pip_size

    @classmethod
    def from_contract(
        cls,
        *,
        symbol: str,
        digits: int,
        point: float,
        contract_size: float,
        tick_size: float | None = None,
        tick_value: float | None = None,
        quote_to_account_rate: float = 1.0,
        volume_min: float = 0.01,
        volume_max: float = 100.0,
        volume_step: float = 0.01,
        pip_size_override: float | None = None,
    ) -> "SymbolSpec":
        """Собрать спецификацию, выводя tick_value из contract_size при отсутствии.

        quote_to_account_rate — курс конвертации валюты котировки в валюту счёта
        (1.0, если валюта котировки совпадает с валютой счёта)."""
        ts = tick_size if tick_size is not None else point
        if tick_value is None:
            tick_value = contract_size * ts * quote_to_account_rate
        return cls(
            symbol=symbol,
            digits=digits,
            point=point,
            contract_size=contract_size,
            tick_size=ts,
            tick_value=tick_value,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_step=volume_step,
            pip_size_override=pip_size_override,
        )


@dataclass(frozen=True)
class LotCalculation:
    lot: float                    # итоговый объём (округлён под шаг и лимиты)
    raw_lot: float                # объём до округления/клампа
    risk_amount: float            # заданный риск в валюте счёта
    sl_distance_price: float      # дистанция SL в единицах цены
    sl_pips: float                # та же дистанция в пунктах
    value_per_price_unit_per_lot: float
    risk_amount_effective: float  # фактический риск после округления лота
    capped: bool                  # True, если упёрлись в min/max объёма брокера


def round_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    # Округляем ВНИЗ под шаг лота, чтобы не превысить заданный риск.
    return floor(value / step + 1e-9) * step


def calculate_lot(
    *,
    balance: float,
    risk_percent: float,
    sl_distance_price: float,
    spec: SymbolSpec,
) -> LotCalculation:
    """Объём, при котором убыток по SL ≈ balance * risk%, для ЛЮБОГО инструмента."""

    if balance <= 0:
        raise ValueError("balance must be positive")
    if risk_percent <= 0:
        raise ValueError("risk_percent must be positive")
    if sl_distance_price <= 0:
        raise ValueError("sl_distance_price must be positive (entry и SL не совпадают)")

    value_per_unit = spec.value_per_price_unit_per_lot
    if value_per_unit <= 0:
        raise ValueError(f"{spec.symbol}: derived value per price unit must be positive")

    risk_amount = balance * (risk_percent / 100.0)
    risk_money_per_lot = sl_distance_price * value_per_unit
    raw_lot = risk_amount / risk_money_per_lot

    if not isfinite(raw_lot):
        raise ValueError("lot calculation produced a non-finite value")

    lot = round_to_step(raw_lot, spec.volume_step)
    capped = False
    if lot < spec.volume_min:
        lot = spec.volume_min
        capped = True
    elif lot > spec.volume_max:
        lot = spec.volume_max
        capped = True

    return LotCalculation(
        lot=round(lot, 2),
        raw_lot=raw_lot,
        risk_amount=risk_amount,
        sl_distance_price=sl_distance_price,
        sl_pips=sl_distance_price / spec.pip_size,
        value_per_price_unit_per_lot=value_per_unit,
        risk_amount_effective=lot * sl_distance_price * value_per_unit,
        capped=capped,
    )


def calculate_lot_from_prices(
    *,
    balance: float,
    risk_percent: float,
    entry_price: float,
    sl_price: float,
    spec: SymbolSpec,
) -> LotCalculation:
    """Дистанцию SL берём из цен входа и стопа (в единицах цены инструмента)."""
    return calculate_lot(
        balance=balance,
        risk_percent=risk_percent,
        sl_distance_price=abs(entry_price - sl_price),
        spec=spec,
    )


def calculate_lot_from_pips(
    *,
    balance: float,
    risk_percent: float,
    sl_pips: float,
    spec: SymbolSpec,
) -> LotCalculation:
    """Дистанция SL задана в пунктах (удобно для FX)."""
    if sl_pips <= 0:
        raise ValueError("sl_pips must be positive")
    return calculate_lot(
        balance=balance,
        risk_percent=risk_percent,
        sl_distance_price=sl_pips * spec.pip_size,
        spec=spec,
    )
