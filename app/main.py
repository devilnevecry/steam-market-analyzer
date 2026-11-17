"""FastAPI entrypoint."""

import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_db
from app.routers import api, pages
from app.scheduler import start_scheduler, stop_scheduler, update_all
from app.services.steam_client import SteamClient

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.database import seed_if_empty
    await seed_if_empty()
    import httpx
    http_client = httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=True)
    client = SteamClient(http_client)
    app.state.steam_client = client
    app.state.http_client = http_client
    import app.scheduler as sch
    sch.client = client
    start_scheduler()
    asyncio.create_task(update_all())
    yield
    stop_scheduler()
    await client.close()
    await http_client.aclose()


app = FastAPI(title="Steam Market Arbitrage & Liquidity Analyzer", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
