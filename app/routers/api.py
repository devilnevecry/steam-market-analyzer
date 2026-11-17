"""REST API."""

import re
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, HTTPException

from app import database as db
from app.scheduler import _refresh_one
from app.schemas import (
    CalcRequest,
    CalcResult,
    ItemCreate,
    ItemDetail,
    ItemOut,
    PortfolioCreate,
    PortfolioOut,
)
from app.services.calculator import (
    liquidity_score,
    net_margin_pct,
    net_profit,
    classify_status,
    steam_fee,
    net_from_sale,
)
from app.services.steam_client import SteamClient

router = APIRouter()


def _parse_steam_input(data: ItemCreate) -> tuple[int, str]:
    url = data.url or data.input
    appid = data.appid
    name = data.market_hash_name
    if url and (appid is None or not name):
        parsed = _parse_url(url)
        if parsed:
            appid, name = parsed
    if url and (appid is None or not name) and not url.startswith("http"):
        # maybe "730|name"
        pass
    if appid is None or not name:
        # try parse from input string if contains steam link
        if data.input and "steamcommunity.com/market/listings" in data.input:
            parsed = _parse_url(data.input)
            if parsed:
                appid, name = parsed
    if appid is None or not name:
        raise HTTPException(status_code=400, detail="Need appid and market_hash_name or url")
    return int(appid), str(name)


def _parse_url(url: str) -> tuple[int, str] | None:
    try:
        p = urlparse(url.strip())
        # path: /market/listings/{appid}/{name}
        m = re.search(r"/market/listings/(\d+)/(.+)", p.path)
        if not m:
            return None
        appid = int(m.group(1))
        name = unquote(m.group(2))
        return appid, name
    except Exception:
        return None


async def _item_detail(item: dict) -> dict:
    snap = await db.latest_snapshot(item["id"])
    lowest_sell = snap["lowest_sell"] if snap else None
    highest_buy = snap["highest_buy"] if snap else None
    volume = snap["volume_24h"] if snap else None
    spread_abs = None
    spread_pct = None
    net = None
    if lowest_sell is not None and highest_buy is not None:
        spread_abs = round(lowest_sell - highest_buy, 2)
        net = net_profit(highest_buy, lowest_sell)
        spread_pct = net_margin_pct(highest_buy, lowest_sell)
    liq = liquidity_score(volume)
    status = classify_status(spread_pct, liq)
    return {
        "item": ItemOut(
            id=item["id"],
            appid=item["appid"],
            market_hash_name=item["market_hash_name"],
            item_nameid=item.get("item_nameid"),
            enabled=bool(item.get("enabled", 1)),
            created_at=item.get("created_at"),
        ).model_dump(),
        "snapshot": {
            "id": snap["id"],
            "item_id": snap["item_id"],
            "lowest_sell": snap["lowest_sell"],
            "highest_buy": snap["highest_buy"],
            "volume_24h": snap["volume_24h"],
            "median_price": snap["median_price"],
            "captured_at": snap["captured_at"],
        } if snap else None,
        "spread_abs": spread_abs,
        "spread_pct": spread_pct,
        "net_profit": net,
        "liquidity_score": liq,
        "status": status,
    }


@router.get("/items")
async def list_items():
    items = await db.list_items()
    out = []
    for it in items:
        out.append(await _item_detail(it))
    return out


@router.post("/items")
async def create_item(data: ItemCreate):
    appid, name = _parse_steam_input(data)
    item_id = await db.add_item(appid, name)
    item = await db.get_item(item_id)
    # refresh
    try:
        await _refresh_one(item)
    except Exception:
        pass
    return await _item_detail(item)


@router.get("/items/{item_id}")
async def get_item(item_id: int):
    item = await db.get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return await _item_detail(item)


@router.delete("/items/{item_id}")
async def delete_item(item_id: int):
    await db.delete_item(item_id)
    return {"ok": True}


@router.post("/items/{item_id}/refresh")
async def refresh_item(item_id: int, force: bool = False):
    item = await db.get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    await _refresh_one(item, force=force)
    return await _item_detail(item)


@router.get("/items/{item_id}/history")
async def item_history(item_id: int, limit: int = 200):
    rows = await db.snapshot_history(item_id, limit)
    return rows


@router.get("/items/{item_id}/histogram")
async def item_histogram(item_id: int):
    item = await db.get_item(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    import app.scheduler as sch
    if sch.client is None:
        from app.services.steam_client import SteamClient
        sch.client = SteamClient()
    hist = await sch.client.fetch_order_book(item["appid"], item["market_hash_name"])
    snap = await db.latest_snapshot(item_id)
    snap_lowest = snap["lowest_sell"] if snap else None
    if snap_lowest is not None and hist.get("lowest_sell") is not None:
        if abs(hist["lowest_sell"] - snap_lowest) > max(0.5, snap_lowest * 0.1):
            hist = {"highest_buy": None, "lowest_sell": snap_lowest, "buy_orders": [], "sell_orders": []}
    return {
        "item_nameid": item.get("item_nameid"),
        "highest_buy": hist.get("highest_buy"),
        "lowest_sell": hist.get("lowest_sell"),
        "buy_orders": [{"price": p, "quantity": q} for p, q in hist.get("buy_orders", [])[:5]],
        "sell_orders": [{"price": p, "quantity": q} for p, q in hist.get("sell_orders", [])[:5]],
    }


@router.post("/calc")
async def calc(req: CalcRequest):
    fee = steam_fee(req.sell_price)
    net_sale = net_from_sale(req.sell_price)
    profit = net_profit(req.buy_price, req.sell_price)
    margin = net_margin_pct(req.buy_price, req.sell_price)
    return CalcResult(
        gross_spread=round(req.sell_price - req.buy_price, 2),
        steam_fee=fee,
        net_profit=profit,
        net_margin_pct=margin,
        buyer_receives=net_sale,
    ).model_dump()


# Portfolio
@router.get("/portfolio")
async def portfolio_list():
    entries = await db.list_portfolio()
    out = []
    for e in entries:
        item = await db.get_item(e["item_id"])
        snap = await db.latest_snapshot(e["item_id"]) if item else None
        lowest_sell = snap["lowest_sell"] if snap else None
        current_value = None
        profit = None
        if lowest_sell is not None:
            current_value = round(lowest_sell * e["quantity"], 2)
            profit = round((net_from_sale(lowest_sell) - e["buy_price"]) * e["quantity"], 2)
        out.append({
            "id": e["id"],
            "item_id": e["item_id"],
            "buy_price": e["buy_price"],
            "quantity": e["quantity"],
            "note": e["note"],
            "bought_at": e["bought_at"],
            "appid": e.get("appid"),
            "market_hash_name": e.get("market_hash_name"),
            "lowest_sell": lowest_sell,
            "current_value": current_value,
            "unrealized_profit": profit,
        })
    return out


@router.post("/portfolio")
async def portfolio_add(data: PortfolioCreate):
    eid = await db.add_portfolio(data.item_id, data.buy_price, data.quantity, data.note)
    entries = await db.list_portfolio()
    for e in entries:
        if e["id"] == eid:
            return e
    return {"id": eid}


@router.delete("/portfolio/{entry_id}")
async def portfolio_delete(entry_id: int):
    await db.delete_portfolio(entry_id)
    return {"ok": True}
