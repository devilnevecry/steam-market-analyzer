"""Pydantic v2 schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    appid: Optional[int] = None
    market_hash_name: Optional[str] = None
    url: Optional[str] = None
    input: Optional[str] = None


class ItemOut(BaseModel):
    id: int
    appid: int
    market_hash_name: str
    item_nameid: Optional[int] = None
    enabled: bool = True
    created_at: Optional[str] = None


class PriceSnapshotOut(BaseModel):
    id: int
    item_id: int
    lowest_sell: Optional[float] = None
    highest_buy: Optional[float] = None
    volume_24h: Optional[int] = None
    median_price: Optional[float] = None
    captured_at: Optional[str] = None


class ItemDetail(BaseModel):
    item: ItemOut
    snapshot: Optional[PriceSnapshotOut] = None
    spread_abs: Optional[float] = None
    spread_pct: Optional[float] = None
    net_profit: Optional[float] = None
    liquidity_score: Optional[float] = None
    status: str = "Ожидание"


class PortfolioCreate(BaseModel):
    item_id: int
    buy_price: float = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    note: Optional[str] = None


class PortfolioOut(BaseModel):
    id: int
    item_id: int
    buy_price: float
    quantity: int
    note: Optional[str] = None
    bought_at: Optional[str] = None
    appid: Optional[int] = None
    market_hash_name: Optional[str] = None


class OrderLevel(BaseModel):
    price: float
    quantity: int


class HistogramOut(BaseModel):
    item_nameid: int
    highest_buy: Optional[float] = None
    lowest_sell: Optional[float] = None
    buy_orders: list[OrderLevel] = []
    sell_orders: list[OrderLevel] = []


class CalcRequest(BaseModel):
    buy_price: float
    sell_price: float


class CalcResult(BaseModel):
    gross_spread: float
    steam_fee: float
    net_profit: float
    net_margin_pct: float
    buyer_receives: float
