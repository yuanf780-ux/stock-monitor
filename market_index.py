import requests
import yfinance as yf
import pandas as pd
from typing import Optional, Dict

US_INDICES = {
    "^GSPC": {"name": "標準普爾500", "short": "標普 S&P 500", "color": "#3b82f6"},
    "^DJI":  {"name": "道瓊工業指數", "short": "道瓊 DJI",    "color": "#06b6d4"},
    "^IXIC": {"name": "那斯達克指數", "short": "那指 NASDAQ",  "color": "#8b5cf6"},
}

_TAIFEX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Referer":    "https://mis.taifex.com.tw/",
    "Content-Type": "application/json",
}


def fetch_us_index(symbol: str) -> Dict:
    try:
        f = yf.Ticker(symbol).fast_info
        price  = float(f.last_price  or 0)
        prev   = float(f.previous_close or price)
        change = price - prev
        pct    = change / prev * 100 if prev else 0
        meta   = US_INDICES.get(symbol, {})
        return {
            "symbol": symbol,
            "name":   meta.get("name", symbol),
            "short":  meta.get("short", symbol),
            "color":  meta.get("color", "#9ca3af"),
            "price":  price,
            "change": change,
            "pct":    pct,
            "valid":  True,
        }
    except Exception as e:
        return {"symbol": symbol, "valid": False, "error": str(e)}


def fetch_tw_index() -> Dict:
    try:
        f = yf.Ticker("^TWII").fast_info
        price  = float(f.last_price  or 0)
        prev   = float(f.previous_close or price)
        change = price - prev
        pct    = change / prev * 100 if prev else 0
        return {
            "symbol": "^TWII",
            "name":   "台股加權指數",
            "short":  "TAIEX",
            "color":  "#f97316",
            "price":  price,
            "change": change,
            "pct":    pct,
            "valid":  True,
        }
    except Exception as e:
        return {"symbol": "^TWII", "valid": False, "error": str(e)}


def _fetch_taifex_raw(market_type: int) -> list:
    """market_type: 0=日盤, 1=夜盤"""
    try:
        r = requests.post(
            "https://mis.taifex.com.tw/futures/api/getQuoteList",
            json={"MarketType": str(market_type), "SymbolType": "F"},
            headers=_TAIFEX_HEADERS,
            timeout=10,
        )
        if not r.ok:
            return []
        return r.json().get("RtData", {}).get("QuoteList", [])
    except Exception:
        return []


def _parse_taifex_contract(items: list, suffix: str, label: str, color: str) -> Dict:
    contracts = [
        i for i in items
        if str(i.get("SymbolID", "")).endswith(suffix)
        and "TXF" in str(i.get("SymbolID", ""))
        and len(str(i.get("SymbolID", ""))) > 6
    ]
    contracts.sort(key=lambda x: int(x.get("CTotalVolume", 0) or 0), reverse=True)

    if not contracts:
        return {"name": label, "valid": False}

    c   = contracts[0]
    last = float(c.get("CLastPrice") or 0)
    ref  = float(c.get("CRefPrice")  or 0)
    diff = float(c.get("CDiff")      or 0)
    rate = float(c.get("CDiffRate")  or 0)
    vol  = int(c.get("CTotalVolume") or 0)

    # Night session might not have opened
    if last == 0:
        return {"name": label, "valid": False, "reason": "尚未開盤"}

    return {
        "symbol":   c.get("SymbolID", ""),
        "contract": c.get("DispCName", ""),
        "name":     label,
        "color":    color,
        "price":    last,
        "change":   diff,
        "pct":      rate,
        "open":     float(c.get("COpenPrice") or 0),
        "high":     float(c.get("CHighPrice") or 0),
        "low":      float(c.get("CLowPrice")  or 0),
        "volume":   vol,
        "valid":    True,
    }


def fetch_tx_day() -> Dict:
    items = _fetch_taifex_raw(0)
    return _parse_taifex_contract(items, "-F", "台指期（日盤）", "#10b981")


def fetch_tx_night() -> Dict:
    items = _fetch_taifex_raw(1)
    return _parse_taifex_contract(items, "-M", "台指期（夜盤）", "#eab308")


def fetch_intraday(symbol: str, interval: str = "5m") -> Optional[pd.Series]:
    try:
        df = yf.download(symbol, period="1d", interval=interval, progress=False)
        if df.empty:
            return None
        c = df["Close"].dropna()
        if hasattr(c, "squeeze"):
            c = c.squeeze()
        return c if len(c) > 1 else None
    except Exception:
        return None
