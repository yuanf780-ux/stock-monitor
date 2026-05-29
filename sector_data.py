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


def fetch_sector_performance(sector_stocks: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Fetch recent price data for top_n stocks in a sector and calculate returns.
    Returns a DataFrame with price info per stock.
    """
    tickers = sector_stocks["ticker"].head(top_n).tolist()
    if not tickers:
        return pd.DataFrame()

    try:
        end   = datetime.today()
        start = end - timedelta(days=40)
        raw   = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

        if raw.empty:
            return pd.DataFrame()

        if len(tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        close = close.dropna(how="all")
        if close.empty:
            return pd.DataFrame()

        latest    = close.iloc[-1]
        w1_ago    = close.iloc[-6]  if len(close) >= 6  else close.iloc[0]
        m1_ago    = close.iloc[-21] if len(close) >= 21 else close.iloc[0]

        rows = []
        for t in tickers:
            if t not in close.columns:
                continue
            p = latest.get(t)
            p1w = w1_ago.get(t)
            p1m = m1_ago.get(t)
            if pd.isna(p):
                continue
            r1w = (p / p1w - 1) * 100 if p1w and not pd.isna(p1w) else None
            r1m = (p / p1m - 1) * 100 if p1m and not pd.isna(p1m) else None
            short = sector_stocks.loc[sector_stocks["ticker"] == t, "short_name"]
            rows.append({
                "ticker":    t,
                "name":      short.values[0] if len(short) else t,
                "price":     round(p, 2),
                "ret_1w":    round(r1w, 2) if r1w is not None else None,
                "ret_1m":    round(r1m, 2) if r1m is not None else None,
            })

        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def compute_all_sector_perf(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """
    Compute 1-week return per sector using top_n representative stocks.
    Used for the sector heatmap / ranking overview.
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
        end   = datetime.today()
        start = end - timedelta(days=35)
        raw   = yf.download(list(set(all_tickers)), start=start, end=end,
                            auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()

        if len(all_tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": all_tickers[0]})
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

        close = close.dropna(how="all")
        latest = close.iloc[-1]
        w1_ago = close.iloc[-6] if len(close) >= 6 else close.iloc[0]
        m1_ago = close.iloc[-21] if len(close) >= 21 else close.iloc[0]

        for name, tickers in sector_ticker_map.items():
            ret1w_list, ret1m_list = [], []
            for t in tickers:
                if t not in close.columns:
                    continue
                p, p1w, p1m = latest.get(t), w1_ago.get(t), m1_ago.get(t)
                if not pd.isna(p) and not pd.isna(p1w) and p1w:
                    ret1w_list.append((p / p1w - 1) * 100)
                if not pd.isna(p) and not pd.isna(p1m) and p1m:
                    ret1m_list.append((p / p1m - 1) * 100)

            if ret1w_list:
                results.append({
                    "sector":   name,
                    "ret_1w":   round(sum(ret1w_list) / len(ret1w_list), 2),
                    "ret_1m":   round(sum(ret1m_list) / len(ret1m_list), 2) if ret1m_list else None,
                    "n_stocks": len(ret1w_list),
                })

        result_df = pd.DataFrame(results).sort_values("ret_1w", ascending=False).reset_index(drop=True)
        return result_df
    except Exception:
        return pd.DataFrame()
