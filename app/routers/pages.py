"""HTML pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

FAVICON_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='#131B2E'/><path d='M6 22 L12 16 L17 19 L26 10' stroke='#10B981' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/><circle cx='26' cy='10' r='2' fill='#10B981'/></svg>"""


@router.get("/favicon.ico")
async def favicon():
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@router.get("/items/{item_id}", response_class=HTMLResponse)
async def item_detail(request: Request, item_id: int):
    return templates.TemplateResponse(request, "item_detail.html", {"item_id": item_id})


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    return templates.TemplateResponse(request, "portfolio.html", {})
