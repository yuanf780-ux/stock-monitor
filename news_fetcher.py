"""
新聞抓取與 AI 摘要模組
整合 yfinance 新聞 + Claude API 分析成可行動的投資洞察
"""
import os
import requests
import yfinance as yf
from datetime import datetime, timezone
from typing import List, Dict


# ── 關鍵股票新聞追蹤清單（12 支，覆蓋主要題材）────────────────────
NEWS_TICKERS = [
    "NVDA", "AAPL", "TSLA", "MU",    # AI/半導體/記憶體/EV
    "MSFT", "AMD", "AVGO", "QCOM",   # AI雲端/CPU/網路晶片/手機
    "SMCI", "META", "GOOGL", "AMZN", # AI Server/雲端大廠
]


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

    # 轉換成台灣時間和美東時間
    time_tw = time_us = ""
    try:
        if pub_ts:
            from datetime import timedelta
            dt_utc = datetime.fromtimestamp(pub_ts, tz=timezone.utc)

            # 台灣 UTC+8
            dt_tw = dt_utc + timedelta(hours=8)
            time_tw = dt_tw.strftime("%m/%d %H:%M")

            # 美東：3月第2週日 - 11月第1週日 為 EDT(UTC-4)，其餘 EST(UTC-5)
            month = dt_utc.month
            is_edt = 3 <= month <= 11  # 簡化判斷
            offset = -4 if is_edt else -5
            tz_label = "EDT" if is_edt else "EST"
            dt_us = dt_utc + timedelta(hours=offset)
            time_us = dt_us.strftime("%m/%d %H:%M") + f" {tz_label}"
    except Exception:
        pass

    return {"title": title, "publisher": publisher, "url": url,
            "time": time_tw, "time_us": time_us,
            "ticker": sym, "ts": pub_ts}


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


