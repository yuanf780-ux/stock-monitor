import yfinance as yf
import requests
import pandas as pd
import time
from typing import Optional, Dict, Any

# ── 台股名稱快查表（避免 yfinance .info 失敗時沒有名稱）──────────────
_TW_NAMES: Dict[str, str] = {}  # 延遲載入

def _get_tw_names() -> Dict[str, str]:
    global _TW_NAMES
    if _TW_NAMES:
        return _TW_NAMES
    try:
        r = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8
        )
        for d in r.json():
            code = d.get("公司代號", "").strip()
            name = d.get("公司簡稱", d.get("公司名稱", "")).strip()
            if code and name:
                _TW_NAMES[code] = name
                _TW_NAMES[code + ".TW"] = name
    except Exception:
        pass
    return _TW_NAMES


def _fetch_tw_realtime(code: str) -> Optional[Dict[str, Any]]:
    """TWSE 即時行情 API（不受 Yahoo Finance 限速影響）"""
    try:
        url = (f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
               f"?ex_ch=tse_{code}.tw&_={int(time.time()*1000)}")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        data = r.json().get("msgArray", [])
        if not data:
            # 試 OTC（上櫃）
            url2 = (f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
                    f"?ex_ch=otc_{code}.tw&_={int(time.time()*1000)}")
            r2 = requests.get(url2, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            data = r2.json().get("msgArray", [])
        if not data:
            return None
        d = data[0]
        price = float(d.get("z", 0) or d.get("y", 0) or 0)
        prev  = float(d.get("y", price) or price)
        if price == 0:
            return None
        change = price - prev
        pct    = (change / prev * 100) if prev else 0
        names  = _get_tw_names()
        name   = d.get("n", "") or names.get(code, code)
        return {
            "ticker":     code + ".TW",
            "name":       name,
            "price":      round(price, 2),
            "change":     round(change, 2),
            "change_pct": round(pct, 2),
            "volume":     int(d.get("v", 0) or 0),
            "currency":   "TWD",
            "valid":      True,
            "source":     "twse",
        }
    except Exception:
        return None


def fetch_stock_info(ticker: str) -> Dict[str, Any]:
    is_tw = ticker.endswith(".TW") or ticker.endswith(".TWO")

    # 台股優先用 TWSE API（更穩定）
    if is_tw:
        code = ticker.replace(".TW", "").replace(".TWO", "")
        result = _fetch_tw_realtime(code)
        if result:
            return result

    # yfinance（美股 + 台股備援）
    for attempt in range(2):
        try:
            stock = yf.Ticker(ticker)
            fast  = stock.fast_info
            price = float(fast.last_price or 0)
            prev  = float(fast.previous_close or price)
            if price == 0:
                raise ValueError("price is 0")
            change = price - prev
            pct    = (change / prev * 100) if prev else 0

            # 名稱：優先用 fast_info，省去慢速 .info 呼叫
            name = ticker
            try:
                name = (stock.fast_info.get("shortName", "")
                        or stock.info.get("shortName", "")
                        or stock.info.get("longName", "")
                        or ticker)
            except Exception:
                if is_tw:
                    names = _get_tw_names()
                    name  = names.get(ticker, ticker)

            return {
                "ticker":     ticker,
                "name":       name,
                "price":      round(price, 2),
                "change":     round(change, 2),
                "change_pct": round(pct, 2),
                "volume":     int(fast.three_month_average_volume or 0),
                "currency":   "TWD" if is_tw else "USD",
                "valid":      True,
                "source":     "yfinance",
            }
        except Exception:
            if attempt == 0:
                time.sleep(1)
            continue

    return {"ticker": ticker, "valid": False, "error": "無法取得資料"}


def fetch_history(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    for attempt in range(2):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            if df.empty:
                if attempt == 0:
                    time.sleep(1); continue
                return None
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df
        except Exception:
            if attempt == 0:
                time.sleep(1)
            continue
    return None


def fetch_batch_prices(tickers: list) -> Dict[str, Dict]:
    """批次抓取收盤價。台股先用 TWSE API，其餘用 yfinance。"""
    if not tickers:
        return {}

    result: Dict[str, Dict] = {}

    # 台股：TWSE API
    tw_tickers = [t for t in tickers if t.endswith(".TW") or t.endswith(".TWO")]
    us_tickers = [t for t in tickers if t not in tw_tickers]

    for t in tw_tickers:
        code = t.replace(".TW", "").replace(".TWO", "")
        r = _fetch_tw_realtime(code)
        if r:
            result[t] = {"price": r["price"], "change": r["change"], "pct": r["change_pct"], "valid": True}

    # 美股：yfinance batch
    if us_tickers:
        try:
            raw = yf.download(us_tickers, period="2d", interval="1d",
                              auto_adjust=True, progress=False)
            if not raw.empty:
                if len(us_tickers) == 1:
                    close = raw[["Close"]].rename(columns={"Close": us_tickers[0]})
                else:
                    close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

                for t in us_tickers:
                    if t not in close.columns:
                        continue
                    series = close[t].dropna()
                    if series.empty:
                        continue
                    price = float(series.iloc[-1])
                    prev  = float(series.iloc[-2]) if len(series) >= 2 else price
                    chg   = price - prev
                    pct   = (chg / prev * 100) if prev else 0
                    result[t] = {"price": round(price, 2), "change": round(chg, 2),
                                 "pct": round(pct, 2), "valid": True}
        except Exception:
            pass

    # 抓不到的補上 yfinance 單筆
    missing = [t for t in tickers if t not in result]
    for t in missing:
        r = fetch_stock_info(t)
        if r.get("valid"):
            result[t] = {"price": r["price"], "change": r["change"],
                         "pct": r["change_pct"], "valid": True}

    return result
