"""Async Steam Market client with throttling and parsing."""

import asyncio
import random
import re
from urllib.parse import quote

import httpx

from app.config import settings


def parse_price(text) -> float | None:
    if text is None:
        return None
    s = str(text)
    s = re.sub(r"(?i)(руб|pуб|rub|usd|eur|р\.|p\.|\$|€|£)", "", s)
    s = s.replace("\xa0", "").replace("\u2009", "").replace(" ", "")
    s = re.sub(r"[^\d.,\-]", "", s)
    s = s.strip(".,")
    if not s or s in (".", ","):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(text) -> int | None:
    if text is None:
        return None
    s = re.sub(r"[^\d]", "", str(text))
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


class SteamClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        if client is None:
            proxies = settings.proxy if settings.proxy else None
            client = httpx.AsyncClient(
                timeout=settings.request_timeout,
                proxy=proxies,
                follow_redirects=True,
                headers={"Accept-Language": "ru,en;q=0.9"},
            )
        self._client = client
        self._sem = asyncio.Semaphore(1)
        self._backoff = 0.0

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _ua(self) -> str:
        return random.choice(settings.user_agents)

    async def _throttle(self) -> None:
        delay = random.uniform(settings.rate_limit_min, settings.rate_limit_max)
        if self._backoff > 0:
            delay += self._backoff
        await asyncio.sleep(delay)

    async def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        async with self._sem:
            for attempt in range(5):
                await self._throttle()
                try:
                    resp = await self._client.get(
                        url, params=params, headers={"User-Agent": self._ua()}
                    )
                except httpx.HTTPError:
                    self._backoff = min(self._backoff + settings.backoff_base, 60.0)
                    if attempt < 4:
                        await asyncio.sleep(settings.backoff_base * (attempt + 1))
                        continue
                    raise
                if resp.status_code == 429:
                    self._backoff = min(max(self._backoff * 2, settings.backoff_base), 120.0)
                    await asyncio.sleep(self._backoff)
                    continue
                self._backoff = max(0.0, self._backoff * 0.5)
                if resp.status_code >= 500:
                    if attempt < 4:
                        await asyncio.sleep(settings.backoff_base * (attempt + 1))
                        continue
                resp.raise_for_status()
                return resp
            raise RuntimeError("Steam request failed after retries")

    async def fetch_price_overview(self, appid: int, market_hash_name: str) -> dict:
        url = "https://steamcommunity.com/market/priceoverview/"
        params = {
            "appid": appid,
            "currency": settings.currency,
            "market_hash_name": market_hash_name,
        }
        resp = await self._get(url, params)
        data = resp.json()
        if not data.get("success"):
            return {}
        volume_raw = data.get("volume")
        volume = parse_int(volume_raw) if volume_raw is not None else None
        return {
            "lowest_sell": parse_price(data.get("lowest_price")),
            "volume_24h": volume,
            "median_price": parse_price(data.get("median_price")),
        }

    async def fetch_item_nameid(self, appid: int, market_hash_name: str) -> int | None:
        url = f"https://steamcommunity.com/market/listings/{appid}/{quote(market_hash_name, safe='')}"
        try:
            resp = await self._get(url)
        except Exception:
            return None
        html = resp.text
        patterns = [
            r"Market_LoadOrderSpread\(\s*(\d+)\s*\)",
            r'"item_nameid"\s*:\s*"?(\d+)"?',
            r"nameid\s*=\s*(\d+)",
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    continue
        return None

    async def fetch_order_book(self, appid: int, market_hash_name: str) -> dict:
        url = f"https://steamcommunity.com/market/listings/{appid}/{quote(market_hash_name, safe='')}"
        try:
            resp = await self._get(url)
        except Exception:
            return {}
        txt = resp.text

        def get_int(key: str) -> int | None:
            m = re.search(r'\\"' + key + r'\\":(\d+)', txt)
            if not m:
                return None
            try:
                return int(m.group(1))
            except ValueError:
                return None

        amt_min = get_int("amtMinSellOrder")
        amt_max = get_int("amtMaxBuyOrder")
        lowest_sell = (amt_min / 100.0) if amt_min is not None else None
        highest_buy = (amt_max / 100.0) if amt_max is not None else None

        def parse_compact(key: str) -> list[tuple[float, int]]:
            m = re.search(r'\\"' + key + r'\\":\[(.*?)\]', txt, re.S)
            if not m:
                return []
            nums = re.findall(r"\d+", m.group(1))
            out: list[tuple[float, int]] = []
            i = 0
            while i + 1 < len(nums):
                try:
                    price = int(nums[i]) / 100.0
                    qty = int(nums[i + 1])
                except ValueError:
                    i += 2
                    continue
                out.append((price, qty))
                i += 2
            return out

        buy_orders = parse_compact("rgCompactBuyOrders")
        sell_orders = parse_compact("rgCompactSellOrders")
        return {
            "highest_buy": highest_buy,
            "lowest_sell": lowest_sell,
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
        }

    async def fetch_histogram(self, item_nameid: int) -> dict:
        url = "https://steamcommunity.com/market/itemordershistogram"
        params = {
            "country": "RU",
            "language": "russian",
            "currency": settings.currency,
            "item_nameid": item_nameid,
        }
        try:
            resp = await self._get(url, params)
        except Exception:
            return {}
        data = resp.json()
        if not data.get("success"):
            return {}
        highest_buy = parse_price(data.get("highest_buy_order"))
        lowest_sell = parse_price(data.get("lowest_sell_order"))
        buy_orders: list[tuple[float, int]] = []
        sell_orders: list[tuple[float, int]] = []
        for g in data.get("buy_order_graph") or []:
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                p = parse_price(g[0])
                q = parse_int(g[1])
                if p is not None and q is not None:
                    buy_orders.append((p, q))
        for g in data.get("sell_order_graph") or []:
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                p = parse_price(g[0])
                q = parse_int(g[1])
                if p is not None and q is not None:
                    sell_orders.append((p, q))
        return {
            "highest_buy": highest_buy,
            "lowest_sell": lowest_sell,
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
        }