def fetch_stock_news(tickers: List[str] = None, max_per_ticker: int = 8,
                     hours: int = 24) -> List[Dict]:
    """
    平行抓取多股票新聞，保留過去 N 小時的全部新聞（預設 24 小時）。
    max_per_ticker：每支股票最多抓幾則（yfinance 上限約 10-15）
    hours：保留幾小時內的新聞
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if tickers is None:
        tickers = NEWS_TICKERS

    cutoff = _time.time() - hours * 3600   # 24小時前的 timestamp

    seen_titles: set = set()
    all_news: List[Dict] = []

    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as pool:
        futures = {pool.submit(_fetch_one, sym, max_per_ticker, set()): sym
                   for sym in tickers}
        for fut in as_completed(futures, timeout=12):
            try:
                items = fut.result()
                for item in items:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        all_news.append(item)
            except Exception:
                pass

    all_news.sort(key=lambda x: x["ts"], reverse=True)

    # 保留 24 小時內的新聞；若太少則至少保留最新 15 則
    within_day = [n for n in all_news if n["ts"] >= cutoff]
    return within_day if len(within_day) >= 10 else all_news[:max(15, len(within_day))]


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


def zh_news_analysis(news_item: Dict, impact: Dict) -> str:
    """
    點「中文解析」後的完整分析：
    新聞摘要 + 有利題材 + 不利題材 + 多空判斷
    """
    theme   = impact.get("theme", "")
    tw_list = impact.get("tw_stocks", [])
    stock_list_str = "\n".join(
        f"  - {ticker} {name}" for ticker, name in tw_list[:6]
    ) if tw_list else "  （無特定台股）"

    api_key = get_api_key()
    if not api_key:
        if impact.get("matched"):
            names = "、".join(n for _, n in tw_list[:3])
            return f"【{theme}】相關消息，台股 {names} 明日值得留意。"
        return ""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"你是台股操盤手助理，請針對以下新聞給出完整分析。\n\n"
            f"新聞：{news_item['title']}\n"
            f"題材分類：{theme or '一般財經'}\n"
            f"可能相關台股（代碼名稱如下，請只使用這些，不可自行發明）：\n"
            f"{stock_list_str}\n\n"
            f"請用繁體中文，嚴格按以下格式輸出：\n\n"
            f"新聞重點：（1~2句說清楚這則新聞的事實）\n\n"
            f"有利題材：（哪些產業/族群受益，例：AI伺服器、記憶體，若無則填「無」）\n"
            f"有利台股：（上方清單中受益的股票「代碼+名稱」，最多3支，若無則填「無」）\n\n"
            f"不利題材：（哪些產業/族群受害，若無則填「無」）\n"
            f"不利台股：（上方清單中受害的股票「代碼+名稱」，最多3支，若無則填「無」）\n\n"
            f"整體方向：（一句話：這對台股整體是偏多/偏空/中性，並說明理由）"
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        err = str(e)
        if "credit" in err.lower() or "balance" in err.lower():
            return "💳 API 額度不足，請到 console.anthropic.com/settings/billing 充值。"
        if impact.get("matched"):
            names = "、".join(n for _, n in tw_list[:3])
            return f"【{theme}】消息，{names} 明日值得留意。"
        return f"AI 分析暫時失敗：{err[:60]}"


# ── 自動中文摘要（無需按鈕，顯示在標題下方）────────────────────────────

# 關鍵字替換（無 API 時的基礎版）
# 句型模板（優先比對）
_PATTERNS = [
    ("hits.*trillion", "市值突破兆元大關"),
    ("market cap", "市值"),
    ("earnings beat", "財報超預期"),
    ("earnings miss", "財報不如預期"),
    ("price target.*raised", "目標價上調"),
    ("price target.*lowered", "目標價下調"),
    ("record high", "創歷史新高"),
    ("all.time high", "創歷史新高"),
    ("52.week high", "創52週新高"),
    ("layoff", "宣布裁員"),
    ("laid off", "宣布裁員"),
    ("ipo", "即將 IPO 上市"),
    ("stock split", "宣布股票分割"),
    ("buyback", "啟動庫藏股回購"),
    ("dividend", "公告配息"),
    ("acquisition", "宣布收購"),
    ("merger", "合併計畫"),
    ("partnership", "宣布合作"),
    ("sells.*shares", "減持持股"),
    ("increases.*stake", "增持股份"),
    ("buys.*stake", "買進股份"),
    ("top holdings", "主要持股"),
    ("concentration risk", "集中風險"),
    ("ai demand", "AI 需求強勁"),
    ("data center", "資料中心需求"),
]

_KW = {
    "earnings": "財報", "revenue": "營收", "profit": "獲利", "sales": "銷售",
    "beat": "超標", "miss": "未達預期", "guidance": "展望調整",
    "upgrade": "評級調升", "downgrade": "評級調降",
    "overweight": "增持評級", "outperform": "優於大盤",
    "deal": "合約簽署", "layoffs": "宣布裁員", "hiring": "擴大招聘",
    "dividend": "配息", "buyback": "回購股票",
    "AI": "AI 相關", "chip": "晶片", "semiconductor": "半導體",
    "memory": "記憶體", "data center": "資料中心", "server": "伺服器",
    "electric vehicle": "電動車", "EV": "電動車", "battery": "電池",
    "inflation": "通膨", "rate cut": "降息預期", "fed": "Fed 政策",
    "price target": "目標價", "risk": "風險", "rally": "股價上漲",
}

def _quick_zh(title: str) -> str:
    """不需 API，用模板+關鍵字快速生成中文摘要"""
    import re as _re
    t = title.lower()
    # 公司名稱對照
    companies = {
        "nvidia": "輝達", "apple": "蘋果", "microsoft": "微軟",
        "google": "谷歌", "alphabet": "Alphabet", "amazon": "亞馬遜",
        "tesla": "特斯拉", "meta": "Meta", "micron": "美光",
        "amd": "超微", "tsmc": "台積電", "qualcomm": "高通",
        "broadcom": "博通", "intel": "英特爾", "dell": "戴爾",
        "hpe": "惠普企業", "supermicro": "超微電腦", "arm": "Arm",
        "sk hynix": "SK海力士", "samsung": "三星",
        "warren buffett": "巴菲特", "renaissance": "文藝復興基金",
    }
    corp = next((zh for en, zh in companies.items() if en in t), "")
    # 句型模板優先
    for pat, desc in _PATTERNS:
        if _re.search(pat, t):
            return f"{corp}：{desc}" if corp else desc
    # 關鍵字組合
    hits = [zh for en, zh in _KW.items() if en.lower() in t]
    parts = ([corp] if corp else []) + hits[:2]
    return "・".join(parts) if parts else ""


def is_key_news(title: str, impact: dict) -> bool:
    """
    判斷是否為重點新聞（財報/展望/大事件/強題材匹配）。
    """
    t = title.lower()
    key_patterns = [
        "earnings", "beat", "miss", "guidance", "outlook", "forecast",
        "record", "all-time", "trillion", "acquisition", "merger",
        "layoff", "ipo", "price target", "upgrade", "downgrade",
        "rate cut", "fomc", "fed", "quarterly result",
        "q1","q2","q3","q4", "revenue", "profit",
    ]
    # 有強題材且有台股對照 = 重點
    has_theme = bool(impact.get("matched"))
    has_tw    = len(impact.get("tw_stocks", [])) >= 3
    has_kw    = any(kw in t for kw in key_patterns)
    return (has_kw and has_theme) or (has_tw and has_kw)


def batch_auto_summary(news_list: List[Dict]) -> Dict[int, str]:
    """
    批次生成所有新聞的中文摘要。
    無 API → 關鍵字版
    有 API → 分批次（每批 20 則）呼叫 Claude Haiku 翻譯所有標題
    """
    import re as _re
    result: Dict[int, str] = {}

    # 無 API：全部用關鍵字版
    api_key = get_api_key()
    if not api_key:
        for i, n in enumerate(news_list):
            s = _quick_zh(n["title"])
            if s:
                result[i] = s
        return result

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        BATCH = 20  # 每批 20 則，避免 token 超限

        def _translate_batch(batch_items):
            """翻譯一批新聞，回傳 {local_idx: 中文}"""
            titles_str = "\n".join(
                f"{j+1}. {item['title']}" for j, item in enumerate(batch_items)
            )
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=700,
                messages=[{"role": "user", "content": (
                    f"請將以下英文新聞標題翻成繁體中文，每則用一句話（20~35字）說清楚「誰做了什麼事」。\n"
                    f"格式：數字. 中文標題（直接說重點，不要加評論）\n\n"
                    f"範例：\n"
                    f"1. 輝達第二季財報超預期，AI 晶片需求持續爆發，股價盤後漲 8%\n"
                    f"2. 文藝復興基金減持美光科技持股約 2 千萬美元\n\n"
                    f"新聞：\n{titles_str}"
                )}],
            )
            batch_result = {}
            for line in msg.content[0].text.strip().split("\n"):
                line = line.strip()
                m = _re.match(r"^(\d+)[\.。、]\s*(.+)$", line)
                if m:
                    local_idx = int(m.group(1)) - 1
                    summary   = m.group(2).strip()
                    if 0 <= local_idx < len(batch_items) and summary:
                        batch_result[local_idx] = summary
            return batch_result

        # 分批次翻譯
        for batch_start in range(0, len(news_list), BATCH):
            batch = news_list[batch_start:batch_start + BATCH]
            try:
                batch_result = _translate_batch(batch)
                for local_idx, summary in batch_result.items():
                    result[batch_start + local_idx] = summary
            except Exception:
                # 這批失敗 → 用關鍵字補
                for j, n in enumerate(batch):
                    s = _quick_zh(n["title"])
                    if s:
                        result[batch_start + j] = s

        return result
    except Exception:
        # 全部失敗 → 關鍵字版
        for i, n in enumerate(news_list):
            s = _quick_zh(n["title"])
            if s:
                result[i] = s
        return result


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
        if "credit" in str(e).lower() or "balance" in str(e).lower():
            return "💳 Anthropic 額度不足，請到 https://console.anthropic.com/settings/billing 充值（最低 $5）後再試。"
        return f"AI 分析暫時無法使用：{e}"
