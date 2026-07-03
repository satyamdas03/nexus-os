from pydantic import BaseModel


class Holding(BaseModel):
    ticker: str
    name: str
    asset_class: str
    sector: str
    units: float
    price: float
    market_value: float


class Portfolio(BaseModel):
    client_id: str
    client_name: str
    adviser: str
    fum: float
    holdings: list[Holding]
    cash: float