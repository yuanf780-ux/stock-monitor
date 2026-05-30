"""
新聞抓取與 AI 摘要模組
整合 yfinance 新聞 + Claude API 分析成可行動的投資洞察
"""
import os
import requests
import yfinance as yf
from datetime import datetime, timezone
from typing import List, Dict


# ── 關鍵股票新聞追蹤清單 ──────────────────────────────────────────
NEWS_TICKERS = [
    "NVDA", "AAPL", "TSLA", "MU", "SMCI", "AMD",
    "MSFT", "META", "GOOGL", "AMZN", "AVGO", "TSM",
]


def fetch_stock_news(tickers: List[str] = None, max_per_ticker: int = 3) -> List[Dict]:
    """從 yfinance 抓取多個股票的最新新聞"""
    if tickers is None:
        tickers = NEWS_TICKERS
    all_news = []
    seen_titles = set()

    for sym in tickers:
        try:
            news_list = yf.Ticker(sym).news or []
            for n in news_list[:max_per_ticker]:
                title = n.get("title", "")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                # 時間轉換
                pub_ts = n.get("providerPublishTime", 0)
                try:
                    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                    pub_str = pub_dt.strftime("%m/%d %H:%M UTC")
                except Exception:
                    pub_str = ""
                all_news.append({
                    "title":     title,
                    "publisher": n.get("publisher", ""),
                    "url":       n.get("link", ""),
                    "time":      pub_str,
                    "ticker":    sym,
                    "ts":        pub_ts,
                })
        except Exception:
            continue

    # 依時間排序（最新在前）
    all_news.sort(key=lambda x: x["ts"], reverse=True)
    return all_news[:25]


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def ai_news_briefing(news_list: List[Dict], us_movers: List[Dict],
                     cycle_phase: str) -> str:
    """
    用 Claude 分析今日新聞 + 美股動向，輸出可行動的台股晨報。
    """
    api_key = _get_api_key()
    if not api_key:
        return ""

    # 準備新聞摘要給 Claude
    news_text = "\n".join(
        f"- [{n['ticker']}] {n['title']} ({n['time']})"
        for n in news_list[:15]
    )
    movers_text = "\n".join(
        f"- {m['name']}({m['sym']}) {m['pct']:+.2f}% | 題材：{m['theme']}"
        for m in us_movers[:8]
    ) if us_movers else "無顯著漲跌"

    prompt = f"""你是一位專注台美股市場的操盤手助理，請根據以下資訊，產出今日台股投資者最需要知道的「早報摘要」。

目前景氣循環：{cycle_phase}

美股今日主要漲跌（>±1.5%）：
{movers_text}

今日重要財經新聞：
{news_text}

請用繁體中文，以以下格式輸出（每點1-2句，具體直接）：

## 今日3大關鍵訊號
1. [題材名稱] 說明原因 → 台股影響：XXX、XXX
2. [題材名稱] 說明原因 → 台股影響：XXX、XXX
3. [題材名稱] 說明原因 → 台股影響：XXX、XXX

## 明日台股操作方向
- 強勢：（1-2個具體族群或股票）
- 觀望：（1個需注意的風險點）
- 回避：（1個弱勢方向）

## 本週波段重點
（1-2句，結合景氣循環位置給出方向性判斷）

注意：請直接給結論，不要說「根據資料」或「請注意」，語氣像是操盤老手在給建議。"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"AI 分析暫時無法使用：{e}"
