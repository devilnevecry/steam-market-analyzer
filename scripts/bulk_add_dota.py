import asyncio
import httpx
import string

from app.database import init_db, add_item


async def fetch_page(client: httpx.AsyncClient, query: str, start: int) -> list[dict]:
    for attempt in range(5):
        try:
            r = await client.get(
                "https://steamcommunity.com/market/search/render/",
                params={
                    "query": query,
                    "start": start,
                    "count": 100,
                    "search_descriptions": 0,
                    "sort_column": "popular",
                    "sort_dir": "desc",
                    "appid": 570,
                    "norender": 1,
                },
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
        except httpx.HTTPError:
            await asyncio.sleep(5)
            continue
        if r.status_code == 429:
            await asyncio.sleep(15 * (attempt + 1))
            continue
        if r.status_code != 200:
            await asyncio.sleep(5)
            continue
        try:
            data = r.json()
        except Exception:
            await asyncio.sleep(5)
            continue
        return data.get("results", []) or []
    return []


async def fetch_names(limit: int = 500) -> list[str]:
    names: set[str] = set()
    queries = [""] + list(string.ascii_lowercase)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for q in queries:
            start = 0
            while len(names) < limit:
                results = await fetch_page(c, q, start)
                if not results:
                    break
                for res in results:
                    hn = res.get("hash_name")
                    if hn:
                        names.add(hn)
                start += len(results)
                await asyncio.sleep(3)
                if len(results) < 100:
                    break
            if len(names) >= limit:
                break
    return list(names)[:limit]


async def main() -> None:
    await init_db()
    names = await fetch_names(500)
    for n in names:
        await add_item(570, n)
    print(f"Added {len(names)} Dota 2 items")


if __name__ == "__main__":
    asyncio.run(main())
