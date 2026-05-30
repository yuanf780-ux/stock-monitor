import yfinance as yf
import requests
import pandas as pd
import time
from typing import Optional, Dict, Any, Tuple

# ── 常見美股中文名稱對照 ──────────────────────────────────────────────
_US_CN_MAP: Dict[str, str] = {
    # AI / 半導體
    "輝達": "NVDA", "英偉達": "NVDA", "nvidia": "NVDA",
    "超微": "AMD",  "amd": "AMD",
    "英特爾": "INTC", "intel": "INTC",
    "博通": "AVGO", "broadcom": "AVGO",
    "高通": "QCOM", "qualcomm": "QCOM",
    "邁威爾": "MRVL", "marvell": "MRVL",
    "艾司摩爾": "ASML", "asml": "ASML",
    "應用材料": "AMAT", "amat": "AMAT",
    "科磊": "LRCX", "lam": "LRCX",
    "科磊檢測": "KLAC", "klac": "KLAC",
    "超微電腦": "SMCI", "smci": "SMCI",
    "美光": "MU", "micron": "MU",
    "威騰": "WDC", "wdc": "WDC",
    # 大型科技
    "蘋果": "AAPL", "apple": "AAPL",
    "微軟": "MSFT", "microsoft": "MSFT",
    "谷歌": "GOOGL", "字母": "GOOGL", "google": "GOOGL", "alphabet": "GOOGL",
    "亞馬遜": "AMZN", "amazon": "AMZN",
    "臉書": "META", "meta": "META", "facebook": "META",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "台積電adr": "TSM", "台積adr": "TSM", "tsm": "TSM",
    # 伺服器 / 雲端
    "戴爾": "DELL", "dell": "DELL",
    "惠普企業": "HPE", "hpe": "HPE",
    "維美德": "VRT", "vertiv": "VRT",
    # 網路
    "思科": "CSCO", "cisco": "CSCO",
    "arista": "ANET", "阿里斯塔": "ANET",
    # 航運
    "以星": "ZIM", "zim": "ZIM",
    # 生技
    "禮來": "LLY", "lilly": "LLY",
    "諾和諾德": "NVO", "novo": "NVO",
    "直覺外科": "ISRG", "isrg": "ISRG",
    # 金融
    "摩根大通": "JPM", "jpmorgan": "JPM",
    "美國銀行": "BAC", "bofa": "BAC",
    "高盛": "GS", "goldman": "GS",
}

# ── 台股名稱快查表 ────────────────────────────────────────────────────
_TW_NAMES:    Dict[str, str] = {}   # code / code.TW → name
_TW_NAME2CODE: Dict[str, str] = {}  # name → code.TW

def _get_tw_names() -> Dict[str, str]:
    global _TW_NAMES, _TW_NAME2CODE
    if _TW_NAMES:
        return _TW_NAMES
    try:
        r = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8
        )
        for d in r.json():
            code  = d.get("公司代號", "").strip()
            short = d.get("公司簡稱", "").strip()
            full  = d.get("公司名稱", "").strip()
            if code:
                name = short or full
                _TW_NAMES[code]       = name
                _TW_NAMES[code+".TW"] = name
                # 名稱反查
                if short:
                    _TW_NAME2CODE[short] = code + ".TW"
                if full:
                    _TW_NAME2CODE[full]  = code + ".TW"
                    # 去掉「股份有限公司」等後綴
                    clean = (full.replace("股份有限公司","").replace("有限公司","")
                             .replace("股份","").strip())
                    if clean and clean != full:
                        _TW_NAME2CODE[clean] = code + ".TW"
    except Exception:
        pass
    return _TW_NAMES


def get_all_stock_options() -> list:
    """
    回傳所有可搜尋股票的選項列表，供 selectbox 使用。
    格式：["台積電 2330.TW", "鴻海 2317.TW", "輝達 NVDA", ...]
    """
    _get_tw_names()   # 確保已載入
    options = []

    # 台股（從 TWSE 資料）
    seen = set()
    for code, name in sorted(_TW_NAMES.items()):
        if code.endswith(".TW") and code not in seen:
            seen.add(code)
            options.append(f"{name} ({code})")

    # 常見美股：優先用中文名稱
    us_added   = set()
    sym_to_cn  = {}   # sym → best Chinese name
    for cn_name, sym in _US_CN_MAP.items():
        # 只取中文名稱（非純 ASCII）
        if not cn_name.isascii() and sym not in sym_to_cn:
            sym_to_cn[sym] = cn_name
    for sym, cn_name in sym_to_cn.items():
        options.append(f"{cn_name} ({sym})")
        us_added.add(sym)
    # 補上沒有中文名稱的美股（用純英文代碼）
    for sym in ["NVDA","AAPL","TSLA","MSFT","GOOGL","AMZN","META","AMD",
                "INTC","AVGO","QCOM","MU","SMCI","DELL","TSM","ASML",
                "AMAT","LRCX","KLAC","WDC","LLY","NVO","ISRG","JPM",
                "HPE","VRT","ANET","CSCO","GS","JPM","BAC","RIVN"]:
        if sym not in us_added:
            options.append(f"{sym} ({sym})")
            us_added.add(sym)

    return options


