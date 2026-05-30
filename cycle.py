"""
景氣循環偵測模組
用市場指標推算目前處於哪個循環階段，並給出對應的族群輪動建議
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any

# ── 景氣循環四階段定義 ─────────────────────────────────────────────
CYCLE_PHASES = {
    "復甦期": {
        "emoji":   "🌱",
        "color":   "#22c55e",
        "desc":    "經濟谷底翻升，信心回溫，風險偏好回升",
        "tw_buy":  ["半導體", "記憶體", "電子零組件", "AI 伺服器"],
        "tw_avoid":["食品", "電信", "公用事業"],
        "us_buy":  ["NVDA", "AMD", "MU", "AVGO", "TSM"],
        "us_avoid":["MCD", "KO", "VZ", "NEE"],
    },
    "擴張期": {
        "emoji":   "🚀",
        "color":   "#3b82f6",
        "desc":    "景氣持續成長，企業獲利加速，風險資產全面走多",
        "tw_buy":  ["電機機械", "航運業", "鋼鐵工業", "金融保險", "半導體"],
        "tw_avoid":["食品工業", "公用事業"],
        "us_buy":  ["NVDA", "AAPL", "MSFT", "META", "AMZN", "GS"],
        "us_avoid":["GLD", "TLT"],
    },
    "高峰期": {
        "emoji":   "⚠️",
        "color":   "#f59e0b",
        "desc":    "景氣過熱，通膨升溫，升息壓力大，注意反轉訊號",
        "tw_buy":  ["金融保險", "油電燃氣", "航運業", "生技醫療"],
        "tw_avoid":["半導體", "電子零組件", "AI 伺服器"],
        "us_buy":  ["XLE", "XLF", "GLD", "JPM"],
        "us_avoid":["NVDA", "AMD", "SMCI"],
    },
    "衰退期": {
        "emoji":   "🌧️",
        "color":   "#ef4444",
        "desc":    "景氣下行，企業獲利縮減，防禦性資產為主",
        "tw_buy":  ["食品工業", "電信業", "生技醫療", "公用事業"],
        "tw_avoid":["航運業", "鋼鐵工業", "金融保險"],
        "us_buy":  ["XLP", "XLU", "GLD", "TLT", "JNJ"],
        "us_avoid":["TSLA", "SMCI", "ZIM"],
    },
}

# ── 景氣指標追蹤清單 ──────────────────────────────────────────────
INDICATORS = {
    "^GSPC":     {"name": "S&P 500",    "unit": "點"},
    "^VIX":      {"name": "VIX 恐慌指數","unit": ""},
    "^TNX":      {"name": "10年期美債利率","unit": "%"},
    "^IRX":      {"name": "3個月美債利率","unit": "%"},
    "DX-Y.NYB":  {"name": "美元指數 DXY","unit": ""},
    "GC=F":      {"name": "黃金",        "unit": "USD"},
    "CL=F":      {"name": "原油 WTI",    "unit": "USD"},
    "^TWII":     {"name": "台股加權指數", "unit": "點"},
}


def fetch_indicator(sym: str, days: int = 200) -> dict:
    try:
        df = yf.Ticker(sym).history(period=f"{max(days+10, 60)}d")
        if df.empty:
            return {}
        price  = float(df["Close"].iloc[-1])
        prev   = float(df["Close"].iloc[-2]) if len(df) >= 2 else price
        ma200  = float(df["Close"].tail(200).mean()) if len(df) >= 200 else None
        ma50   = float(df["Close"].tail(50).mean())  if len(df) >= 50  else None
        ma20   = float(df["Close"].tail(20).mean())  if len(df) >= 20  else None
        chg    = price - prev
        pct    = chg / prev * 100 if prev else 0
        return {
            "price": round(price, 2),
            "change": round(chg, 2),
            "pct": round(pct, 2),
            "ma200": round(ma200, 2) if ma200 else None,
            "ma50":  round(ma50, 2)  if ma50  else None,
            "ma20":  round(ma20, 2)  if ma20  else None,
            "vs_ma200_pct": round((price/ma200 - 1)*100, 1) if ma200 else None,
        }
    except Exception:
        return {}


def _score_signal(value, thresholds: list, scores: list) -> int:
    """依 thresholds 分段回傳對應 score。"""
    for i, t in enumerate(thresholds):
        if value < t:
            return scores[i]
    return scores[-1]


def compute_cycle_score(indicators: Dict[str, dict]) -> Dict[str, Any]:
    """
    綜合多個指標計算景氣循環評分。
    評分 -10 ~ +10：
      +6 ~ +10 : 擴張期
       0 ~ +5  : 復甦期
      -5 ~ -1  : 高峰期（過熱轉折）
     -10 ~ -6  : 衰退期
    """
    score = 0
    reasons = []

    # 1. S&P 500 vs MA200
    sp = indicators.get("^GSPC", {})
    vs200 = sp.get("vs_ma200_pct")
    if vs200 is not None:
        if vs200 > 10:
            score += 2; reasons.append(f"S&P 站上 MA200 上方 {vs200:.1f}% → 多頭強勢")
        elif vs200 > 0:
            score += 1; reasons.append(f"S&P 在 MA200 上方 {vs200:.1f}%")
        elif vs200 > -5:
            score -= 1; reasons.append(f"S&P 跌破 MA200，距離 {vs200:.1f}%")
        else:
            score -= 2; reasons.append(f"S&P 嚴重跌破 MA200 {vs200:.1f}% → 空頭")

    # 2. VIX（恐慌指數）
    vix = indicators.get("^VIX", {}).get("price")
    if vix:
        if vix < 15:
            score += 2; reasons.append(f"VIX={vix:.1f} 極低，市場非常平靜（貪婪）")
        elif vix < 20:
            score += 1; reasons.append(f"VIX={vix:.1f} 偏低，市場樂觀")
        elif vix < 30:
            score -= 1; reasons.append(f"VIX={vix:.1f} 偏高，市場緊張")
        else:
            score -= 3; reasons.append(f"VIX={vix:.1f} 極高 → 恐慌，可能反轉機會")

    # 3. 殖利率曲線（10年 - 3個月）
    y10 = indicators.get("^TNX", {}).get("price")
    y3m = indicators.get("^IRX", {}).get("price")
    if y10 and y3m:
        spread = y10 - y3m
        if spread > 1.5:
            score += 2; reasons.append(f"殖利率曲線正斜率 {spread:.2f}% → 景氣看好")
        elif spread > 0:
            score += 1; reasons.append(f"殖利率曲線微正 {spread:.2f}%")
        elif spread > -0.5:
            score -= 1; reasons.append(f"殖利率曲線趨平 {spread:.2f}%，需留意")
        else:
            score -= 2; reasons.append(f"殖利率倒掛 {spread:.2f}% → 衰退風險高")

    # 4. 美元指數 DXY
    dxy = indicators.get("DX-Y.NYB", {})
    dxy_ma20 = dxy.get("ma20")
    dxy_price = dxy.get("price")
    if dxy_price and dxy_ma20:
        if dxy_price < dxy_ma20 * 0.99:
            score += 1; reasons.append(f"美元偏弱（DXY={dxy_price:.1f}）→ 風險偏好上升")
        elif dxy_price > dxy_ma20 * 1.02:
            score -= 1; reasons.append(f"美元強勢（DXY={dxy_price:.1f}）→ 資金流向避險")

    # 5. 黃金趨勢
    gold = indicators.get("GC=F", {})
    gold_vs200 = gold.get("vs_ma200_pct")
    if gold_vs200 is not None:
        if gold_vs200 > 10:
            score -= 1; reasons.append(f"黃金大漲 {gold_vs200:.1f}% → 避險需求高")
        elif gold_vs200 < -5:
            score += 1; reasons.append(f"黃金偏弱 → 市場風險偏好")

    # 6. 原油
    oil = indicators.get("CL=F", {})
    oil_pct = oil.get("pct")
    if oil_pct is not None:
        if oil_pct > 2:
            score += 1; reasons.append(f"原油今日大漲 {oil_pct:.1f}% → 景氣需求強")
        elif oil_pct < -3:
            score -= 1; reasons.append(f"原油今日重跌 {oil_pct:.1f}% → 需求疑慮")

    # 7. 台股趨勢
    tw = indicators.get("^TWII", {})
    tw_vs200 = tw.get("vs_ma200_pct")
    if tw_vs200 is not None:
        if tw_vs200 > 5:
            score += 1; reasons.append(f"台股站穩 MA200 上方 {tw_vs200:.1f}%")
        elif tw_vs200 < -5:
            score -= 1; reasons.append(f"台股跌破 MA200 {tw_vs200:.1f}%")

    # ── 判定階段 ──────────────────────────────────────────────────
    if score >= 6:
        phase = "擴張期"
    elif score >= 1:
        phase = "復甦期"
    elif score >= -4:
        phase = "高峰期"
    else:
        phase = "衰退期"

    return {
        "score":   score,
        "phase":   phase,
        "phase_info": CYCLE_PHASES[phase],
        "reasons": reasons,
    }


def morning_signal(us_prices: dict) -> list:
    """
    根據美股昨收的漲跌，推算台股隔天可能強勢的族群和標的。
    回傳 list of { "reason", "tw_sectors", "tw_stocks", "strength" }
    """
    from us_tw_impact import US_TW_IMPACT
    signals = []
    for sym, p in us_prices.items():
        pct = p.get("pct", 0)
        if abs(pct) < 1.5:
            continue
        impact = US_TW_IMPACT.get(sym, {})
        if not impact:
            continue
        tw_list = impact.get("tw_stocks", [])
        tw_tickers = [t for t, _, _ in tw_list
                      if not any(k in t for k in ["廠","者","牌","PANASONIC","ALB","NIO"])]
        direction = "上漲" if pct > 0 else "下跌"
        signals.append({
            "sym":      sym,
            "name":     impact.get("name", sym),
            "theme":    impact.get("theme", ""),
            "pct":      pct,
            "direction": direction,
            "reason":   impact.get("reason", ""),
            "impact_type": impact.get("impact_type", ""),
            "tw_tickers": tw_tickers,
            "tw_stocks": tw_list,
            "strength": abs(pct),
        })
    signals.sort(key=lambda x: x["strength"], reverse=True)
    return signals[:10]
