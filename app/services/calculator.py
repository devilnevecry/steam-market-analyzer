"""Steam commission and arbitrage math."""

from decimal import Decimal, ROUND_HALF_UP


def _r2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def steam_fee(sell_price: float) -> float:
    """Steam fee given buyer-facing sell price (15% seller-side => ~13.04% buyer-side)."""
    # seller base = sell_price / 1.15, fee = sell_price - base, rounded to cents
    base = Decimal(str(sell_price)) / Decimal("1.15")
    base_r = base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = Decimal(str(sell_price)) - base_r
    return float(fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def net_from_sale(sell_price: float) -> float:
    return _r2(sell_price - steam_fee(sell_price))


def gross_spread(buy_price: float, sell_price: float) -> float:
    return _r2(sell_price - buy_price)


def net_profit(buy_price: float, sell_price: float) -> float:
    return _r2(net_from_sale(sell_price) - buy_price)


def net_margin_pct(buy_price: float, sell_price: float) -> float:
    if buy_price <= 0:
        return 0.0
    return _r2((net_profit(buy_price, sell_price) / buy_price) * 100.0)


def liquidity_score(volume_24h: int | None, buy_depth: int | None = None, sell_depth: int | None = None) -> float:
    vol = volume_24h or 0
    bd = buy_depth or 0
    sd = sell_depth or 0
    # volume component 0-60, depth component 0-40
    vol_score = min(60.0, (vol / 50.0) * 60.0) if vol > 0 else 0.0
    depth = bd + sd
    depth_score = min(40.0, (depth / 200.0) * 40.0)
    return _r2(vol_score + depth_score)


def classify_status(net_margin: float | None, liq: float | None) -> str:
    if net_margin is None:
        return "Ожидание"
    if (liq or 0) < 20:
        return "Низкая ликвидность"
    if net_margin >= 5:
        return "Выгодно"
    if net_margin >= 0:
        return "Нейтрально"
    return "Убыточно"
