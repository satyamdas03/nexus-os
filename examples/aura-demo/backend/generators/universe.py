"""Static reference universe for the 34k synthetic book.

~35 tickers spanning Equity (US / Ex-US / single-country EM), Bonds, Commodity,
Crypto, Cash. Each ticker carries the metadata the rules engine needs
(asset_class, sector, region, liquidity_tier) plus the GBM parameters
(mu, sigma, base_price) consumed by generators/market.py.

liquidity_tier: 1 = high (large ETFs / govt bonds), 2 = medium, 3 = low (crypto,
single-country EM). The min_liquid_pct rule requires a minimum weight in tier-1.

This is the single source of truth for ticker metadata. generate_data copies
`region` and `liquidity_tier` onto each holding row; rules_engine reads them.
core/trades.py is extended in Task 2b to look tickers up here.
"""

# Sector correlation used by the GBM model (generators/market.py).
RHO = 0.5

# fmt: off
UNIVERSE = [
    # --- Equity: US broad + sector ETFs (tier 1) ---
    {"ticker": "SPY",  "name": "S&P 500 ETF",        "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 500.0, "mu": 0.08, "sigma": 0.16},
    {"ticker": "QQQ",  "name": "Nasdaq 100 ETF",     "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 420.0, "mu": 0.10, "sigma": 0.22},
    {"ticker": "VTI",  "name": "Total Mkt ETF",      "asset_class": "Equity",  "sector": "Broad",        "region": "US",    "liquidity_tier": 1, "base_price": 260.0, "mu": 0.08, "sigma": 0.16},
    {"ticker": "XLV",  "name": "Healthcare ETF",     "asset_class": "Equity",  "sector": "Healthcare",   "region": "US",    "liquidity_tier": 1, "base_price": 145.0, "mu": 0.07, "sigma": 0.15},
    {"ticker": "XLF",  "name": "Financials ETF",     "asset_class": "Equity",  "sector": "Financials",   "region": "US",    "liquidity_tier": 1, "base_price": 45.0,  "mu": 0.08, "sigma": 0.18},
    {"ticker": "XLK",  "name": "Tech Sector ETF",    "asset_class": "Equity",  "sector": "Technology",   "region": "US",    "liquidity_tier": 1, "base_price": 220.0, "mu": 0.11, "sigma": 0.22},
    {"ticker": "XLY",  "name": "Consumer Disc ETF",  "asset_class": "Equity",  "sector": "Consumer",     "region": "US",    "liquidity_tier": 1, "base_price": 180.0, "mu": 0.08, "sigma": 0.19},
    {"ticker": "XLP",  "name": "Consumer Staples",   "asset_class": "Equity",  "sector": "Consumer",     "region": "US",    "liquidity_tier": 1, "base_price": 80.0,  "mu": 0.06, "sigma": 0.12},
    {"ticker": "XLE",  "name": "Energy ETF",         "asset_class": "Equity",  "sector": "Energy",       "region": "US",    "liquidity_tier": 2, "base_price": 90.0,  "mu": 0.05, "sigma": 0.28},
    {"ticker": "XLRE", "name": "Real Estate ETF",    "asset_class": "Equity",  "sector": "RealEstate",   "region": "US",    "liquidity_tier": 2, "base_price": 42.0,  "mu": 0.05, "sigma": 0.20},
    # --- Equity: Ex-US developed (tier 1-2) ---
    {"ticker": "VEA",  "name": "Developed Mkts ETF", "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 1, "base_price": 60.0,  "mu": 0.07, "sigma": 0.17},
    {"ticker": "EFA",  "name": "EAFE ETF",           "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 1, "base_price": 80.0,  "mu": 0.07, "sigma": 0.17},
    {"ticker": "EWJ",  "name": "Japan ETF",          "asset_class": "Equity",  "sector": "Broad",        "region": "ExUS",  "liquidity_tier": 2, "base_price": 70.0,  "mu": 0.06, "sigma": 0.18},
    {"ticker": "EWG",  "name": "Germany ETF",        "asset_class": "Equity",  "sector": "Industrials",  "region": "ExUS",  "liquidity_tier": 2, "base_price": 30.0,  "mu": 0.06, "sigma": 0.20},
    # --- Equity: Emerging markets (tier 2-3) ---
    {"ticker": "VWO",  "name": "Emerging Mkts ETF",  "asset_class": "Equity",  "sector": "Broad",        "region": "EM",    "liquidity_tier": 2, "base_price": 45.0,  "mu": 0.07, "sigma": 0.24},
    {"ticker": "EEM",  "name": "EM ETF",             "asset_class": "Equity",  "sector": "Broad",        "region": "EM",    "liquidity_tier": 2, "base_price": 42.0,  "mu": 0.07, "sigma": 0.24},
    {"ticker": "MCHI", "name": "China ETF",          "asset_class": "Equity",  "sector": "Technology",   "region": "EM",    "liquidity_tier": 3, "base_price": 55.0,  "mu": 0.06, "sigma": 0.30},
    {"ticker": "INDA", "name": "India ETF",          "asset_class": "Equity",  "sector": "Financials",   "region": "EM",    "liquidity_tier": 3, "base_price": 50.0,  "mu": 0.08, "sigma": 0.28},
    {"ticker": "EWZ",  "name": "iShares MSCI Brazil ETF", "asset_class": "Equity", "sector": "Broad",   "region": "EM",    "liquidity_tier": 2, "base_price": 28.0,  "mu": 0.10, "sigma": 0.26},
    # --- Bonds (tier 1) ---
    {"ticker": "TLT",  "name": "20+ Yr Treasury",    "asset_class": "Bonds",   "sector": "Govt",         "region": "US",    "liquidity_tier": 1, "base_price": 95.0,  "mu": 0.03, "sigma": 0.12},
    {"ticker": "IEF",  "name": "7-10 Yr Treasury",   "asset_class": "Bonds",   "sector": "Govt",         "region": "US",    "liquidity_tier": 1, "base_price": 95.0,  "mu": 0.03, "sigma": 0.06},
    {"ticker": "LQD",  "name": "Inv-Grade Corp",     "asset_class": "Bonds",   "sector": "Corporate",    "region": "US",    "liquidity_tier": 1, "base_price": 110.0, "mu": 0.04, "sigma": 0.08},
    {"ticker": "HYG",  "name": "High Yield Corp",    "asset_class": "Bonds",   "sector": "Corporate",    "region": "US",    "liquidity_tier": 2, "base_price": 80.0,  "mu": 0.05, "sigma": 0.10},
    {"ticker": "BNDX", "name": "Intl Bond ETF",      "asset_class": "Bonds",   "sector": "Govt",         "region": "ExUS",  "liquidity_tier": 2, "base_price": 50.0,  "mu": 0.02, "sigma": 0.07},
    # --- Commodity (tier 1-2) ---
    {"ticker": "GLD",  "name": "Gold ETF",           "asset_class": "Commodity","sector": "Metals",      "region": "US",    "liquidity_tier": 1, "base_price": 240.0, "mu": 0.04, "sigma": 0.15},
    {"ticker": "SLV",  "name": "Silver ETF",         "asset_class": "Commodity","sector": "Metals",      "region": "US",    "liquidity_tier": 2, "base_price": 26.0,  "mu": 0.04, "sigma": 0.25},
    {"ticker": "DBC",  "name": "Commodity Index",    "asset_class": "Commodity","sector": "Broad",       "region": "US",    "liquidity_tier": 2, "base_price": 25.0,  "mu": 0.03, "sigma": 0.18},
    # --- Crypto (tier 3) ---
    {"ticker": "BTC",  "name": "Bitcoin",            "asset_class": "Crypto",  "sector": "Digital",      "region": "US",    "liquidity_tier": 3, "base_price": 60000.0,"mu": 0.20, "sigma": 0.60},
    {"ticker": "ETH",  "name": "Ethereum",           "asset_class": "Crypto",  "sector": "Digital",      "region": "US",    "liquidity_tier": 3, "base_price": 3000.0, "mu": 0.22, "sigma": 0.70},
    # --- Cash (tier 1) ---
    {"ticker": "CASH", "name": "Money Mkt",          "asset_class": "Cash",    "sector": "Cash",         "region": "US",    "liquidity_tier": 1, "base_price": 1.0,   "mu": 0.04, "sigma": 0.001},
]
# fmt: on

UNIVERSE_BY_TICKER = {u["ticker"]: u for u in UNIVERSE}
ASSET_CLASSES = sorted({u["asset_class"] for u in UNIVERSE})
SECTORS = sorted({u["sector"] for u in UNIVERSE})
REGIONS = sorted({u["region"] for u in UNIVERSE})


def all_tickers() -> list[str]:
    return [u["ticker"] for u in UNIVERSE]


def by_region(region: str) -> list[str]:
    return [u["ticker"] for u in UNIVERSE if u["region"] == region]


def by_asset_class(asset_class: str) -> list[str]:
    return [u["ticker"] for u in UNIVERSE if u["asset_class"] == asset_class]
