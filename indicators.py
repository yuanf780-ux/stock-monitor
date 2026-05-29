import pandas as pd
import numpy as np


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for n in [5, 20, 60]:
        df[f"ma{n}"] = df["Close"].rolling(window=n).mean().round(2)
    df["ema12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["ema26"] = df["Close"].ewm(span=26, adjust=False).mean()
    return df


def add_bollinger_bands(df: pd.DataFrame, window: int = 20, std: float = 2.0) -> pd.DataFrame:
    df = df.copy()
    mid = df["Close"].rolling(window=window).mean()
    sigma = df["Close"].rolling(window=window).std()
    df["bb_upper"] = (mid + std * sigma).round(2)
    df["bb_mid"]   = mid.round(2)
    df["bb_lower"] = (mid - std * sigma).round(2)
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = (100 - 100 / (1 + rs)).round(2)
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = (ema12 - ema26).round(4)
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean().round(4)
    df["macd_hist"]   = (df["macd"] - df["macd_signal"]).round(4)
    return df


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    df = add_moving_averages(df)
    df = add_bollinger_bands(df)
    df = add_rsi(df)
    df = add_macd(df)
    return df


def get_signals(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    signals = []

    rsi = last.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            signals.append(f"RSI={rsi:.1f} 超買區間")
        elif rsi <= 30:
            signals.append(f"RSI={rsi:.1f} 超賣區間")

    macd = last.get("macd")
    sig  = last.get("macd_signal")
    prev_macd = prev.get("macd")
    prev_sig  = prev.get("macd_signal")
    if all(v is not None for v in [macd, sig, prev_macd, prev_sig]):
        if prev_macd < prev_sig and macd > sig:
            signals.append("MACD 黃金交叉 (多方信號)")
        elif prev_macd > prev_sig and macd < sig:
            signals.append("MACD 死亡交叉 (空方信號)")

    ma5  = last.get("ma5")
    ma20 = last.get("ma20")
    prev_ma5  = prev.get("ma5")
    prev_ma20 = prev.get("ma20")
    if all(v is not None for v in [ma5, ma20, prev_ma5, prev_ma20]):
        if prev_ma5 < prev_ma20 and ma5 > ma20:
            signals.append("MA5 上穿 MA20 黃金交叉")
        elif prev_ma5 > prev_ma20 and ma5 < ma20:
            signals.append("MA5 下穿 MA20 死亡交叉")

    return {
        "rsi":     round(rsi, 1) if rsi is not None else None,
        "macd":    round(macd, 4) if macd is not None else None,
        "signals": signals,
    }