def option_to_ticker(option: str) -> Tuple[str, str]:
    """
    從選項字串取出 ticker 和名稱。
    支援格式：'台積電  2330.TW' 或 '輝達 (NVDA)' 或 '台泥  1101.TW'
    """
    s = option.strip()
    # 格式：'名稱 (代碼)'
    if "(" in s and s.endswith(")"):
        ticker = s.split("(")[-1].rstrip(")")
        name   = s.split("(")[0].strip()
        return ticker, name
    # 格式：'名稱  代碼'（雙空格）
    parts = s.split()
    if len(parts) >= 2:
        ticker = parts[-1]
        name   = " ".join(parts[:-1])
        return ticker, name
    return s.upper(), s


def name_to_ticker(query: str) -> Tuple[str, str]:
    """
    把中文名稱或代碼轉換成 ticker。
    回傳 (ticker, display_name) 。
    若找不到對應名稱，原樣回傳 query 作為 ticker。
    """
    q = query.strip()
    q_lower = q.lower().replace(" ", "")

    # 1. 純數字 → 台股代碼
    if q.isdigit():
        return q + ".TW", q

    # 2. 已是合法代碼格式
    if "." in q or q.upper() in ("NVDA","AAPL","TSLA","MSFT","GOOGL","AMZN",
                                   "META","AMD","INTC","AVGO","QCOM","MU",
                                   "SMCI","DELL","TSM","ASML","AMAT","LRCX"):
        return q.upper(), q.upper()

    # 3. 美股中文名稱對照
    us = _US_CN_MAP.get(q_lower) or _US_CN_MAP.get(q)
    if us:
        return us, us

    # 4. 台股中文名稱查詢（用 TWSE 資料）
    _get_tw_names()
    tw = _TW_NAME2CODE.get(q)
    if tw:
        return tw, _TW_NAMES.get(tw, q)

    # 5. 模糊比對：找包含 query 的第一個台股名稱
    for name, code in _TW_NAME2CODE.items():
        if q in name or name in q:
            return code, name

    # 6. 找不到，原樣回傳
    return q.upper(), q


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


# ── K 線粒度設定（供 page_detail 使用）────────────────────────────────
KLINE_PRESETS: dict = {
    "1分K":    {"interval": "1m",   "days": 1,    "label": "1分K（近1天）"},
    "5分K":    {"interval": "5m",   "days": 5,    "label": "5分K（近5天）"},
    "30分K":   {"interval": "30m",  "days": 30,   "label": "30分K（近30天）"},
    "1小時K":  {"interval": "60m",  "days": 60,   "label": "1小時K（近60天）"},
    "5日":     {"interval": "1d",   "days": 5,    "label": "日K（近5日）"},
    "20日":    {"interval": "1d",   "days": 20,   "label": "日K（近20日）"},
    "1週":     {"interval": "1d",   "days": 7,    "label": "日K（近1週）"},
    "2週":     {"interval": "1d",   "days": 14,   "label": "日K（近2週）"},
    "3週":     {"interval": "1d",   "days": 21,   "label": "日K（近3週）"},
    "4週":     {"interval": "1d",   "days": 28,   "label": "日K（近4週）"},
    "1個月":   {"interval": "1d",   "period": "1mo",  "label": "日K（近1個月）"},
    "3個月":   {"interval": "1d",   "period": "3mo",  "label": "日K（近3個月）"},
    "6個月":   {"interval": "1d",   "period": "6mo",  "label": "日K（近6個月）"},
    "1年":     {"interval": "1d",   "period": "1y",   "label": "日K（近1年）"},
    "自訂":    {"interval": "1d",   "period": "custom","label": "自訂區間"},
}


def fetch_kline(ticker: str, preset_key: str,
                custom_start=None, custom_end=None) -> Optional[pd.DataFrame]:
    """
    根據 KLINE_PRESETS 的設定抓取 K 線資料。
    """
    from datetime import datetime, timedelta
    preset = KLINE_PRESETS.get(preset_key, KLINE_PRESETS["6個月"])
    interval = preset["interval"]

    try:
        stock = yf.Ticker(ticker)

        if preset.get("period") == "custom" and custom_start and custom_end:
            df = stock.history(start=str(custom_start), end=str(custom_end),
                               interval=interval)
        elif "days" in preset:
            end   = datetime.today()
            start = end - timedelta(days=preset["days"])
            df = stock.history(start=start.strftime("%Y-%m-%d"),
                               end=end.strftime("%Y-%m-%d"),
                               interval=interval)
        else:
            df = stock.history(period=preset["period"], interval=interval)

        if df.empty:
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return None
