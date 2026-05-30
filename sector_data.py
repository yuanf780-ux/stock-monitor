import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

SECTOR_NAME_MAP: Dict[str, str] = {
    "01": "水泥工業",
    "02": "食品工業",
    "03": "塑膠工業",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "08": "玻璃陶瓷",
    "09": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "14": "建材營造",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "20": "其他",
    "21": "化學工業",
    "22": "生技醫療",
    "23": "油電燃氣",
    "24": "半導體",
    "25": "電腦及週邊設備",
    "26": "光電業",
    "27": "通信網路",
    "28": "其他電子",
    "29": "電子通路",
    "30": "資訊服務",
    "31": "電子工業",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
    "91": "存託憑證",
}

# Global themes mapped to TWSE sector codes (for AI prediction context)
GLOBAL_THEME_MAP = {
    "AI / 人工智慧":     ["24", "36", "25", "30"],
    "電動車 / 儲能":     ["24", "05", "26", "35"],
    "半導體供應鏈":      ["24", "25", "26", "28"],
    "航運 / 物流":       ["15"],
    "金融科技":          ["17", "36", "30"],
    "綠能 / 再生能源":   ["35", "23", "05"],
    "生技醫療":          ["22"],
    "國防 / 軍工":       ["05", "28", "25"],
    "AI Server / CoWoS": ["24", "25", "31", "28"],
    "消費復甦":          ["02", "16", "18", "37"],
}


def fetch_all_stocks() -> Optional[pd.DataFrame]:
    try:
        r = requests.get(TWSE_URL, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        df = pd.DataFrame(data)
        df = df.rename(columns={
            "公司代號": "code",
            "公司名稱": "name",
            "公司簡稱": "short_name",
            "產業別": "sector_code",
        })
        df["code"]        = df["code"].str.strip()
        df["sector_code"] = df["sector_code"].str.strip()
        df["ticker"]      = df["code"] + ".TW"
        df["sector_name"] = df["sector_code"].map(SECTOR_NAME_MAP).fillna("其他")
        return df[["code", "short_name", "name", "ticker", "sector_code", "sector_name"]]
    except Exception as e:
        return None


def get_sector_list(df: pd.DataFrame) -> List[str]:
    codes = df["sector_code"].dropna().unique()
    names = [SECTOR_NAME_MAP.get(c, c) for c in sorted(codes)]
    return sorted(set(names))


def get_stocks_in_sector(df: pd.DataFrame, sector_name: str) -> pd.DataFrame:
    return df[df["sector_name"] == sector_name].copy()


PERIOD_MAP = {
    "當日":    {"calendar_days": 3,   "label": "今日"},
    "當周":    {"calendar_days": 7,   "label": "本週"},
    "這兩週":  {"calendar_days": 14,  "label": "近兩週"},
    "這一個月":{"calendar_days": 35,  "label": "近一個月"},
    "這半年":  {"calendar_days": 195, "label": "近半年"},
}


def _period_start_end(period_key: str,
                      custom_start=None, custom_end=None):
    """回傳 (start_date, end_date, download_start)"""
    end = datetime.today()
    if period_key == "自訂" and custom_start and custom_end:
        import datetime as _dt
        start = datetime.combine(custom_start, datetime.min.time()) \
                if hasattr(custom_start, "year") else datetime.today() - timedelta(days=30)
        end   = datetime.combine(custom_end,   datetime.min.time()) \
                if hasattr(custom_end,   "year") else datetime.today()
    else:
        cfg   = PERIOD_MAP.get(period_key, PERIOD_MAP["當周"])
        start = end - timedelta(days=cfg["calendar_days"])

    # 下載時多抓 5 天緩衝（跳過假日）
    dl_start = start - timedelta(days=5)
    return start, end, dl_start


def fetch_sector_performance(sector_stocks: pd.DataFrame, top_n: int = 10,
                             period_key: str = "當周",
                             custom_start=None, custom_end=None) -> pd.DataFrame:
    """
    Fetch price data for top_n stocks in a sector and calculate returns
    for the given period.
    """
    tickers = sector_stocks["ticker"].head(top_n).tolist()
    if not tickers:
        return pd.DataFrame()

    try:
        start, end, dl_start = _period_start_end(period_key, custom_start, custom_end)
        raw = yf.download(tickers, start=dl_start, end=end,
                          auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()

        if len(tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        close = close.dropna(how="all")
        if close.empty:
            return pd.DataFrame()

        latest = close.iloc[-1]
        # 找距 start 最近的收盤日
        start_ts = pd.Timestamp(start)
        before   = close[close.index <= start_ts]
        base     = before.iloc[-1] if not before.empty else close.iloc[0]

        rows = []
        for t in tickers:
            if t not in close.columns:
                continue
            p  = latest.get(t)
            pb = base.get(t)
            if pd.isna(p):
                continue
            ret = (p / pb - 1) * 100 if pb and not pd.isna(pb) else None
            short = sector_stocks.loc[sector_stocks["ticker"] == t, "short_name"]
            rows.append({
                "ticker": t,
                "name":   short.values[0] if len(short) else t,
                "price":  round(p, 2),
                "ret":    round(ret, 2) if ret is not None else None,
            })

        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def compute_all_sector_perf(df: pd.DataFrame, top_n: int = 5,
                            period_key: str = "當周",
                            custom_start=None, custom_end=None) -> pd.DataFrame:
    """
    Compute return per sector for the given period using top_n representative stocks.
    """
    results = []
    major_sectors = [c for c in SECTOR_NAME_MAP if c != "91"]
    sector_df = df[df["sector_code"].isin(major_sectors)]

    all_tickers = []
    sector_ticker_map: Dict[str, List[str]] = {}
    for code, name in SECTOR_NAME_MAP.items():
        if code == "91":
            continue
        stocks = sector_df[sector_df["sector_code"] == code].head(top_n)
        tickers = stocks["ticker"].tolist()
        if tickers:
            sector_ticker_map[name] = tickers
            all_tickers.extend(tickers)

    if not all_tickers:
        return pd.DataFrame()

    try:
        start, end, dl_start = _period_start_end(period_key, custom_start, custom_end)
        raw = yf.download(list(set(all_tickers)), start=dl_start, end=end,
                          auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()

        if len(all_tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": all_tickers[0]})
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        close = close.dropna(how="all")
        latest   = close.iloc[-1]
        start_ts = pd.Timestamp(start)
        before   = close[close.index <= start_ts]
        base_row = before.iloc[-1] if not before.empty else close.iloc[0]

        for name, tickers in sector_ticker_map.items():
            ret_list = []
            for t in tickers:
                if t not in close.columns:
                    continue
                p  = latest.get(t)
                pb = base_row.get(t)
                if not pd.isna(p) and not pd.isna(pb) and pb:
                    ret_list.append((p / pb - 1) * 100)

            if ret_list:
                results.append({
                    "sector":   name,
                    "ret_1w":   round(sum(ret_list) / len(ret_list), 2),  # 保持欄位名稱向後相容
                    "ret_1m":   None,
                    "n_stocks": len(ret_list),
                })

        result_df = pd.DataFrame(results).sort_values("ret_1w", ascending=False).reset_index(drop=True)
        return result_df
    except Exception:
        return pd.DataFrame()
