"""
新聞抓取與 AI 摘要模組
整合 yfinance 新聞 + Claude API 分析成可行動的投資洞察
"""
import os
import requests
import yfinance as yf
from datetime import datetime, timezone
from typing import List, Dict


# ── 關鍵股票新聞追蹤清單（精簡到 6 支最重要的）────────────────────
NEWS_TICKERS = ["NVDA", "AAPL", "TSLA", "MU", "MSFT", "AMD"]


def _parse_news_item(raw: dict, sym: str) -> dict:
    """解析 yfinance 新聞（相容新舊兩種格式）"""
    # 新格式：raw["content"]["title"]
    content = raw.get("content", {})
    if content:
        title = content.get("title", "")
        pub_ts = 0
        try:
            pt = content.get("pubDate") or content.get("publishedAt") or ""
            if pt:
                from datetime import datetime as _dt
                pub_ts = int(_dt.fromisoformat(pt.rstrip("Z")).timestamp())
        except Exception:
            pass
        url = ""
        try:
            url = (content.get("canonicalUrl", {}).get("url", "")
                   or content.get("clickThroughUrl", {}).get("url", ""))
        except Exception:
            pass
        publisher = ""
        try:
            publisher = content.get("provider", {}).get("displayName", "")
        except Exception:
            pass
    else:
        # 舊格式（直接 title 在頂層）
        title     = raw.get("title", "")
        pub_ts    = raw.get("providerPublishTime", 0)
        url       = raw.get("link", "")
        publisher = raw.get("publisher", "")

    try:
        pub_str = datetime.fromtimestamp(pub_ts, tz=timezone.utc).strftime("%m/%d %H:%M") if pub_ts else ""
    except Exception:
        pub_str = ""

    return {"title": title, "publisher": publisher, "url": url,
            "time": pub_str, "ticker": sym, "ts": pub_ts}


def _fetch_one(sym: str, max_n: int, seen: set) -> List[Dict]:
    """抓單一股票的新聞（供平行執行）"""
    result = []
    try:
        for raw in (yf.Ticker(sym).news or [])[:max_n]:
            item = _parse_news_item(raw, sym)
            if item["title"] and item["title"] not in seen:
                result.append(item)
    except Exception:
        pass
    return result


def fetch_stock_news(tickers: List[str] = None, max_per_ticker: int = 3) -> List[Dict]:
    """平行抓取多股票新聞，速度比串行快 4-5 倍"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if tickers is None:
        tickers = NEWS_TICKERS

    seen_titles: set = set()
    all_news: List[Dict] = []

    with ThreadPoolExecutor(max_workers=min(len(tickers), 6)) as pool:
        futures = {pool.submit(_fetch_one, sym, max_per_ticker, set()): sym
                   for sym in tickers}
        for fut in as_completed(futures, timeout=8):
            try:
                items = fut.result()
                for item in items:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        all_news.append(item)
            except Exception:
                pass

    all_news.sort(key=lambda x: x["ts"], reverse=True)
    return all_news[:20]


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
