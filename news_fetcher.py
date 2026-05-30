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


# ── 新聞關鍵字 → 產業影響對照表 ──────────────────────────────────────
NEWS_IMPACT_MAP = [
    {
        "keywords": ["nvidia","gpu","cuda","h100","h200","b200","blackwell","hopper","ai chip"],
        "theme":    "AI GPU / 算力",
        "color":    "#22c55e",
        "tw_stocks": [("2330.TW","台積電"), ("2382.TW","廣達"), ("2356.TW","英業達"),
                      ("3017.TW","奇鋐"), ("2308.TW","台達電")],
    },
    {
        "keywords": ["apple","iphone","mac","airpods","vision pro","ios","wwdc"],
        "theme":    "蘋果供應鏈",
        "color":    "#9ca3af",
        "tw_stocks": [("2317.TW","鴻海"), ("3008.TW","大立光"), ("2354.TW","鴻準"),
                      ("2382.TW","廣達"), ("2330.TW","台積電")],
    },
    {
        "keywords": ["micron","dram","hbm","nand","memory","semiconductor memory","flash"],
        "theme":    "記憶體 / DRAM",
        "color":    "#8b5cf6",
        "tw_stocks": [("2408.TW","南亞科"), ("2344.TW","華邦電"), ("2337.TW","旺宏"),
                      ("6770.TW","力積電"), ("3711.TW","日月光")],
    },
    {
        "keywords": ["tsmc","taiwan semi","foundry","wafer","3nm","2nm","cowos","packaging"],
        "theme":    "晶圓代工 / 封裝",
        "color":    "#3b82f6",
        "tw_stocks": [("2330.TW","台積電"), ("2303.TW","聯電"), ("3711.TW","日月光"),
                      ("5347.TW","世界先進")],
    },
    {
        "keywords": ["tesla","ev","electric vehicle","lithium","battery","charging","byd"],
        "theme":    "電動車 / 綠能",
        "color":    "#ef4444",
        "tw_stocks": [("2317.TW","鴻海"), ("2308.TW","台達電"), ("3665.TW","貿聯KY"),
                      ("2330.TW","台積電")],
    },
    {
        "keywords": ["microsoft","azure","copilot","openai","chatgpt","cloud","aws","google cloud"],
        "theme":    "AI 雲端 / 資本支出",
        "color":    "#0ea5e9",
        "tw_stocks": [("2382.TW","廣達"), ("2356.TW","英業達"), ("6669.TW","緯穎"),
                      ("3017.TW","奇鋐")],
    },
    {
        "keywords": ["amd","epyc","mi300","radeon","ryzen","cpu","processor"],
        "theme":    "CPU / GPU 競爭",
        "color":    "#f97316",
        "tw_stocks": [("2330.TW","台積電"), ("3711.TW","日月光"), ("2382.TW","廣達")],
    },
    {
        "keywords": ["intel","gaudi","xeon","foundry 2.0","18a"],
        "theme":    "英特爾 / 代工競爭",
        "color":    "#6b7280",
        "tw_stocks": [("2330.TW","台積電（競爭反向受益）"),("2303.TW","聯電")],
    },
    {
        "keywords": ["qualcomm","snapdragon","5g","modem","handset","smartphone","mobile chip"],
        "theme":    "手機晶片 / 5G",
        "color":    "#f59e0b",
        "tw_stocks": [("2454.TW","聯發科"), ("2379.TW","瑞昱"), ("2330.TW","台積電")],
    },
    {
        "keywords": ["server","data center","hpc","hyperscaler","infrastructure","capex","spending"],
        "theme":    "資料中心 / 伺服器",
        "color":    "#10b981",
        "tw_stocks": [("2382.TW","廣達"), ("2356.TW","英業達"), ("6669.TW","緯穎"),
                      ("SMCI","超微電腦")],
    },
    {
        "keywords": ["shipping","freight","container","tanker","dry bulk","cosco","maersk"],
        "theme":    "航運",
        "color":    "#64748b",
        "tw_stocks": [("2603.TW","長榮"), ("2609.TW","陽明"), ("2615.TW","萬海")],
    },
    {
        "keywords": ["fed","rate","inflation","cpi","interest rate","fomc","powell","rate cut"],
        "theme":    "Fed / 利率政策",
        "color":    "#fbbf24",
        "tw_stocks": [("2881.TW","富邦金"), ("2882.TW","國泰金"), ("2886.TW","兆豐金")],
    },
    {
        "keywords": ["solar","renewable","wind","energy storage","battery storage","green energy"],
        "theme":    "綠能 / 儲能",
        "color":    "#84cc16",
        "tw_stocks": [("2308.TW","台達電"), ("3576.TW","新日光"), ("3023.TW","信邦")],
    },
    {
        "keywords": ["biotech","drug","fda","clinical","pharmaceutical","gene","obesity","glp-1"],
        "theme":    "生技醫療",
        "color":    "#ec4899",
        "tw_stocks": [("4711.TW","台灣醫材"), ("4144.TW","聖祥"), ("6548.TW","長聖")],
    },
    {
        "keywords": ["supermicro","smci","dell","hpe","server maker","rack","liquid cool"],
        "theme":    "AI Server 整機",
        "color":    "#22c55e",
        "tw_stocks": [("2382.TW","廣達"), ("2356.TW","英業達"), ("3017.TW","奇鋐"),
                      ("2308.TW","台達電")],
    },
]


def tag_news_impact(title: str) -> dict:
    """
    用關鍵字比對，快速給新聞標上產業影響標籤。
    回傳 {"theme", "color", "tw_stocks", "matched"} 或空 dict。
    """
    title_lower = title.lower()
    for entry in NEWS_IMPACT_MAP:
        if any(kw in title_lower for kw in entry["keywords"]):
            return {
                "theme":     entry["theme"],
                "color":     entry["color"],
                "tw_stocks": entry["tw_stocks"],
                "matched":   True,
            }
    return {"matched": False}


def get_api_key():
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
