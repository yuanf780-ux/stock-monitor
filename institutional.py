"""
三大法人（外資、投信、自營商）買賣超資料
來源：TWSE Open API
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _trading_days_back(n: int) -> list[str]:
    """Return up to n recent trading-day date strings YYYYMMDD."""
    dates = []
    d = datetime.now()
    while len(dates) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:          # Mon–Fri only
            dates.append(d.strftime("%Y%m%d"))
    return dates


def fetch_day(date_str: str) -> Optional[pd.DataFrame]:
    """Fetch one day of institutional data. Returns None if market closed."""
    try:
        r = requests.get(_URL, params={
            "response": "json",
            "date": date_str,
            "selectType": "ALLBUT0999",
        }, headers=_HEADERS, timeout=12)
        data = r.json()
        if data.get("stat") != "OK":
            return None

        cols = ["code", "name",
                "fi_buy", "fi_sell", "fi_net",        # 外陸資
                "fd_buy", "fd_sell", "fd_net",         # 外資自營商
                "it_buy", "it_sell", "it_net",         # 投信
                "dl_net",
                "dl_buy_own", "dl_sell_own", "dl_net_own",
                "dl_buy_hedge", "dl_sell_hedge", "dl_net_hedge",
                "total_net"]                           # 三大法人合計

        rows = []
        for row in data.get("data", []):
            if len(row) < 19:
                continue
            def to_int(v):
                try:
                    return int(str(v).replace(",", "").replace("−", "-").strip())
                except Exception:
                    return 0
            rows.append({
                "code":      row[0].strip(),
                "name":      row[1].strip(),
                "fi_net":    to_int(row[4]),    # 外資買賣超
                "it_net":    to_int(row[10]),   # 投信買賣超
                "dl_net":    to_int(row[11]),   # 自營商買賣超
                "total_net": to_int(row[18]),   # 三大法人合計
                "date":      date_str,
            })

        df = pd.DataFrame(rows)
        df["ticker"] = df["code"] + ".TW"
        return df
    except Exception:
        return None


def fetch_cumulative(n_days: int = 10) -> pd.DataFrame:
    """
    Aggregate institutional data over n_days.
    Returns DataFrame with cumulative sums and consecutive buying/selling days.
    """
    all_frames = []
    for date_str in _trading_days_back(n_days * 2):   # extra margin for holidays
        df = fetch_day(date_str)
        if df is not None:
            all_frames.append(df)
        if len(all_frames) >= n_days:
            break

    if not all_frames:
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values("date")

    # Aggregate per stock
    agg = combined.groupby(["code", "name", "ticker"]).agg(
        fi_cum  =("fi_net",    "sum"),
        it_cum  =("it_net",    "sum"),
        dl_cum  =("dl_net",    "sum"),
        total_cum=("total_net","sum"),
        n_days  =("date",      "count"),
    ).reset_index()

    # Consecutive buying/selling days (most recent first)
    def _consec(code, col):
        series = (combined[combined["code"] == code]
                  .sort_values("date", ascending=False)[col].values)
        if len(series) == 0:
            return 0
        sign = 1 if series[0] > 0 else (-1 if series[0] < 0 else 0)
        if sign == 0:
            return 0
        count = 0
        for v in series:
            if (sign > 0 and v > 0) or (sign < 0 and v < 0):
                count += 1
            else:
                break
        return count * sign   # positive = consecutive buy days, negative = sell days

    codes = agg["code"].tolist()
    agg["fi_consec"]  = [_consec(c, "fi_net")    for c in codes]
    agg["tot_consec"] = [_consec(c, "total_net") for c in codes]

    return agg.sort_values("fi_cum", ascending=False).reset_index(drop=True)


def get_top_accumulation(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    """Top stocks by cumulative foreign investor buying."""
    if df.empty:
        return df
    d = df[df["fi_cum"] > 0].nlargest(top_n, "fi_cum")
    return d


def get_top_distribution(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    """Top stocks by cumulative foreign investor selling."""
    if df.empty:
        return df
    d = df[df["fi_cum"] < 0].nsmallest(top_n, "fi_cum")
    return d


def get_stock_institutional(code: str, n_days: int = 10) -> pd.DataFrame:
    """Daily institutional flow for a specific stock."""
    frames = []
    for date_str in _trading_days_back(n_days * 2):
        df = fetch_day(date_str)
        if df is not None:
            row = df[df["code"] == code]
            if not row.empty:
                frames.append(row)
        if len(frames) >= n_days:
            break
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_values("date").reset_index(drop=True)
