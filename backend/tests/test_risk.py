import math

from app.risk import SymbolSpec, calculate_lot, calculate_lot_from_prices


# EURUSD: pip=0.0001, стоимость пункта на 1 лот ≈ $10.
EURUSD = SymbolSpec(symbol="EURUSD", pip_size=0.0001, pip_value_per_lot=10.0)


def test_basic_formula():
    # $50k * 1% = $500 риска; SL=20 пунктов; пункт=$10/лот.
    # raw = 500 / (20 * 10) = 2.5 лота.
    calc = calculate_lot(balance=50_000, risk_percent=1.0, sl_pips=20, spec=EURUSD)
    assert math.isclose(calc.raw_lot, 2.5, rel_tol=1e-9)
    assert calc.lot == 2.5
    assert math.isclose(calc.risk_amount, 500.0)


def test_rounding_down_to_step():
    # raw = 300 / (20 * 10) = 1.5; при балансе $30k -> 1.5 ровно.
    calc = calculate_lot(balance=30_000, risk_percent=1.0, sl_pips=20, spec=EURUSD)
    assert calc.lot == 1.5
    # Дробный случай округляется ВНИЗ под шаг (не превышаем риск).
    calc2 = calculate_lot(balance=3_000, risk_percent=1.5, sl_pips=17, spec=EURUSD)
    # raw = 45 / 170 = 0.2647 -> 0.26
    assert calc2.lot == 0.26
    assert calc2.lot <= calc2.raw_lot


def test_min_volume_cap():
    calc = calculate_lot(balance=200, risk_percent=1.0, sl_pips=50, spec=EURUSD)
    # raw = 2 / 500 = 0.004 -> ниже минимума, поднимаем до 0.01 и помечаем capped.
    assert calc.lot == 0.01
    assert calc.capped is True


def test_from_prices():
    calc = calculate_lot_from_prices(
        balance=10_000, risk_percent=2.0, entry_price=1.1000, sl_price=1.0950, spec=EURUSD
    )
    # дистанция = 50 пунктов; риск = $200; raw = 200 / (50*10) = 0.4
    assert math.isclose(calc.sl_pips, 50.0, rel_tol=1e-9)
    assert calc.lot == 0.4
