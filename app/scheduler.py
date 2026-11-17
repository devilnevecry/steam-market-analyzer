"""Background scheduler for price refresh."""

import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import list_items, add_snapshot, latest_snapshot, add_log
from app.services.steam_client import SteamClient

client: SteamClient | None = None
scheduler = AsyncIOScheduler()


def _is_fresh(snap: dict | None) -> bool:
    if not snap or not snap.get("captured_at"):
        return False
    try:
        captured = datetime.fromisoformat(str(snap["captured_at"]).replace(" ", "T"))
    except ValueError:
        return False
    return datetime.utcnow() - captured < timedelta(minutes=settings.cache_ttl_minutes)


async def _refresh_one(item: dict, force: bool = False) -> None:
    global client
    if client is None:
        return
    item_id = item["id"]
    if not force:
        snap = await latest_snapshot(item_id)
        if _is_fresh(snap):
            return
    appid = item["appid"]
    name = item["market_hash_name"]
    try:
        overview = await client.fetch_price_overview(appid, name)
        order = await client.fetch_order_book(appid, name)
    except Exception as e:
        await add_log("ERROR", f"refresh {name}: {e}")
        return
    lowest_sell = overview.get("lowest_sell")
    highest_buy = order.get("highest_buy")
    volume = overview.get("volume_24h")
    median = overview.get("median_price")
    if lowest_sell is not None and order.get("lowest_sell") is not None:
        if abs(order["lowest_sell"] - lowest_sell) > max(0.5, lowest_sell * 0.1):
            highest_buy = None
        else:
            lowest_sell = order["lowest_sell"]
    try:
        await add_snapshot(item_id, lowest_sell, highest_buy, volume, median, None)
    except Exception as e:
        await add_log("ERROR", f"snapshot {name}: {e}")


async def update_all() -> None:
    try:
        items = await list_items()
    except Exception as e:
        await add_log("ERROR", f"list_items: {e}")
        return
    for it in items:
        try:
            await _refresh_one(it)
        except Exception as e:
            await add_log("ERROR", f"update_all {it.get('market_hash_name')}: {e}")
            continue


def start_scheduler() -> None:
    scheduler.add_job(
        update_all,
        "interval",
        minutes=settings.scheduler_interval_minutes,
        id="update_all",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
