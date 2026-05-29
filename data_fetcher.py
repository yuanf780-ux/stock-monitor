import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def fetch_stock_info(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        fast = stock.fast_info

        price = fast.last_price or 0
        prev_close = fast.previous_close or price
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": fast.three_month_average_volume or 0,
            "market_cap": info.get("marketCap", 0),
            "currency": info.get("currency", "USD"),
            "valid": True,
        }
    except Exception as e:
        return {"ticker": ticker, "valid": False, "error": str(e)}


def fetch_history(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return None


def fetch_batch_info(tickers: list) -> Dict[str, Dict]:
    results = {}
    for t in tickers:
        results[t] = fetch_stock_info(t)
    return results


def fetch_batch_prices(tickers: list) -> Dict[str, Dict]:
    """
    Batch-download 2-day close prices for a list of tickers.
    Returns {ticker: {price, change, pct}} — fast and efficient.
    """
    if not tickers:
        return {}
    try:
        raw = yf.download(tickers, period="2d", interval="1d",
                          auto_adjust=True, progress=False)
        if raw.empty:
            return {}

        if len(tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        result: Dict[str, Dict] = {}
        for t in tickers:
            if t not in close.columns:
                continue
            series = close[t].dropna()
            if series.empty:
                continue
            price = float(series.iloc[-1])
            prev  = float(series.iloc[-2]) if len(series) >= 2 else price
            chg   = price - prev
            pct   = (chg / prev * 100) if prev else 0
            result[t] = {
                "price":  round(price, 2),
                "change": round(chg, 2),
                "pct":    round(pct, 2),
                "valid":  True,
            }
        return result
    except Exception:
        return {}
