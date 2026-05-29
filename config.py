DEFAULT_TW_STOCKS = [
    {"ticker": "2330.TW", "name": "台積電"},
    {"ticker": "2317.TW", "name": "鴻海"},
    {"ticker": "2454.TW", "name": "聯發科"},
    {"ticker": "2382.TW", "name": "廣達"},
    {"ticker": "2881.TW", "name": "富邦金"},
]

DEFAULT_US_STOCKS = [
    {"ticker": "NVDA", "name": "輝達"},
    {"ticker": "AAPL", "name": "蘋果"},
    {"ticker": "TSLA", "name": "特斯拉"},
    {"ticker": "MSFT", "name": "微軟"},
]

ALERT_DEFAULTS = {
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "price_change_pct": 3.0,
}

INDICATOR_COLORS = {
    "ma5":   "#FFD700",
    "ma20":  "#FF6B35",
    "ma60":  "#00CED1",
    "upper": "#9B59B6",
    "lower": "#9B59B6",
}
