import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

from config import DEFAULT_TW_STOCKS, DEFAULT_US_STOCKS, ALERT_DEFAULTS, INDICATOR_COLORS
from data_fetcher import (fetch_stock_info, fetch_history, fetch_batch_prices,
                          name_to_ticker, get_all_stock_options, option_to_ticker,
                          fetch_kline, KLINE_PRESETS)
from indicators import compute_all, get_signals
import ai_analyst
import sector_data as sd
import sector_predictor
import market_index as mi
import tw_us_map
import supply_chain as sc
import institutional as inst
import us_tw_impact as uti
import cycle as cyc
import news_fetcher as nf

# ── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="股票監控系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",   # 手機自動收合
)

st.markdown("""<style>
/* ══ 基礎樣式 ══════════════════════════════════════════════════════ */
.stock-name  { font-size: 1em;    font-weight: 600; color: #f1f5f9; }
.stock-code  { font-size: 0.72em; color: #94a3b8; }
.stock-price { font-size: 1.45em; font-weight: 700; color: #ffffff; }
.theme-tag {
    display: inline-block;
    background: #1e3a5f; color: #93c5fd;
    border-radius: 4px; padding: 2px 7px;
    font-size: 0.72em; margin: 2px 2px 2px 0; font-weight: 500;
}
.signal-box {
    background: #1a1a2e; border: 1px solid #374151;
    border-radius: 8px; padding: 14px 16px;
    margin-top: 8px; white-space: pre-wrap;
    color: #e2e8f0; font-size: 0.9em; line-height: 1.6;
}
/* ══ 手機版全面優化 ════════════════════════════════════════════════ */
@media (max-width: 768px) {
    /* 縮小邊距，讓內容更寬 */
    .block-container {
        padding: 0.4rem 0.4rem 5rem 0.4rem !important;
        max-width: 100% !important;
    }
    /* 所有欄位在手機變 2 欄（由 CSS 控制，不影響 Streamlit 邏輯） */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    [data-testid="column"] {
        min-width: calc(50% - 6px) !important;
        flex: 0 0 calc(50% - 6px) !important;
    }
    /* 3 欄的情況也變 2 欄 */
    [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(odd):last-child {
        min-width: 100% !important;
    }
    /* 字體放大，觸控友好 */
    .stock-price { font-size: 1.3em !important; }
    .stock-name  { font-size: 0.95em !important; }
    /* 按鈕放大觸控區域 */
    button, [data-testid="baseButton-secondary"],
    [data-testid="baseButton-primary"] {
        min-height: 44px !important;
        font-size: 1em !important;
        touch-action: manipulation;
    }
    /* 側邊欄在手機自動收起 */
    [data-testid="stSidebar"] { width: 280px !important; }
    /* radio 按鈕間距 */
    [data-testid="stRadio"] label { padding: 6px 4px !important; font-size: 0.9em !important; }
    /* selectbox */
    [data-testid="stSelectbox"] select { font-size: 1em !important; }
    /* 圖表全寬 */
    .js-plotly-plot { max-width: 100vw !important; }
    /* 頁面標題 */
    h1 { font-size: 1.6em !important; }
    h2 { font-size: 1.3em !important; }
    h3 { font-size: 1.1em !important; }
    /* 表格文字 */
    [data-testid="stDataFrame"] { font-size: 0.85em !important; }
}
/* ══ 手機底部導覽列 ════════════════════════════════════════════════ */
#mobile-nav {
    display: none;
}
@media (max-width: 768px) {
    #mobile-nav {
        display: flex !important;
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background: #1e293b;
        border-top: 1px solid #334155;
        z-index: 9999;
        padding: 0;
    }
    #mobile-nav a {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 8px 2px;
        color: #94a3b8;
        text-decoration: none;
        font-size: 0.65em;
        font-weight: 500;
        cursor: pointer;
        border: none;
        background: transparent;
        min-height: 56px;
    }
    #mobile-nav a span.icon { font-size: 1.5em; line-height: 1; margin-bottom: 2px; }
    #mobile-nav a.active { color: #3b82f6; }
}
</style>""", unsafe_allow_html=True)

# 開放給所有人使用（無密碼）

# ── Session State ──────────────────────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = [*DEFAULT_TW_STOCKS, *DEFAULT_US_STOCKS]
if "page" not in st.session_state:
    st.session_state.page = "即時大盤"
if "detail_ticker" not in st.session_state:
    st.session_state.detail_ticker = ""
if "pending_remove" not in st.session_state:
    st.session_state.pending_remove = []


def goto_detail(ticker: str, name: str = ""):
    st.session_state.detail_ticker = ticker
    st.session_state.detail_name   = name
    st.session_state.page          = "個股深度分析"
    st.rerun()


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 股票監控系統")
    st.divider()

    _pages = [
        "景氣循環 & 明日台股",
        "即時大盤",
        "自選股列表",
        "個股深度分析",
        "外資籌碼追蹤",
        "美股信號 → 台股影響",
        "族群分析",
        "台美對照 & 供應鏈",
    ]
    # 不用 key，讓 index 每次都生效（避免 StreamlitAPIException）
    _cur_idx = _pages.index(st.session_state.page) if st.session_state.page in _pages else 0
    page = st.radio("頁面", _pages, index=_cur_idx)
    if page != st.session_state.page:
        st.session_state.page = page
        st.rerun()

    st.divider()
    st.markdown("**搜尋個股**")

    @st.cache_data(ttl=3600)
    def _stock_options():
        return ["— 輸入名稱或代碼搜尋 —"] + get_all_stock_options()

    opts = _stock_options()
    sel = st.selectbox("搜尋個股", opts,
                       index=0, key="sidebar_select",
                       label_visibility="collapsed")
    if sel and sel != opts[0]:
        t, n = option_to_ticker(sel)
        if st.button("查看分析", use_container_width=True, type="primary"):
            st.session_state.detail_ticker = t
            st.session_state.page = "個股深度分析"
            st.rerun()

    st.divider()
    st.markdown("**自選股（本次瀏覽有效）**")
    st.caption("關閉瀏覽器後自動重置")

    with st.form("add_form", clear_on_submit=True):
        add_sel = st.selectbox("新增股票", ["— 選擇股票 —"] + get_all_stock_options(),
                               label_visibility="collapsed", key="add_sel_sb")
        if st.form_submit_button("加入", use_container_width=True):
            if add_sel and add_sel != "— 選擇股票 —":
                t, n = option_to_ticker(add_sel)
                if not any(w["ticker"] == t for w in st.session_state.watchlist):
                    st.session_state.watchlist.append({"ticker": t, "name": n})
                    st.rerun()

    if len(st.session_state.watchlist) > len([*DEFAULT_TW_STOCKS, *DEFAULT_US_STOCKS]):
        rm = st.selectbox("移除股票", ["— 選擇要移除的 —"] +
                          [f'{w["name"]} ({w["ticker"]})' for w in st.session_state.watchlist],
                          label_visibility="collapsed", key="rm_sel")
        if rm and rm != "— 選擇要移除的 —" and st.button("移除", use_container_width=True):
            tk = rm.split("(")[-1].replace(")", "").strip()
            st.session_state.watchlist = [w for w in st.session_state.watchlist if w["ticker"] != tk]
            st.rerun()

    st.divider()
    st.caption(f"資料更新：{pd.Timestamp.now().strftime('%H:%M:%S')}")
    if st.button("刷新資料", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# ── Shared helpers ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _sparkline(series, height=60):
    if series is None or len(series) < 2:
        return None
    base = float(series.iloc[0])
    pct  = (series / base - 1) * 100
    up   = float(pct.iloc[-1]) >= 0
    lc   = "#22c55e" if up else "#ef4444"
    fc   = "rgba(34,197,94,0.12)" if up else "rgba(239,68,68,0.12)"
    fig  = go.Figure(go.Scatter(y=pct.values, mode="lines",
                                 line=dict(color=lc, width=1.8),
                                 fill="tozeroy", fillcolor=fc))
    fig.update_layout(height=height, margin=dict(l=0,r=0,t=0,b=0),
                      xaxis_visible=False, yaxis_visible=False,
                      showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    return fig


@st.cache_data(ttl=300)
def _batch_prices(tickers_tuple):
    return fetch_batch_prices(list(tickers_tuple))


# 股票選單快取在模組層級，避免 page_detail 內部定義造成不穩定
@st.cache_data(ttl=3600)
def _all_stock_opts():
    try:
        opts = get_all_stock_options()
        return opts if opts else []
    except Exception:
        return []


def _price_html(ticker, prices):
    p = prices.get(ticker, {})
    if not p:
        return '<span style="color:#6b7280">—</span>'
    pct   = p["pct"]
    color = "#22c55e" if pct >= 0 else "#ef4444"
    arrow = "▲" if pct >= 0 else "▼"
    return (f'<span style="color:#fff;font-weight:bold">{p["price"]:,.2f}</span> '
            f'<span style="color:{color};font-size:0.82em">{arrow}{pct:+.2f}%</span>')


def _momentum_score(ticker: str) -> dict:
    """Simple momentum score -5..+5 combining technicals."""
    try:
        df = fetch_history(ticker, period="3mo")
        if df is None or len(df) < 20:
            return {"score": 0, "label": "中性", "color": "#9ca3af", "reasons": []}
        df = compute_all(df)
        last = df.iloc[-1]
        score = 0
        reasons = []
        rsi = last.get("rsi")
        if rsi:
            if rsi > 65:
                score += 1; reasons.append(f"RSI {rsi:.0f} 強勢")
            elif rsi < 35:
                score -= 1; reasons.append(f"RSI {rsi:.0f} 弱勢")
        ma5, ma20, ma60 = last.get("ma5"), last.get("ma20"), last.get("ma60")
        price = last.get("Close", 0)
        if ma20 and price > ma20:
            score += 1; reasons.append("站上 MA20")
        elif ma20 and price < ma20:
            score -= 1; reasons.append("跌破 MA20")
        if ma60 and price > ma60:
            score += 1; reasons.append("站上 MA60")
        elif ma60 and price < ma60:
            score -= 1; reasons.append("跌破 MA60")
        if ma5 and ma20 and ma5 > ma20:
            score += 1; reasons.append("MA5 > MA20 多頭排列")
        elif ma5 and ma20 and ma5 < ma20:
            score -= 1; reasons.append("MA5 < MA20 空頭排列")
        macd = last.get("macd"); sig = last.get("macd_signal")
        if macd and sig:
            if macd > sig:
                score += 1; reasons.append("MACD 在訊號線上方")
            else:
                score -= 1; reasons.append("MACD 在訊號線下方")

        if score >= 3:
            label, color = "強勢", "#22c55e"
        elif score >= 1:
            label, color = "偏強", "#86efac"
        elif score <= -3:
            label, color = "弱勢", "#ef4444"
        elif score <= -1:
            label, color = "偏弱", "#fca5a5"
        else:
            label, color = "中性", "#9ca3af"
        return {"score": score, "label": label, "color": color, "reasons": reasons}
    except Exception:
        return {"score": 0, "label": "—", "color": "#9ca3af", "reasons": []}


# ══════════════════════════════════════════════════════════════════════════
# PAGE 0: 即時大盤
# ══════════════════════════════════════════════════════════════════════════
def page_market():
    st.title("📡 即時大盤監控")

    @st.fragment(run_every="60s")
    def _mkt():
        st.caption(f"自動每分鐘更新 · {pd.Timestamp.now().strftime('%H:%M:%S')}")

        st.markdown("#### 🇺🇸 美股三大指數")
        c1, c2, c3 = st.columns(3)
        for sym, col in zip(["^GSPC", "^DJI", "^IXIC"], [c1, c2, c3]):
            d = mi.fetch_us_index(sym)
            if not d.get("valid"):
                col.error(f"{sym} 無資料"); continue
            pct   = d["pct"]
            color = "#22c55e" if pct >= 0 else "#ef4444"
            arrow = "▲" if pct >= 0 else "▼"
            border = d.get("color", "#4f46e5")
            with col:
                st.markdown(
                    f'<div style="background:#1e1e2e;border-radius:10px;padding:12px 16px;border-left:4px solid {border};">'
                    f'<div style="font-size:0.7em;color:#9ca3af">{d["short"]}</div>'
                    f'<div style="font-weight:600;color:#e2e8f0">{d["name"]}</div>'
                    f'<div style="font-size:1.5em;font-weight:bold;color:#fff">{d["price"]:,.2f}</div>'
                    f'<div style="color:{color};font-weight:bold">{arrow} {d["change"]:+,.2f} ({pct:+.2f}%)</div>'
                    f'</div>', unsafe_allow_html=True)
                s = mi.fetch_intraday(sym)
                fig = _sparkline(s)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with st.expander("📈 美三指今日走勢對比", expanded=False):
            fig_cmp = go.Figure()
            for sym, info in mi.US_INDICES.items():
                s = mi.fetch_intraday(sym)
                if s is not None and len(s) > 1:
                    base = float(s.iloc[0])
                    fig_cmp.add_trace(go.Scatter(y=(s/base-1)*100, name=info["name"],
                        line=dict(color=info["color"], width=2)))
            fig_cmp.add_hline(y=0, line_dash="dot", line_color="#6b7280", opacity=0.5)
            fig_cmp.update_layout(template="plotly_dark", height=260,
                margin=dict(l=10,r=10,t=10,b=10), xaxis_visible=False,
                yaxis_title="vs 開盤(%)", legend=dict(orientation="h"))
            st.plotly_chart(fig_cmp, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

        st.divider()
        st.markdown("#### 🇹🇼 台股指數 & 台指期")
        t1, t2, t3 = st.columns(3)
        tw  = mi.fetch_tw_index()
        txd = mi.fetch_tx_day()
        txn = mi.fetch_tx_night()
        for d, col, note in [(tw, t1, ""), (txd, t2, "日盤 08:45~13:45"), (txn, t3, "夜盤 15:00~05:00")]:
            if not d.get("valid"):
                col.warning(f"{d.get('name','?')} 尚未開盤 / 無資料"); continue
            pct = d["pct"]; color = "#22c55e" if pct >= 0 else "#ef4444"
            arrow = "▲" if pct >= 0 else "▼"
            border = d.get("color","#4f46e5")
            extra = ""
            if d.get("contract"): extra += f'<div style="font-size:0.72em;color:#9ca3af">合約：{d["contract"]}</div>'
            if d.get("volume"):   extra += f'<div style="font-size:0.72em;color:#9ca3af">量：{d["volume"]:,}</div>'
            if d.get("high"):     extra += f'<div style="font-size:0.72em;color:#9ca3af">H {d["high"]:,.0f} / L {d["low"]:,.0f}</div>'
            if note:              extra += f'<div style="font-size:0.72em;color:#6b7280">{note}</div>'
            with col:
                st.markdown(
                    f'<div style="background:#1e1e2e;border-radius:10px;padding:12px 16px;border-left:4px solid {border};">'
                    f'<div style="font-size:0.7em;color:#9ca3af">{d.get("short","")}</div>'
                    f'<div style="font-weight:600;color:#e2e8f0">{d["name"]}</div>'
                    f'<div style="font-size:1.55em;font-weight:bold;color:#fff">{d["price"]:,.2f}</div>'
                    f'<div style="color:{color};font-weight:bold">{arrow} {d["change"]:+,.2f} ({pct:+.2f}%)</div>'
                    f'{extra}</div>', unsafe_allow_html=True)

        tw_series = mi.fetch_intraday("^TWII", "1m")
        if tw_series is not None and len(tw_series) > 1:
            fig_tw = go.Figure(go.Scatter(x=tw_series.index, y=tw_series.values,
                mode="lines", line=dict(color="#f97316", width=1.5),
                fill="tozeroy", fillcolor="rgba(249,115,22,0.1)"))
            fig_tw.update_layout(template="plotly_dark", height=200,
                margin=dict(l=10,r=10,t=10,b=10), xaxis=dict(tickformat="%H:%M"),
                showlegend=False)
            st.plotly_chart(fig_tw, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

        if txd.get("valid") and tw.get("valid"):
            spread = txd["price"] - tw["price"]
            sc_color = "#22c55e" if spread >= 0 else "#ef4444"
            st.markdown(f'台指期 vs 現貨：<span style="color:{sc_color}"><b>{spread:+.0f} 點</b></span>', unsafe_allow_html=True)
        if txn.get("valid") and txd.get("valid"):
            ns = txn["price"] - txd["price"]
            nc = "#22c55e" if ns >= 0 else "#ef4444"
            st.markdown(f'夜盤 vs 日盤收盤：<span style="color:{nc}"><b>{ns:+.0f} 點</b></span>', unsafe_allow_html=True)

        st.caption("資料來源：Yahoo Finance / TAIFEX MIS。僅供參考，不構成投資建議。")

    _mkt()

    # ── 即時財經新聞（在大盤頁底部，每則有中文解析）─────────────────────
    st.divider()
    st.markdown("### 即時財經新聞")

    @st.cache_data(ttl=300)
    def _mkt_news():
        return nf.fetch_stock_news(max_per_ticker=2)

    col_nl, col_nr = st.columns([1, 3])
    with col_nl:
        reload_news = st.button("重新載入新聞", use_container_width=True, type="primary")
    with col_nr:
        st.caption("每 5 分鐘自動更新 · 點「重新載入新聞」可立即抓最新 · 點「中文解析」取得 AI 分析")

    if reload_news:
        _mkt_news.clear()   # 只清新聞快取，不影響股價快取
        st.rerun()

    with st.spinner("載入新聞中…"):
        news_list = _mkt_news()

    has_api = bool(nf.get_api_key())

    if not news_list:
        st.warning("新聞暫時無法載入，請點「重新載入新聞」")
    else:
        for idx, item in enumerate(news_list):
            impact   = nf.tag_news_impact(item["title"])
            color    = impact.get("color", "#374151")
            theme    = impact.get("theme", "")
            tw_list  = impact.get("tw_stocks", [])
            cache_key = f"mkt_news_zh_{idx}"
            saved_zh  = st.session_state.get(cache_key, "")

            theme_badge = (
                f'<span style="background:{color}22;color:{color};border-radius:4px;'
                f'padding:1px 8px;font-size:0.7em;font-weight:600;margin-left:6px">'
                f'{theme}</span>'
            ) if theme else ""

            tw_chips = ""
            if tw_list:
                tw_chips = (
                    '<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:4px">'
                    '<span style="color:#64748b;font-size:0.7em;align-self:center">台股 →</span>'
                    + "".join(
                        f'<span style="background:#0f172a;border:1px solid {color}55;'
                        f'color:#e2e8f0;border-radius:4px;padding:2px 7px;font-size:0.7em">{n}</span>'
                        for _, n in tw_list[:4]
                    )
                    + '</div>'
                )

            # 新聞卡片（全寬）
            st.markdown(
                f'<div style="background:#1e293b;border-radius:8px;padding:10px 14px;'
                f'border-left:3px solid {color};margin-bottom:2px">'
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
                f'<span style="color:#64748b;font-size:0.7em">🇹🇼 {item["time"]}</span>' f'&nbsp;·&nbsp;' f'<span style="color:#475569;font-size:0.7em">🇺🇸 {item.get("time_us","")}</span>'
                f'<span style="color:#475569;font-size:0.7em">{item["publisher"][:18]}</span>'
                f'{theme_badge}</div>'
                f'<div style="color:#e2e8f0;font-size:0.88em;font-weight:500">'
                f'<a href="{item["url"]}" target="_blank" style="color:#e2e8f0;text-decoration:none">'
                f'{item["title"]}</a></div>'
                f'{tw_chips}'
                + (
                    f'<div style="margin-top:8px;padding:8px 12px;background:#0f172a;'
                    f'border-radius:6px;line-height:1.7;font-size:0.85em;white-space:pre-wrap;'
                    f'color:#c7d2fe">{saved_zh}</div>'
                    if saved_zh else ""
                )
                + '</div>',
                unsafe_allow_html=True,
            )
            # 按鈕放在卡片下方全寬，容易點
            if not saved_zh:
                if st.button(f"AI 中文解析 + 股票多空判斷",
                             key=f"mkt_ai_{idx}", use_container_width=True):
                    if not has_api:
                        st.session_state[cache_key] = (
                            "⚠️ 請先設定 ANTHROPIC_API_KEY\n"
                            "Manage app → Settings → Secrets → 加入：\n"
                            "ANTHROPIC_API_KEY = \"sk-ant-...\""
                        )
                    else:
                        with st.spinner(f"Claude 分析中（約 5 秒）…"):
                            zh = nf.zh_news_analysis(item, impact)
                        st.session_state[cache_key] = zh


# ══════════════════════════════════════════════════════════════════════════
# PAGE 1: 自選股列表
# ══════════════════════════════════════════════════════════════════════════
def page_watchlist():
    st.title("自選股列表")
    st.caption("本頁股票為本次瀏覽暫存，關閉瀏覽器後恢復預設。左側可新增或移除。")

    watchlist = st.session_state.watchlist
    if not watchlist:
        st.info("尚無追蹤股票，請在左側新增。"); return

    tickers = [w["ticker"] for w in watchlist]
    with st.spinner("載入報價…"):
        prices = _batch_prices(tuple(tickers))

    col_a, col_b = st.columns([2, 1])
    with col_a:
        sort_by = st.radio("排序", ["自訂順序", "漲幅高低", "跌幅高低"], horizontal=True)
    with col_b:
        cols_n = st.select_slider("欄數", [2, 3, 4], value=2)

    alert_pct = 3.0

    items = list(watchlist)
    if sort_by == "漲幅高低":
        items.sort(key=lambda w: prices.get(w["ticker"], {}).get("pct", 0), reverse=True)
    elif sort_by == "跌幅高低":
        items.sort(key=lambda w: prices.get(w["ticker"], {}).get("pct", 0))

    alerts = []
    rows = [items[i:i+cols_n] for i in range(0, len(items), cols_n)]

    for row in rows:
        cols = st.columns(cols_n)
        for col, stock in zip(cols, row):
            ticker = stock["ticker"]
            p      = prices.get(ticker, {})
            pct    = p.get("pct", 0)   if p else 0
            price  = p.get("price", 0) if p else 0
            change = p.get("change", 0)if p else 0
            arrow  = "▲" if pct >= 0 else "▼"
            pcolor = "#4ade80" if pct >= 0 else "#f87171"
            # 台股藍框 / 美股金框
            is_tw   = ticker.endswith(".TW") or ticker.endswith(".TWO")
            bg      = "#0f1e3a" if is_tw else "#1c1200"
            border  = "#3b82f6" if is_tw else "#f59e0b"
            mkt_tag = '<span style="background:#1e3a5f;color:#93c5fd;border-radius:3px;padding:1px 5px;font-size:0.65em">台股</span>' if is_tw else \
                      '<span style="background:#3b1500;color:#fcd34d;border-radius:3px;padding:1px 5px;font-size:0.65em">美股</span>'
            themes  = sc.get_themes(ticker)
            # 最多顯示 2 個題材標籤
            theme_html = "".join(f'<span class="theme-tag">{t}</span>' for t in themes[:2])
            # 美股額外從 US_TW_IMPACT 抓題材
            if not themes and not is_tw:
                us_imp = uti.US_TW_IMPACT.get(ticker, {})
                us_theme = us_imp.get("theme", "")
                if us_theme:
                    theme_html = f'<span class="theme-tag">{us_theme.split("/")[0][:14]}</span>'
            if abs(pct) >= alert_pct and p:
                alerts.append(f"注意  **{stock['name']}**  {pct:+.2f}%")
            with col:
                st.markdown(
                    f'<div style="background:{bg};border-radius:10px;padding:12px 14px;'
                    f'border-left:4px solid {border};margin-bottom:6px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span class="stock-code">{ticker}</span>{mkt_tag}'
                    f'</div>'
                    f'<div class="stock-name">{stock["name"]}</div>'
                    f'<div class="stock-price">{price:,.2f}</div>'
                    f'<div style="color:{pcolor};font-weight:600;font-size:0.9em">'
                    f'{arrow} {change:+.2f} ({pct:+.2f}%)</div>'
                    f'<div style="margin-top:5px">{theme_html}</div>'
                    f'</div>', unsafe_allow_html=True)
                if st.button("分析", key=f"wl_{ticker}", use_container_width=True):
                    goto_detail(ticker, stock["name"])
                    st.rerun()

    if alerts:
        st.divider()
        for a in alerts:
            st.warning(a)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 2: 個股深度分析
# ══════════════════════════════════════════════════════════════════════════
def page_detail():
    st.title("個股深度分析")

    # ── 搜尋欄 ────────────────────────────────────────────────────────────
    cur_ticker = st.session_state.get("detail_ticker", "")
    all_opts   = _all_stock_opts()

    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        if all_opts:
            # 找預設選項 index
            default_idx = 0
            if cur_ticker:
                for i, opt in enumerate(all_opts):
                    if cur_ticker in opt:
                        default_idx = i
                        break
            selected_opt = st.selectbox(
                "搜尋股票", all_opts, index=default_idx,
                key="detail_select", label_visibility="collapsed",
                help="輸入名稱、代碼或數字即時篩選",
            )
        else:
            # 選單載入失敗時改用文字輸入
            selected_opt = st.text_input(
                "輸入代碼", value=cur_ticker,
                placeholder="2330.TW / NVDA / 台積電",
                key="detail_text", label_visibility="collapsed",
            )
    with col_btn:
        go_btn = st.button("查詢", use_container_width=True, type="primary")

    if go_btn and selected_opt:
        raw = selected_opt.strip()
        if "(" in raw and raw.endswith(")"):
            t, _ = option_to_ticker(raw)
        else:
            t, _ = name_to_ticker(raw) if raw else (raw, raw)
        st.session_state.detail_ticker = t.upper()
        st.rerun()

    # 從 session state 取 ticker（包含 goto_detail 導航過來的情況）
    ticker = st.session_state.get("detail_ticker", "").strip().upper()
    if not ticker:
        st.info("搜尋股票或點下方快速選股")
        examples = [
            ("2330.TW","台積電"), ("2317.TW","鴻海"), ("2454.TW","聯發科"),
            ("NVDA","輝達"),      ("AAPL","蘋果"),     ("TSLA","特斯拉"),
            ("MU","美光"),        ("SMCI","超微電腦"),  ("AMD","超微"),
        ]
        ecols = st.columns(3)
        for i, (t, n) in enumerate(examples):
            with ecols[i % 3]:
                if st.button(n, key=f"ex_{t}", use_container_width=True):
                    st.session_state.detail_ticker = t
                    st.rerun()
        return

    # ── 載入資料 ─────────────────────────────────────────────────────────
    with st.spinner(f"載入 {ticker} 資料中…"):
        info = fetch_stock_info(ticker)
        df_h = fetch_history(ticker, period="6mo")

    if not info.get("valid") or df_h is None:
        st.error(f"找不到 {ticker} 的資料，請確認代碼正確（台股要加 .TW，如 2330.TW）")
        return

    # ── K 線粒度選擇器 ───────────────────────────────────────────────────
    kline_keys = list(KLINE_PRESETS.keys())
    default_ki = kline_keys.index("6個月") if "6個月" in kline_keys else 0
    sel_kline  = st.selectbox(
        "K 線粒度 / 區間",
        kline_keys,
        index=default_ki,
        format_func=lambda k: KLINE_PRESETS[k]["label"],
        key=f"kline_sel_{ticker}",
        label_visibility="collapsed",
    )

    import datetime as _dt
    custom_start = custom_end = None
    if sel_kline == "自訂":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            custom_start = st.date_input("起始日",
                value=_dt.date.today() - _dt.timedelta(days=365),
                max_value=_dt.date.today() - _dt.timedelta(days=2))
        with col_d2:
            custom_end = st.date_input("結束日",
                value=_dt.date.today(), max_value=_dt.date.today())

    with st.spinner("載入K線資料…"):
        df_h = fetch_kline(ticker, sel_kline, custom_start, custom_end)
    if df_h is None or df_h.empty:
        # 降級到 6mo 日K
        df_h = fetch_history(ticker, period="6mo")

    if not info.get("valid") or df_h is None or df_h.empty:
        st.error(f"找不到 {ticker} 的資料"); return

    df = compute_all(df_h)
    sigs = get_signals(df)
    mom  = _momentum_score(ticker)
    themes = sc.get_themes(ticker)
    name = info.get("name", ticker)

    is_tw = ticker.endswith(".TW") or ticker.endswith(".TWO")
    bg_card = "#0f1e3a" if is_tw else "#1c1200"
    border  = "#3b82f6" if is_tw else "#f59e0b"

    # ── 主要報價頭部 ──────────────────────────────────────────────────────
    pct   = info["change_pct"]
    color = "#4ade80" if pct >= 0 else "#f87171"
    arrow = "▲" if pct >= 0 else "▼"
    mkt_label = "台股" if is_tw else "美股"
    mkt_color = "#3b82f6" if is_tw else "#f59e0b"

    st.markdown(f"""
    <div style="background:{bg_card};border-radius:12px;padding:16px 20px;
                margin-bottom:10px;border-left:5px solid {border};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <span style="background:{mkt_color};color:#fff;border-radius:4px;
                       padding:2px 8px;font-size:0.7em;font-weight:600">{mkt_label}</span>
          <span style="color:#94a3b8;font-size:0.8em;margin-left:8px">{ticker}</span>
          <div style="font-size:1.4em;font-weight:700;color:#f1f5f9;margin-top:4px">{name}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:2.2em;font-weight:800;color:#ffffff;line-height:1.1">{info['price']:,.2f}</div>
          <div style="color:{color};font-weight:700;font-size:1.05em">
            {arrow} {info['change']:+.2f} &nbsp; ({pct:+.2f}%)</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 題材標籤 ─────────────────────────────────────────────────────────
    if themes:
        t_html = "".join(f'<span class="theme-tag">{t}</span>' for t in themes)
        st.markdown(f'<div style="margin-bottom:10px">{t_html}</div>', unsafe_allow_html=True)

    # ── 今日關鍵數字（最重要的參考數據）─────────────────────────────────
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    hi52  = df["High"].max()
    lo52  = df["Low"].min()
    vol_avg20 = df["Volume"].tail(20).mean()
    vol_today = last["Volume"]
    vol_ratio = vol_today / vol_avg20 if vol_avg20 else 0

    rsi_val = last.get("rsi")
    rsi_color = "#f87171" if (rsi_val and rsi_val > 70) else "#4ade80" if (rsi_val and rsi_val < 30) else "#94a3b8"

    # 趨勢強弱
    mc = mom["color"]
    ml = mom["label"]

    m1, m2, m3, m4 = st.columns(4)
    def _metric(col, label, value, note="", value_color="#ffffff"):
        with col:
            st.markdown(
                f'<div style="background:#1e293b;border-radius:8px;padding:10px 12px;margin-bottom:8px;">'
                f'<div style="font-size:0.72em;color:#64748b;font-weight:600">{label}</div>'
                f'<div style="font-size:1.2em;font-weight:700;color:{value_color}">{value}</div>'
                f'<div style="font-size:0.72em;color:#475569">{note}</div>'
                f'</div>', unsafe_allow_html=True)

    _metric(m1, "今日開盤", f"{last['Open']:,.2f}")
    _metric(m2, "今日最高", f"{last['High']:,.2f}", f"區間最高 {hi52:,.2f}")
    _metric(m3, "今日最低", f"{last['Low']:,.2f}", f"區間最低 {lo52:,.2f}")
    _metric(m4, "今日成交量", f"{int(vol_today/1000):,}K",
            f"均量比 {vol_ratio:.1f}x",
            "#4ade80" if vol_ratio > 1.5 else "#94a3b8")

    m5, m6, m7, m8 = st.columns(4)
    _metric(m5, "RSI (14日)", f"{rsi_val:.1f}" if rsi_val else "—",
            "超買>70 超賣<30", rsi_color)
    _metric(m6, "MA20 均線",
            f"{last['ma20']:,.2f}" if last.get('ma20') else "—",
            f"{'站上' if last['Close'] > (last.get('ma20') or 0) else '跌破'} MA20",
            "#4ade80" if last['Close'] > (last.get('ma20') or 0) else "#f87171")
    _metric(m7, "趨勢強弱", ml,
            "  ".join(mom["reasons"][:2]) if mom["reasons"] else "",
            mc)
    _metric(m8, "距52週高",
            f"{(info['price']/hi52-1)*100:+.1f}%",
            f"高點 {hi52:,.2f}",
            "#f87171" if (info['price']/hi52 < 0.8) else "#4ade80")

    # ── Tabs within detail ────────────────────────────────────────────────
    dtab1, dtab2, dtab3, dtab4 = st.tabs(["📊 技術分析", "💰 籌碼法人", "🌳 供應鏈", "🤖 AI 分析"])

    # ── Technical Analysis Tab ─────────────────────────────────────────────
    with dtab1:
        # Momentum badge
        mc  = mom["color"]
        st.markdown(
            f'<div style="display:inline-block;background:{mc}22;border:1px solid {mc};'
            f'border-radius:6px;padding:4px 12px;margin-bottom:8px;">'
            f'<span style="color:{mc};font-weight:bold">趨勢強弱：{mom["label"]} ({mom["score"]:+d}分)</span>'
            f'</div>', unsafe_allow_html=True)

        if mom["reasons"]:
            st.caption("  ·  ".join(mom["reasons"]))

        rsi_ob, rsi_os = 70, 30
        rsi_val = sigs.get("rsi")
        if rsi_val:
            if rsi_val >= rsi_ob:
                st.warning(f"RSI={rsi_val} 超買區（>{rsi_ob}）")
            elif rsi_val <= rsi_os:
                st.info(f"RSI={rsi_val} 超賣區（<{rsi_os}）")
        for sig in sigs.get("signals", []):
            st.info(f"📌 {sig}")

        # Candlestick
        show_vol = st.checkbox("顯示成交量", value=True, key="detail_vol")
        row_h  = [0.55, 0.2, 0.25] if show_vol else [0.65, 0.35]
        nr     = 3 if show_vol else 2
        titles = ["價格走勢", "成交量", "RSI"] if show_vol else ["價格走勢", "RSI"]
        fig = make_subplots(rows=nr, cols=1, shared_xaxes=True,
                            row_heights=row_h, subplot_titles=titles, vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="K線",
            increasing_line_color="#22c55e", decreasing_line_color="#ef4444"), row=1, col=1)
        for n, ck in [(5,"ma5"),(20,"ma20"),(60,"ma60")]:
            if ck in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df[ck], name=f"MA{n}",
                    line=dict(color=INDICATOR_COLORS[ck], width=1.2)), row=1, col=1)
        if "bb_upper" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], name="布林上軌",
                line=dict(color="#9B59B6", width=1, dash="dot")), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], name="布林下軌",
                line=dict(color="#9B59B6", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(155,89,182,0.06)"), row=1, col=1)
        if show_vol:
            vc = ["#22c55e" if c>=o else "#ef4444" for c,o in zip(df["Close"],df["Open"])]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vc, opacity=0.7, name="量"), row=2, col=1)
        rr = 3 if show_vol else 2
        if "rsi" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                line=dict(color="#f59e0b", width=1.5)), row=rr, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", opacity=0.4, row=rr, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", opacity=0.4, row=rr, col=1)
        kline_label = KLINE_PRESETS.get(sel_kline, {}).get("label", "")
        fig.update_layout(
            template="plotly_dark", height=650, showlegend=True,
            legend=dict(
                orientation="h", y=1.02, x=1, xanchor="right",
                itemclick=False,         # 禁止點擊 legend 切換顯示
                itemdoubleclick=False,   # 禁止雙擊
            ),
            margin=dict(l=10,r=10,t=30,b=10),
            xaxis_rangeslider_visible=False,
            dragmode=False,              # 禁止拖曳縮放（防止圖表亂跑）
            uirevision=ticker,           # 切換股票才重置視角，其他操作保持穩定
            title=dict(text=kline_label, font=dict(size=12, color="#64748b"),
                       x=0, xanchor="left"),
        )
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False,
                                "scrollZoom": False,
                                "doubleClick": False})

        if "macd" in df.columns:
            with st.expander("MACD 指標"):
                fm = go.Figure()
                fm.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD",
                    line=dict(color="#818cf8", width=1.5)))
                fm.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal",
                    line=dict(color="#f59e0b", width=1.5)))
                hc = ["#22c55e" if v >= 0 else "#ef4444" for v in df["macd_hist"]]
                fm.add_trace(go.Bar(x=df.index, y=df["macd_hist"], marker_color=hc, opacity=0.7, name="Hist"))
                fm.update_layout(template="plotly_dark", height=220,
                    margin=dict(l=10,r=10,t=10,b=10), legend=dict(orientation="h"))
                st.plotly_chart(fm, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

    # ── Institutional Tab ──────────────────────────────────────────────────
    with dtab2:
        st.markdown("#### 💰 三大法人近期動向")
        code = ticker.replace(".TW", "").replace(".TWO", "")
        if not code.isdigit():
            st.info("外資法人資料僅支援台股（例：2330.TW）")
        else:
            with st.spinner("載入法人資料（約 5-15 秒）…"):
                inst_df = inst.get_stock_institutional(code, n_days=10)

            if inst_df.empty:
                st.warning("暫無法人資料（非交易日或 API 限制）")
            else:
                inst_df["date_str"] = pd.to_datetime(inst_df["date"]).dt.strftime("%m/%d")

                # Summary cards
                c1, c2, c3, c4 = st.columns(4)
                fi_total = inst_df["fi_net"].sum()
                it_total = inst_df["it_net"].sum()
                dl_total = inst_df["dl_net"].sum()
                tot_total = inst_df["total_net"].sum()

                def _inst_card(col, label, val, unit="張"):
                    color = "#22c55e" if val >= 0 else "#ef4444"
                    sign  = "▲" if val >= 0 else "▼"
                    val_k = val / 1000
                    with col:
                        st.markdown(
                            f'<div style="background:#1e293b;border-radius:8px;padding:10px 14px;'
                            f'border-left:3px solid {color};">'
                            f'<div style="font-size:0.75em;color:#9ca3af">{label} 累計</div>'
                            f'<div style="font-size:1.2em;font-weight:bold;color:{color}">'
                            f'{sign} {abs(val_k):.1f}K{unit}</div>'
                            f'</div>', unsafe_allow_html=True)

                _inst_card(c1, "外資", fi_total)
                _inst_card(c2, "投信", it_total)
                _inst_card(c3, "自營商", dl_total)
                _inst_card(c4, "三大法人", tot_total)

                # Consecutive days signal
                last = inst_df.iloc[-1]
                fi_sign = "建倉" if last["fi_net"] > 0 else "減倉"
                fi_days = 0
                for v in inst_df["fi_net"].values[::-1]:
                    if (fi_sign == "建倉" and v > 0) or (fi_sign == "減倉" and v < 0):
                        fi_days += 1
                    else:
                        break
                color_sig = "#22c55e" if fi_sign == "建倉" else "#ef4444"
                st.markdown(
                    f'<div style="margin:12px 0;padding:8px 14px;background:#1e293b;border-radius:8px;">'
                    f'外資最近 <b>{fi_days} 個交易日連續 '
                    f'<span style="color:{color_sig}">{fi_sign}</span></b>，'
                    f'今日外資買賣超：'
                    f'<span style="color:{color_sig}"><b>{last["fi_net"]/1000:+.1f}K 張</b></span>'
                    f'</div>', unsafe_allow_html=True)

                # Bar chart
                fig_inst = go.Figure()
                fi_colors = ["#22c55e" if v >= 0 else "#ef4444" for v in inst_df["fi_net"]]
                fig_inst.add_trace(go.Bar(x=inst_df["date_str"], y=inst_df["fi_net"]/1000,
                    name="外資", marker_color=fi_colors, opacity=0.9))
                it_colors = ["#86efac" if v >= 0 else "#fca5a5" for v in inst_df["it_net"]]
                fig_inst.add_trace(go.Bar(x=inst_df["date_str"], y=inst_df["it_net"]/1000,
                    name="投信", marker_color=it_colors, opacity=0.7))
                fig_inst.update_layout(template="plotly_dark", height=280, barmode="group",
                    margin=dict(l=10,r=10,t=10,b=10),
                    yaxis_title="千張", legend=dict(orientation="h"))
                st.plotly_chart(fig_inst, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

                # Table
                display = inst_df[["date_str","fi_net","it_net","dl_net","total_net"]].copy()
                display.columns = ["日期","外資","投信","自營商","三大法人"]
                for c in ["外資","投信","自營商","三大法人"]:
                    display[c] = display[c].apply(lambda v: f"{'▲' if v>=0 else '▼'}{abs(v)//1000:.0f}K")
                st.dataframe(display[::-1].reset_index(drop=True), use_container_width=True, hide_index=True)

    # ── Supply Chain Tab ───────────────────────────────────────────────────
    with dtab3:
        chain = sc.get_supply_chain(ticker)
        supported = sorted(sc.SUPPLY_CHAIN.keys())
        if not chain:
            st.info(f"尚未建立 **{ticker}** 的供應鏈資料")
            st.markdown("**已建立供應鏈的股票：**")
            sc_cols = st.columns(4)
            for i, t in enumerate(supported):
                with sc_cols[i % 4]:
                    n = sc.SUPPLY_CHAIN[t].get("name", t)
                    if st.button(n, key=f"sc_jump_{t}", use_container_width=True):
                        goto_detail(t, n)
        else:
            st.markdown(f"#### 🌳 {chain.get('name',ticker)} 供應鏈地圖")
            st.caption(chain.get("desc", ""))

            # ── Batch fetch all chain prices ───────────────────────────────
            _skip = {"消費者","企業","電商","貨主","開發者","企業客戶","造船廠","燃油廠",
                     "原材料","玻璃廠","塑料廠","泵浦廠商","基板廠","銅鋁材料",
                     "投資市場","小米","OPPO","vivo","安卓廠","保戶","企業金融",
                     "IMGTECH","ARMH","PANASONIC","ALB","SAMS","RIVN","LI","NIO","CRM"}
            chain_tickers = set()
            for key in ("upstream","midstream","downstream","related"):
                for t, _, _ in chain.get(key, []):
                    if t and t not in _skip and not any(k in t for k in ["廠","者","卓","牌","客","商","牌","全球"]):
                        chain_tickers.add(t)
            chain_tickers.add(ticker)

            with st.spinner("載入供應鏈即時報價…"):
                chain_prices = _batch_prices(tuple(sorted(chain_tickers)))

            # ── Plotly Flow Diagram ────────────────────────────────────────
            # ── 供應鏈流程表（橫向 5 欄，乾淨不重疊）─────────────────────
            def _node_cell(t, nm, note, border_color, chain_prices):
                p = chain_prices.get(t, {})
                if p:
                    pct = p.get("pct", 0)
                    pc  = "#4ade80" if pct >= 0 else "#f87171"
                    ar  = "▲" if pct >= 0 else "▼"
                    price_html = (
                        f'<div style="font-size:1em;font-weight:700;color:#fff">{p["price"]:,.2f}</div>'
                        f'<div style="font-size:0.75em;color:{pc}">{ar} {pct:+.2f}%</div>'
                    )
                else:
                    price_html = '<div style="font-size:0.8em;color:#475569">—</div>'
                return (
                    f'<div style="background:#1e293b;border-left:3px solid {border_color};'
                    f'border-radius:7px;padding:8px 10px;margin:3px 0;min-width:120px;">'
                    f'<div style="font-size:0.72em;color:#64748b">{t}</div>'
                    f'<div style="font-size:0.88em;font-weight:600;color:#e2e8f0">{nm}</div>'
                    f'{price_html}'
                    f'<div style="font-size:0.68em;color:#475569;margin-top:2px">{note[:28]}</div>'
                    f'</div>'
                )

            up_items  = chain.get("upstream",   [])
            mid_items = chain.get("midstream",  [])
            dn_items  = chain.get("downstream", [])
            rel_items = chain.get("related",    [])

            p_core = chain_prices.get(ticker, {})
            pct_c  = p_core.get("pct", info.get("change_pct", 0)) if p_core else info.get("change_pct", 0)
            price_c = p_core.get("price", info.get("price", 0)) if p_core else info.get("price", 0)
            pc_c  = "#4ade80" if pct_c >= 0 else "#f87171"
            ar_c  = "▲" if pct_c >= 0 else "▼"

            core_html = (
                f'<div style="background:#1e3a5f;border:2px solid #f97316;border-radius:10px;'
                f'padding:12px 14px;text-align:center;">'
                f'<div style="font-size:0.72em;color:#94a3b8">{ticker}</div>'
                f'<div style="font-size:1.1em;font-weight:700;color:#fff">{chain.get("name","")}</div>'
                f'<div style="font-size:1.4em;font-weight:800;color:#fff">{price_c:,.2f}</div>'
                f'<div style="color:{pc_c};font-weight:700">{ar_c} {pct_c:+.2f}%</div>'
                f'</div>'
            )

            # 欄位 HTML
            def _col(title, color, items):
                cells = "".join(_node_cell(t, n, note, color, chain_prices) for t, n, note in items)
                return (
                    f'<div style="flex:1;min-width:130px;">'
                    f'<div style="font-size:0.72em;font-weight:700;color:{color};'
                    f'margin-bottom:6px;text-align:center">{title}</div>'
                    f'{cells}'
                    f'</div>'
                )

            cols_html = [
                _col("上游", "#3b82f6", up_items),
                f'<div style="display:flex;align-items:center;padding:0 8px;color:#64748b;font-size:1.2em">→</div>',
                f'<div style="flex:0 0 160px"><div style="font-size:0.72em;font-weight:700;color:#f97316;margin-bottom:6px;text-align:center">本股</div>{core_html}</div>',
            ]
            if mid_items:
                cols_html += [
                    f'<div style="display:flex;align-items:center;padding:0 8px;color:#64748b;font-size:1.2em">→</div>',
                    _col("中游", "#8b5cf6", mid_items),
                ]
            cols_html += [
                f'<div style="display:flex;align-items:center;padding:0 8px;color:#64748b;font-size:1.2em">→</div>',
                _col("下游", "#10b981", dn_items),
            ]

            flow_html = (
                f'<div style="display:flex;align-items:flex-start;gap:4px;'
                f'overflow-x:auto;padding:12px;background:#0f172a;border-radius:10px;">'
                + "".join(cols_html) +
                f'</div>'
            )

            st.markdown("**供應鏈流程圖（上游 → 本股 → 下游）**")
            st.markdown(flow_html, unsafe_allow_html=True)

            if rel_items:
                st.markdown("**同業 / 相關公司**")
                rel_html = (
                    f'<div style="display:flex;flex-wrap:wrap;gap:6px;padding:8px;'
                    f'background:#0f172a;border-radius:8px;">'
                    + "".join(_node_cell(t, n, note, "#f59e0b", chain_prices) for t, n, note in rel_items) +
                    f'</div>'
                )
                st.markdown(rel_html, unsafe_allow_html=True)

            # ── Clickable card sections ────────────────────────────────────
            def _chain_cards(title, color, items, prices_dict, section_key):
                if not items:
                    return
                st.markdown(f"**{title}**")
                n_col = min(len(items), 3)
                cols  = st.columns(n_col)
                for i, (t, n, note) in enumerate(items):
                    p   = prices_dict.get(t, {})
                    has_chain = t in sc.SUPPLY_CHAIN
                    with cols[i % n_col]:
                        pct   = p.get("pct", 0) if p else 0
                        price = p.get("price", 0) if p else 0
                        chg   = p.get("change", 0) if p else 0
                        pc    = "#22c55e" if pct >= 0 else "#ef4444"
                        ar    = "▲" if pct >= 0 else "▼"
                        price_line = (f'<div style="font-size:1.05em;font-weight:bold;color:#fff">{price:,.2f}</div>'
                                      f'<div style="color:{pc};font-size:0.82em">{ar} {chg:+.2f} ({pct:+.2f}%)</div>'
                                      if p else '<div style="color:#6b7280;font-size:0.82em">— 暫無報價</div>')
                        chain_badge = '<span style="background:#312e81;color:#a5b4fc;border-radius:3px;padding:1px 5px;font-size:0.7em">🌳 有供應鏈</span>' if has_chain else ""
                        st.markdown(
                            f'<div style="background:#1e293b;border-left:3px solid {color};'
                            f'border-radius:7px;padding:8px 12px;margin-bottom:4px;">'
                            f'<div style="display:flex;justify-content:space-between;">'
                            f'<b style="color:#e2e8f0">{n}</b>'
                            f'<span style="color:#9ca3af;font-size:0.75em">{t}</span>'
                            f'</div>'
                            f'{price_line}'
                            f'<div style="color:#6b7280;font-size:0.72em;margin-top:2px">{note} {chain_badge}</div>'
                            f'</div>', unsafe_allow_html=True)
                        if sc.get_supply_chain(t) or sc.get_themes(t):
                            btn_label = "展開供應鏈" if has_chain else "分析"
                            if st.button(btn_label, key=f"chain_{section_key}_{t}_{i}",
                                         use_container_width=True):
                                goto_detail(t, n)
                                st.rerun()

            _chain_cards("⬆️ 上游 — 設備 / 材料 / 零件供應商",
                         "#3b82f6", chain.get("upstream", []), chain_prices, "up")

            st.markdown('<div style="text-align:center;font-size:1.8em;margin:4px 0">⬇️</div>',
                        unsafe_allow_html=True)

            # Core stock card
            p_self = chain_prices.get(ticker, {"price": info["price"], "change": info["change"], "pct": info["change_pct"]})
            pct_s  = p_self.get("pct", 0)
            pc_s   = "#22c55e" if pct_s >= 0 else "#ef4444"
            st.markdown(
                f'<div style="background:#1e3a5f;border:2px solid #f97316;border-radius:10px;'
                f'padding:12px 16px;margin-bottom:8px;text-align:center;">'
                f'<div style="font-size:0.8em;color:#9ca3af">{ticker}</div>'
                f'<div style="font-size:1.3em;font-weight:bold;color:#fff">{chain.get("name","")}</div>'
                f'<div style="font-size:1.6em;font-weight:bold;color:#fff">{p_self.get("price",0):,.2f}</div>'
                f'<div style="color:{pc_s};font-weight:bold">{"▲" if pct_s>=0 else "▼"} {p_self.get("change",0):+.2f} ({pct_s:+.2f}%)</div>'
                f'<div style="margin-top:4px">{"".join(f"<span class=theme-badge>{t}</span>" for t in sc.get_themes(ticker)[:4])}</div>'
                f'</div>', unsafe_allow_html=True)

            if chain.get("midstream"):
                st.markdown('<div style="text-align:center;font-size:1.8em;margin:4px 0">⬇️</div>',
                            unsafe_allow_html=True)
                _chain_cards("🔄 中游 — 封裝 / 加工 / 整合",
                             "#8b5cf6", chain.get("midstream", []), chain_prices, "mid")

            st.markdown('<div style="text-align:center;font-size:1.8em;margin:4px 0">⬇️</div>',
                        unsafe_allow_html=True)
            _chain_cards("⬇️ 下游 — 客戶 / 品牌 / 終端應用",
                         "#10b981", chain.get("downstream", []), chain_prices, "dn")

            if chain.get("related"):
                st.divider()
                _chain_cards("🔗 同業競爭 / 相關公司",
                             "#f59e0b", chain.get("related", []), chain_prices, "rel")

    # ── AI Analysis Tab ────────────────────────────────────────────────────
    with dtab4:
        st.markdown("#### 🤖 Claude AI 趨勢分析")
        if st.button("產生 AI 分析報告", type="primary", use_container_width=True):
            with st.spinner(f"Claude 分析 {name} 中…"):
                result = ai_analyst.analyze(ticker, name, info, df, sigs)
            st.markdown(f'<div class="signal-box">{result}</div>', unsafe_allow_html=True)
        else:
            st.caption("需設定 ANTHROPIC_API_KEY 環境變數")


# ══════════════════════════════════════════════════════════════════════════
# PAGE 3: 外資籌碼追蹤
# ══════════════════════════════════════════════════════════════════════════
def page_institutional():
    st.title("💰 外資籌碼追蹤")
    st.caption("資料來源：TWSE 三大法人買賣超，每日收盤後更新")

    n_days = st.radio("統計天數", [3, 5, 10, 20], index=1, horizontal=True)

    if st.button("📥 載入外資籌碼資料", type="primary", use_container_width=True):
        with st.spinner(f"抓取近 {n_days} 日三大法人資料（約 15-30 秒）…"):
            cum_df = inst.fetch_cumulative(n_days=n_days)
            st.session_state["inst_cum_df"] = cum_df
            st.session_state["inst_n_days"] = n_days

    cum_df = st.session_state.get("inst_cum_df", pd.DataFrame())
    if cum_df.empty:
        st.info("點擊上方按鈕載入資料。"); return

    st.success(f"共 {len(cum_df)} 檔股票  ·  統計近 {st.session_state.get('inst_n_days', n_days)} 個交易日")

    tab_acc, tab_dis, tab_consec, tab_all = st.tabs([
        "🟢 外資建倉排行", "🔴 外資減倉排行", "🔥 連買連賣排行", "📋 全部明細"
    ])

    def _inst_bar(df_sub, col_key, title, color_pos, color_neg, uid, top_n=20):
        d = df_sub.head(top_n).copy()
        if d.empty:
            st.info("暫無資料"); return
        vals = d[col_key] / 1000
        colors = [color_pos if v >= 0 else color_neg for v in vals]
        labels = [f"{row['name']} ({row['code']})" for _, row in d.iterrows()]
        fig = go.Figure(go.Bar(
            y=labels, x=vals, orientation="h",
            marker_color=colors, opacity=0.88,
            text=[f"{v:+.0f}K" for v in vals], textposition="outside",
        ))
        fig.update_layout(template="plotly_dark",
            height=max(300, len(d)*28), title=title,
            margin=dict(l=10, r=80, t=40, b=20),
            xaxis_title="千張（千股）",
            yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

        # 明細表
        show = d[["code","name","fi_cum","it_cum","total_cum","fi_consec"]].copy()
        show.columns = ["代碼","名稱","外資累計","投信累計","三大法人","外資連買(日)"]
        for c in ["外資累計","投信累計","三大法人"]:
            show[c] = show[c].apply(lambda v: f"{'▲' if v>=0 else '▼'} {abs(v)//1000:.0f}K")
        st.dataframe(show.reset_index(drop=True), use_container_width=True, hide_index=True)

        # 跳轉分析 — uid 確保 key 唯一
        sel = st.selectbox("選股查看分析", ["— 請選擇 —"] + labels, key=f"sel_{uid}")
        if sel != "— 請選擇 —" and st.button("查看個股深度分析", key=f"btn_{uid}"):
            code = sel.split("(")[-1].replace(")", "").strip()
            name = sel.split("(")[0].strip()
            goto_detail(code + ".TW", name)
            st.rerun()

    with tab_acc:
        st.markdown("#### 🟢 外資累計買超前 30 名（建倉 / 吸籌碼）")
        top_acc = inst.get_top_accumulation(cum_df, 30)
        _inst_bar(top_acc, "fi_cum", "外資累計買超（千張）", "#22c55e", "#ef4444", "acc")

    with tab_dis:
        st.markdown("#### 🔴 外資累計賣超前 30 名（減倉 / 出貨）")
        top_dis = inst.get_top_distribution(cum_df, 30)
        _inst_bar(top_dis.iloc[::-1].reset_index(drop=True), "fi_cum", "外資累計賣超（千張）", "#22c55e", "#ef4444", "dis")

    with tab_consec:
        st.markdown("#### 🔥 連續買超 / 賣超排行（連續天數）")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**連續買超最多天（外資）**")
            buy_consec = cum_df[cum_df["fi_consec"] > 0].nlargest(15, "fi_consec")
            if not buy_consec.empty:
                fig_bc = go.Figure(go.Bar(
                    y=buy_consec["name"], x=buy_consec["fi_consec"],
                    orientation="h", marker_color="#22c55e",
                    text=buy_consec["fi_consec"].astype(str)+"日",
                    textposition="outside",
                ))
                fig_bc.update_layout(template="plotly_dark",
                    height=max(250, len(buy_consec)*24),
                    margin=dict(l=10,r=60,t=10,b=20),
                    xaxis_title="天", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_bc, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})
        with c2:
            st.markdown("**連續賣超最多天（外資）**")
            sell_consec = cum_df[cum_df["fi_consec"] < 0].nsmallest(15, "fi_consec")
            if not sell_consec.empty:
                fig_sc = go.Figure(go.Bar(
                    y=sell_consec["name"], x=sell_consec["fi_consec"].abs(),
                    orientation="h", marker_color="#ef4444",
                    text=sell_consec["fi_consec"].abs().astype(int).astype(str)+"日",
                    textposition="outside",
                ))
                fig_sc.update_layout(template="plotly_dark",
                    height=max(250, len(sell_consec)*24),
                    margin=dict(l=10,r=60,t=10,b=20),
                    xaxis_title="天", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_sc, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

    with tab_all:
        st.markdown("#### 📋 全部股票三大法人明細")
        search = st.text_input("搜尋名稱或代碼", placeholder="台積電 / 2330")
        show_all = cum_df.copy()
        if search:
            mask = (show_all["name"].str.contains(search, na=False) |
                    show_all["code"].str.contains(search, na=False))
            show_all = show_all[mask]
        show_all = show_all[["code","name","fi_cum","it_cum","dl_cum","total_cum","fi_consec","n_days"]].copy()
        show_all.columns = ["代碼","名稱","外資累計","投信累計","自營累計","三大合計","外資連續(日)","資料天數"]
        for c in ["外資累計","投信累計","自營累計","三大合計"]:
            show_all[c] = show_all[c].apply(lambda v: f"{'▲' if v>=0 else '▼'} {abs(v)//1000:.1f}K")
        st.dataframe(show_all.reset_index(drop=True), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 4: 族群分析
# ══════════════════════════════════════════════════════════════════════════
def page_sector():
    st.title("🏭 族群分析")

    @st.cache_data(ttl=3600)
    def _all_stocks():
        return sd.fetch_all_stocks()

    all_stocks_df = _all_stocks()
    if all_stocks_df is None:
        st.error("無法取得 TWSE 族群資料"); return

    sector_list = sd.get_sector_list(all_stocks_df)

    tab_rank, tab_detail, tab_predict = st.tabs(["📊 族群排行", "🔍 成分股查詢", "🤖 AI 輪動預測"])

    # ── 共用時間區間選擇器 ────────────────────────────────────────────
    import datetime as _dt
    PERIOD_OPTS = ["當日", "當周", "這兩週", "這一個月", "這半年", "自訂"]
    period_col1, period_col2 = st.columns([3, 2])
    with period_col1:
        sel_period = st.radio("統計區間", PERIOD_OPTS, index=1, horizontal=True,
                              key="sector_period")
    custom_s = custom_e = None
    if sel_period == "自訂":
        with period_col2:
            dc1, dc2 = st.columns(2)
            with dc1:
                custom_s = st.date_input("起始", value=_dt.date.today()-_dt.timedelta(days=30),
                                          max_value=_dt.date.today(), key="sec_cs")
            with dc2:
                custom_e = st.date_input("結束", value=_dt.date.today(),
                                          max_value=_dt.date.today(), key="sec_ce")

    period_label = sd.PERIOD_MAP.get(sel_period, {}).get("label", sel_period)

    with tab_rank:
        st.markdown(f"#### 各族群漲跌排行（{period_label}）")
        col_load, col_info = st.columns([1, 3])
        with col_load:
            load_perf = st.button("載入族群績效", type="primary", use_container_width=True)
        with col_info:
            st.caption("每族群取前 5 支代表股計算平均漲跌幅（約 30-60 秒）")

        if load_perf:
            with st.spinner(f"計算各族群「{sel_period}」績效…"):
                perf_df = sd.compute_all_sector_perf(
                    all_stocks_df, top_n=5,
                    period_key=sel_period,
                    custom_start=custom_s, custom_end=custom_e,
                )
                st.session_state["sector_perf_df"]     = perf_df
                st.session_state["sector_period_label"] = period_label

        perf_df = st.session_state.get("sector_perf_df", pd.DataFrame())
        saved_label = st.session_state.get("sector_period_label", "")
        if not perf_df.empty:
            perf_sorted = perf_df.sort_values("ret_1w")
            colors = ["#22c55e" if v >= 0 else "#ef4444" for v in perf_sorted["ret_1w"]]
            fig_hm = go.Figure(go.Bar(
                y=perf_sorted["sector"], x=perf_sorted["ret_1w"],
                orientation="h", marker_color=colors,
                text=[f"{v:+.1f}%" for v in perf_sorted["ret_1w"]],
                textposition="outside",
            ))
            fig_hm.update_layout(template="plotly_dark",
                height=max(400, len(perf_sorted)*23),
                title=f"各族群漲跌幅排行（{saved_label}）",
                margin=dict(l=10, r=80, t=40, b=20),
                xaxis_title="漲跌幅 (%)")
            st.plotly_chart(fig_hm, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

            display = perf_df.copy()
            display["排名"] = range(1, len(display)+1)
            display["漲跌幅"] = display["ret_1w"].apply(
                lambda x: f"{'▲' if x>=0 else '▼'} {x:+.2f}%")
            st.dataframe(
                display[["排名","sector","漲跌幅","n_stocks"]].rename(
                    columns={"sector": "族群", "n_stocks": "樣本數"}),
                use_container_width=True, hide_index=True)

    with tab_detail:
        sel_sector = st.selectbox("選擇族群", sector_list)
        sector_stocks = sd.get_stocks_in_sector(all_stocks_df, sel_sector)
        st.markdown(f"**{sel_sector}** 共 {len(sector_stocks)} 檔  ·  統計區間：{period_label}")

        fetch_btn = st.button("查詢族群個股表現", use_container_width=True)
        with st.expander("成分股清單", expanded=False):
            st.dataframe(sector_stocks[["code","short_name","ticker"]].rename(
                columns={"code":"代碼","short_name":"名稱","ticker":"Yahoo代碼"}),
                use_container_width=True, hide_index=True)

        if fetch_btn:
            with st.spinner(f"取得「{sel_sector}」{period_label}績效…"):
                perf = sd.fetch_sector_performance(
                    sector_stocks, top_n=15,
                    period_key=sel_period,
                    custom_start=custom_s, custom_end=custom_e,
                )
            if not perf.empty:
                perf_s = perf.sort_values("ret")
                colors_s = ["#22c55e" if (v is not None and v>=0) else "#ef4444"
                            for v in perf_s["ret"]]
                fig_s = go.Figure(go.Bar(
                    y=perf_s["name"], x=perf_s["ret"],
                    orientation="h", marker_color=colors_s,
                    text=[f"{v:+.1f}%" if v else "" for v in perf_s["ret"]],
                    textposition="outside",
                ))
                fig_s.update_layout(template="plotly_dark",
                    height=max(280, len(perf_s)*28),
                    margin=dict(l=10, r=70, t=10, b=20),
                    xaxis_title=f"{period_label}漲跌%")
                st.plotly_chart(fig_s, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

                add_sel = st.multiselect("加入自選股",
                    options=perf["ticker"].tolist(),
                    format_func=lambda t: perf.loc[perf["ticker"]==t,"name"].values[0]
                               if not perf.loc[perf["ticker"]==t].empty else t)
                if st.button("加入", key="sector_add_btn"):
                    for t in add_sel:
                        n = perf.loc[perf["ticker"]==t,"name"].values
                        if not any(w["ticker"]==t for w in st.session_state.watchlist):
                            st.session_state.watchlist.append(
                                {"ticker":t,"name":n[0] if len(n) else t})
                    st.success(f"已加入 {len(add_sel)} 檔"); st.rerun()

    with tab_predict:
        st.markdown("#### 🤖 AI 族群輪動預測")
        if st.button("🔮 產生族群預測", type="primary", use_container_width=True):
            perf_ai = st.session_state.get("sector_perf_df", pd.DataFrame())
            if perf_ai.empty:
                st.warning("請先在「族群排行」載入績效資料")
            else:
                with st.spinner("Claude 分析中…"):
                    pred = sector_predictor.predict_hot_sectors(perf_ai)
                st.markdown(f'<div class="signal-box">{pred}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 5: 台美對照 & 供應鏈
# ══════════════════════════════════════════════════════════════════════════
def page_twus():
    st.title("🌐 台美對照 & 供應鏈")

    tab_map, tab_global = st.tabs(["🔄 台美族群對照", "📌 全球主題對應"])

    with tab_map:
        sector_names = [m["sector"] for m in tw_us_map.TW_US_MAP]
        sel = st.selectbox("選擇族群", sector_names, key="twus_sel")
        mapping = next(m for m in tw_us_map.TW_US_MAP if m["sector"] == sel)

        all_tickers = [t for t,_,_ in mapping["tw"]] + [t for t,_,_ in mapping["us"]]
        with st.spinner("載入即時股價…"):
            prices = _batch_prices(tuple(all_tickers))

        def _card(ticker, name, note, border):
            p = prices.get(ticker, {})
            if p:
                pct = p["pct"]; color = "#22c55e" if pct>=0 else "#ef4444"; arrow = "▲" if pct>=0 else "▼"
                price_line = (f'<div style="font-size:1.1em;font-weight:bold;color:#fff">{p["price"]:,.2f}</div>'
                              f'<div style="color:{color};font-size:0.82em">{arrow} {p["change"]:+.2f} ({pct:+.2f}%)</div>')
            else:
                price_line = '<div style="color:#6b7280;font-size:0.85em">— 暫無報價</div>'
            btn_key = f"twus_btn_{ticker}"
            return (f'<div style="background:#16213e;border-left:3px solid {border};'
                    f'padding:8px 12px;border-radius:6px;margin-bottom:6px;">'
                    f'<span style="color:#fff;font-weight:600">{name}</span> '
                    f'<span style="color:#9ca3af;font-size:0.75em">{ticker}</span>'
                    f'{price_line}'
                    f'<div style="color:#6b7280;font-size:0.72em">{note}</div>'
                    f'</div>')

        col_tw, col_us = st.columns(2)
        with col_tw:
            st.markdown("##### 🇹🇼 台灣代表股")
            st.caption(mapping["theme"])
            for t, n, note in mapping["tw"]:
                st.markdown(_card(t, n, note, mapping["color"]), unsafe_allow_html=True)
                if st.button("分析", key=f"twus_tw_{t}", help=f"分析 {n}"):
                    goto_detail(t, n)

        with col_us:
            st.markdown("##### 🇺🇸 對應美股")
            for t, n, note in mapping["us"]:
                st.markdown(_card(t, n, note, "#f59e0b"), unsafe_allow_html=True)
                if st.button("分析", key=f"twus_us_{t}", help=f"分析 {n}"):
                    goto_detail(t, n)

        if mapping.get("etf"):
            st.markdown("**相關 ETF：** " + "　".join(
                f"`{t}` {n}" + (f" `{prices[t]['price']:,.2f}`" if t in prices else "")
                for t, n in mapping["etf"]
            ))

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            us_add = st.multiselect("加入美股", [t for t,_,_ in mapping["us"]],
                format_func=lambda t: next((n for tick,n,_ in mapping["us"] if tick==t),t) +
                    (f" {prices[t]['price']:,.2f}" if t in prices else ""),
                key="twus_us_add")
        with c2:
            tw_add = st.multiselect("加入台股", [t for t,_,_ in mapping["tw"]],
                format_func=lambda t: next((n for tick,n,_ in mapping["tw"] if tick==t),t) +
                    (f" {prices[t]['price']:,.2f}" if t in prices else ""),
                key="twus_tw_add")
        if st.button("➕ 加入自選清單", use_container_width=True):
            nl = {t:n for t,n,_ in mapping["us"]+mapping["tw"]}
            added = sum(1 for t in us_add+tw_add
                        if not any(w["ticker"]==t for w in st.session_state.watchlist)
                        and st.session_state.watchlist.append({"ticker":t,"name":nl.get(t,t)}) is None)
            if added: st.success(f"加入 {added} 檔"); st.rerun()

    with tab_global:
        st.markdown("#### 全球主題 × 台股族群對應")
        rows = [{"全球主題": theme, "對應台股族群": "、".join(sd.SECTOR_NAME_MAP.get(c,c) for c in codes)}
                for theme, codes in sd.GLOBAL_THEME_MAP.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
# ── Route to page ─────────────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════════════════
# PAGE: 美股信號→台股影響
# ══════════════════════════════════════════════════════════════════════════
def page_us_signal():
    st.title("🔗 美股信號 → 台股影響")
    st.caption("追蹤美國關鍵股票漲跌，即時顯示哪些台股題材受影響")

    # ── 抓取美股觀察清單即時報價 ──────────────────────────────────────
    @st.cache_data(ttl=180)
    def _us_prices():
        return fetch_batch_prices(uti.US_WATCHLIST)

    with st.spinner("載入美股即時報價…"):
        us_prices = _us_prices()

    # ── 漲幅/跌幅排行 ─────────────────────────────────────────────────
    movers = []
    for sym in uti.US_WATCHLIST:
        p = us_prices.get(sym, {})
        if not p:
            continue
        impact = uti.US_TW_IMPACT.get(sym, {})
        movers.append({
            "sym":    sym,
            "name":   impact.get("name", sym),
            "theme":  impact.get("theme", ""),
            "price":  p["price"],
            "change": p["change"],
            "pct":    p["pct"],
            "color":  impact.get("color", "#9ca3af"),
        })

    movers.sort(key=lambda x: x["pct"], reverse=True)
    gainers = [m for m in movers if m["pct"] >= 0]
    losers  = [m for m in movers if m["pct"] < 0][::-1]

    # ── 漲跌幅總覽橫條圖（含題材標籤）──────────────────────────────────
    all_sorted = sorted(movers, key=lambda x: x["pct"])
    bar_colors = ["#22c55e" if m["pct"] >= 0 else "#ef4444" for m in all_sorted]

    # Y 軸標籤：股票名稱 + 題材縮寫
    def _short_theme(t: str) -> str:
        # 取題材第一段（斜線前）並限制長度
        return t.split("/")[0].split("（")[0][:10] if t else ""

    y_labels = [
        f"{m['name']} ({m['sym']})  ·  {_short_theme(m['theme'])}"
        for m in all_sorted
    ]
    hover_texts = [
        f"<b>{m['name']} ({m['sym']})</b><br>"
        f"題材：{m['theme']}<br>"
        f"今日：{m['price']:,.2f}  {m['pct']:+.2f}%<br>"
        f"漲跌：{m['change']:+.2f}"
        for m in all_sorted
    ]

    fig_bar = go.Figure(go.Bar(
        x=[m["pct"] for m in all_sorted],
        y=y_labels,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{m['pct']:+.2f}%" for m in all_sorted],
        textposition="outside",
        hovertext=hover_texts,
        hoverinfo="text",
    ))
    fig_bar.update_layout(
        template="plotly_dark",
        height=max(350, len(all_sorted) * 28),
        margin=dict(l=10, r=90, t=40, b=10),
        xaxis_title="漲跌幅 (%)",
        title="美股關鍵股票今日漲跌  ·  含題材分類",
        font=dict(size=12),
        dragmode=False,
        legend=dict(itemclick=False, itemdoubleclick=False),
    )
    with st.expander("美股漲跌總覽圖（含題材）", expanded=True):
        st.plotly_chart(fig_bar, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False,
                                "doubleClick": False})

    # ── 主題篩選 ──────────────────────────────────────────────────────
    st.divider()
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        theme_filter = st.selectbox(
            "依題材篩選",
            ["全部"] + list(uti.THEME_GROUPS.keys()),
            key="us_theme_filter",
        )
    with col_f2:
        sig_filter = st.radio(
            "顯示",
            ["全部", "🟢 漲幅 > 2%", "🔴 跌幅 > 2%"],
            horizontal=True,
            key="us_sig_filter",
        )

    # 套用篩選
    show_syms = set(uti.US_WATCHLIST)
    if theme_filter != "全部":
        show_syms = set(uti.THEME_GROUPS.get(theme_filter, []))
    filtered = [m for m in movers if m["sym"] in show_syms]
    if sig_filter == "🟢 漲幅 > 2%":
        filtered = [m for m in filtered if m["pct"] >= 2]
    elif sig_filter == "🔴 跌幅 > 2%":
        filtered = [m for m in filtered if m["pct"] <= -2]

    if not filtered:
        st.info("目前篩選條件無符合的美股信號。"); return

    # ── 每支美股 → 影響台股展開卡 ───────────────────────────────────
    st.divider()
    for m in sorted(filtered, key=lambda x: abs(x["pct"]), reverse=True):
        sym    = m["sym"]
        impact = uti.US_TW_IMPACT.get(sym, {})
        if not impact:
            continue
        pct    = m["pct"]
        color  = "#22c55e" if pct >= 0 else "#ef4444"
        arrow  = "▲" if pct >= 0 else "▼"
        itype  = impact.get("impact_type", "連動")
        theme  = impact.get("theme", "")
        reason = impact.get("reason", "")

        # 信號強度
        if abs(pct) >= 5:
            sig_label = "強力信號"
            sig_color = "#fbbf24"
        elif abs(pct) >= 2:
            sig_label = "中等信號"
            sig_color = "#f59e0b"
        else:
            sig_label = "輕微信號"
            sig_color = "#94a3b8"

        direction = "漲" if pct >= 0 else "跌"

        # US stock header — 更清楚的題材顯示
        st.markdown(
            f'<div style="background:#1e293b;border-radius:10px;padding:14px 16px;'
            f'border-left:5px solid {color};margin-bottom:6px;">'
            # 第一行：國旗 + 代碼 + 題材標籤 + 信號強度
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">'
            f'  <span style="color:#9ca3af;font-size:0.8em">美股</span>'
            f'  <span style="color:#ffffff;font-weight:700;font-size:1em">{sym}</span>'
            f'  <span style="background:#0f2a4a;color:#93c5fd;border-radius:4px;'
            f'    padding:2px 10px;font-size:0.78em;font-weight:600">{theme}</span>'
            f'  <span style="background:{sig_color}22;color:{sig_color};border-radius:4px;'
            f'    padding:2px 8px;font-size:0.75em;font-weight:600">{sig_label}</span>'
            f'</div>'
            # 第二行：名稱 + 價格
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'  <span style="font-size:1.15em;font-weight:700;color:#f1f5f9">{m["name"]}</span>'
            f'  <div style="text-align:right;">'
            f'    <div style="font-size:1.5em;font-weight:800;color:#fff">{m["price"]:,.2f}</div>'
            f'    <div style="color:{color};font-weight:700">{arrow} {m["change"]:+.2f} ({pct:+.2f}%)</div>'
            f'  </div>'
            f'</div>'
            # 第三行：連動類型 + 原因
            f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #374151;">'
            f'  <span style="background:#1f2937;color:#6ee7b7;border-radius:3px;'
            f'    padding:1px 7px;font-size:0.72em;font-weight:600;margin-right:6px">{itype}</span>'
            f'  <span style="color:#94a3b8;font-size:0.8em">{reason[:60]}{"..." if len(reason)>60 else ""}</span>'
            f'</div>'
            f'<div style="margin-top:4px;color:#64748b;font-size:0.76em">'
            f'  {sym} {direction}{abs(pct):.1f}%，影響以下台股題材 →'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Affected TW stocks
        tw_list = impact.get("tw_stocks", [])
        if not tw_list:
            continue

        tw_tickers = [t for t, _, _ in tw_list
                      if not any(k in t for k in ["廠","者","牌","電商","MU"])]

        @st.cache_data(ttl=300)
        def _tw_p(tup):
            return fetch_batch_prices(list(tup))

        tw_prices = _tw_p(tuple(sorted(set(tw_tickers))))

        n_col = min(len(tw_list), 3)
        cols  = st.columns(n_col)
        for i, (t, n, note) in enumerate(tw_list):
            p = tw_prices.get(t, {}) if t in tw_tickers else {}
            tp   = p.get("pct", 0) if p else 0
            tpr  = p.get("price", 0) if p else 0
            tch  = p.get("change", 0) if p else 0
            tc   = "#22c55e" if tp >= 0 else "#ef4444"
            ta   = "▲" if tp >= 0 else "▼"
            has_sc = t in sc.SUPPLY_CHAIN
            sc_badge = '<span style="background:#312e81;color:#a5b4fc;border-radius:3px;padding:1px 5px;font-size:0.7em;margin-left:4px">🌳</span>' if has_sc else ""
            with cols[i % n_col]:
                st.markdown(
                    f'<div style="background:#0f172a;border-left:3px solid {impact.get("color","#4f46e5")};'
                    f'border-radius:6px;padding:8px 10px;margin-bottom:4px;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="color:#e2e8f0;font-size:0.92em">{n}{sc_badge}</b>'
                    f'<span style="color:#9ca3af;font-size:0.72em">{t}</span>'
                    f'</div>'
                    + (f'<div style="font-size:1.05em;font-weight:bold;color:#fff">{tpr:,.2f}</div>'
                       f'<div style="color:{tc};font-size:0.82em">{ta} {tch:+.2f} ({tp:+.2f}%)</div>'
                       if p else
                       '<div style="color:#6b7280;font-size:0.82em">— 暫無報價</div>') +
                    f'<div style="color:#6b7280;font-size:0.72em;margin-top:2px">{note}</div>'
                    f'</div>', unsafe_allow_html=True)
                if st.button("分析", key=f"uss_{sym}_{t}_{i}", help=f"分析 {n}",
                             use_container_width=True):
                    goto_detail(t, n)

        st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)

    st.caption("⚠️ 題材連動為市場慣性參考，不代表必然漲跌。投資有風險，請審慎評估。")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: 景氣循環 & 明日台股
# ══════════════════════════════════════════════════════════════════════════
def page_cycle():
    st.title("景氣循環 & 明日台股")
    st.caption("根據美股夜盤 + 總體指標，推算目前景氣位置與明日可能強勢標的")

    @st.cache_data(ttl=900)
    def _load_indicators():
        result = {}
        for sym in cyc.INDICATORS:
            result[sym] = cyc.fetch_indicator(sym)
        return result

    @st.cache_data(ttl=300)
    def _load_us_prices():
        from data_fetcher import fetch_batch_prices
        return fetch_batch_prices(uti.US_WATCHLIST)

    with st.spinner("載入景氣指標與美股資料…"):
        indicators = _load_indicators()
        us_prices  = _load_us_prices()

    cycle_result = cyc.compute_cycle_score(indicators)
    phase        = cycle_result["phase"]
    phase_info   = cycle_result["phase_info"]
    score        = cycle_result["score"]
    reasons      = cycle_result["reasons"]

    # ── 景氣循環大標題卡 ────────────────────────────────────────────
    pcolor = phase_info["color"]
    st.markdown(
        f'<div style="background:#1e293b;border-radius:14px;padding:20px 24px;'
        f'border-left:6px solid {pcolor};margin-bottom:16px;">'
        f'<div style="font-size:0.8em;color:#94a3b8;font-weight:600">目前景氣循環階段</div>'
        f'<div style="font-size:2.2em;font-weight:800;color:{pcolor}">'
        f'{phase_info["emoji"]} {phase}</div>'
        f'<div style="font-size:1em;color:#cbd5e1;margin-top:4px">{phase_info["desc"]}</div>'
        f'<div style="margin-top:10px;">'
        f'<div style="background:#0f172a;border-radius:8px;height:14px;overflow:hidden;">'
        f'<div style="background:{pcolor};height:100%;width:{min(100,max(0,(score+10)/20*100)):.0f}%"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.7em;color:#64748b;margin-top:3px">'
        f'<span>衰退期</span><span>高峰期</span><span>復甦期</span><span>擴張期</span>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    # ── 判斷依據 ────────────────────────────────────────────────────
    with st.expander("判斷依據（點開看各指標說明）", expanded=False):
        for r in reasons:
            arrow = "▲" if any(k in r for k in ["多頭","正斜","平靜","樂觀","強勢","偏弱","站穩"]) else "▼"
            color = "#4ade80" if "多頭" in r or "平靜" in r or "樂觀" in r or "偏弱" in r else "#f87171"
            st.markdown(f'<span style="color:{color}">{arrow}</span> {r}', unsafe_allow_html=True)

    # ── 關鍵指標面板 ────────────────────────────────────────────────
    st.markdown("#### 關鍵總體指標")
    ind_list = [
        ("^GSPC",    "S&P 500"),
        ("^VIX",     "VIX 恐慌指數"),
        ("^TNX",     "10Y 美債利率"),
        ("^IRX",     "3M 美債利率"),
        ("DX-Y.NYB", "美元指數 DXY"),
        ("GC=F",     "黃金"),
        ("CL=F",     "原油 WTI"),
        ("^TWII",    "台股加權指數"),
    ]
    rows = [ind_list[i:i+4] for i in range(0, len(ind_list), 4)]
    for row in rows:
        cols = st.columns(4)
        for col, (sym, label) in zip(cols, row):
            d = indicators.get(sym, {})
            if not d:
                col.markdown(f'<div style="background:#1e293b;border-radius:8px;padding:10px;margin-bottom:6px"><div style="font-size:0.72em;color:#64748b">{label}</div><div style="color:#475569">—</div></div>', unsafe_allow_html=True)
                continue
            pct = d.get("pct", 0)
            pc  = "#4ade80" if pct >= 0 else "#f87171"
            ar  = "▲" if pct >= 0 else "▼"
            vs200 = d.get("vs_ma200_pct")
            vs200_txt = f"vs MA200: {vs200:+.1f}%" if vs200 else ""
            with col:
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:8px;padding:10px 12px;margin-bottom:6px;">'
                    f'<div style="font-size:0.72em;color:#64748b">{label}</div>'
                    f'<div style="font-size:1.15em;font-weight:700;color:#fff">{d["price"]:,.2f}</div>'
                    f'<div style="color:{pc};font-size:0.82em">{ar} {pct:+.2f}%</div>'
                    f'<div style="color:#475569;font-size:0.7em">{vs200_txt}</div>'
                    f'</div>', unsafe_allow_html=True)

    # ── 殖利率曲線 ──────────────────────────────────────────────────
    y10 = indicators.get("^TNX", {}).get("price")
    y3m = indicators.get("^IRX", {}).get("price")
    if y10 and y3m:
        spread = y10 - y3m
        sc = "#4ade80" if spread > 0 else "#ef4444"
        invert_warn = '<span style="color:#ef4444">⚠️ 殖利率倒掛，衰退風險</span>' if spread < 0 else ""
        st.markdown(
            f'<div style="background:#1e293b;border-radius:8px;padding:10px 14px;margin-bottom:12px;">'
            f'<span style="color:#94a3b8;font-size:0.85em">殖利率曲線（10Y - 3M）：</span>'
            f'<span style="color:{sc};font-weight:700;font-size:1.1em"> {spread:+.2f}%</span>'
            f'  {invert_warn}'
            f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── 這個階段該買什麼 ─────────────────────────────────────────
    st.markdown(f"#### {phase_info['emoji']} {phase} — 建議關注族群")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**台股優先關注**")
        for s in phase_info["tw_buy"]:
            st.markdown(f'<span class="theme-tag" style="background:#14532d;color:#86efac;font-size:0.9em">▲ {s}</span>', unsafe_allow_html=True)
        st.markdown("<br>**台股暫時迴避**", unsafe_allow_html=True)
        for s in phase_info["tw_avoid"]:
            st.markdown(f'<span class="theme-tag" style="background:#450a0a;color:#fca5a5;font-size:0.9em">▼ {s}</span>', unsafe_allow_html=True)
    with c2:
        st.markdown("**美股優先關注**")
        for s in phase_info["us_buy"]:
            p = us_prices.get(s, {})
            pstr = f'  `{p["price"]:,.2f}`  `{p["pct"]:+.1f}%`' if p else ""
            st.markdown(f'<span class="theme-tag" style="background:#14532d;color:#86efac;font-size:0.9em">▲ {s}{pstr}</span>', unsafe_allow_html=True)
        st.markdown("<br>**美股暫時迴避**", unsafe_allow_html=True)
        for s in phase_info["us_avoid"]:
            st.markdown(f'<span class="theme-tag" style="background:#450a0a;color:#fca5a5;font-size:0.9em">▼ {s}</span>', unsafe_allow_html=True)

    st.divider()

    # ════ 明日台股關注排行（整合所有美股信號，加權計算）══════════════════
    st.markdown("#### 明日台股關注排行")
    st.caption("整合今日所有美股漲跌 → 依關聯強度排名，被多個美股信號指向的台股排名更高")

    watchlist_tw = cyc.tomorrow_tw_watchlist(us_prices, max_stocks=12)

    if not watchlist_tw:
        st.info("目前美股無顯著信號（漲跌 < 1%），明日無特定強勢標的")
    else:
        # 批次取台股即時報價
        wl_tickers = tuple(c["ticker"] for c in watchlist_tw
                           if c["ticker"].endswith(".TW"))
        with st.spinner("載入台股報價…"):
            wl_prices = _batch_prices(wl_tickers)

        for rank, cand in enumerate(watchlist_tw, 1):
            tk     = cand["ticker"]
            name   = cand["name"]
            direct = cand["direction"]
            score  = cand["score"]
            sigs   = cand["signals"]
            themes = cand["themes"]
            p      = wl_prices.get(tk, {})

            dir_color = "#22c55e" if direct == "多" else "#ef4444"
            dir_arrow = "▲" if direct == "多" else "▼"
            price_str = f'{p["price"]:,.2f}  {("▲" if p["pct"]>=0 else "▼")}{p["pct"]:+.1f}%' if p else "—"
            theme_tags = "".join(
                f'<span style="background:#1e3a5f;color:#93c5fd;border-radius:3px;'
                f'padding:1px 6px;font-size:0.7em;margin-right:3px">{t}</span>'
                for t in themes[:2]
            )
            # 信號來源摘要
            sig_summary = "  ".join(
                f'{s["us_name"]}({s["us_sym"]}) {s["us_pct"]:+.1f}%'
                for s in sorted(sigs, key=lambda x: abs(x["us_pct"]), reverse=True)[:3]
            )

            col_r, col_main, col_btn = st.columns([0.4, 5, 1.2])
            with col_r:
                # 排名徽章
                badge_bg = "#1e3a5f" if rank <= 3 else "#1e293b"
                badge_c  = "#fbbf24" if rank <= 3 else "#64748b"
                st.markdown(
                    f'<div style="background:{badge_bg};border-radius:8px;text-align:center;'
                    f'padding:14px 6px;font-size:1.3em;font-weight:800;color:{badge_c}">'
                    f'#{rank}</div>', unsafe_allow_html=True)
            with col_main:
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:10px;padding:10px 14px;'
                    f'border-left:4px solid {dir_color};">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                    f'<div>'
                    f'  <span style="color:#94a3b8;font-size:0.72em">{tk}</span>'
                    f'  {theme_tags}'
                    f'  <div style="font-size:1em;font-weight:700;color:#f1f5f9">{name}</div>'
                    f'</div>'
                    f'<div style="text-align:right">'
                    f'  <div style="font-size:1.1em;font-weight:700;color:#fff">{price_str}</div>'
                    f'  <div style="color:{dir_color};font-size:0.85em;font-weight:600">'
                    f'    {dir_arrow} 關聯分數 {score:.1f}</div>'
                    f'</div></div>'
                    f'<div style="margin-top:6px;color:#64748b;font-size:0.75em">'
                    f'  信號來源：{sig_summary}</div>'
                    f'</div>', unsafe_allow_html=True)
            with col_btn:
                if st.button("深度分析", key=f"wl_cy_{tk}", use_container_width=True):
                    goto_detail(tk, name)

    # ── 即時新聞 + 中文解析 + 產業影響 ──────────────────────────────────
    st.divider()
    st.subheader("即時財經新聞  ×  中文解析  ×  產業影響")

    # ── 即時新聞 + 產業影響分析 ──────────────────────────────────────
    st.divider()
    st.subheader("即時財經新聞  ×  產業影響")
    st.caption("自動標記每則新聞對台股哪些族群和標的的影響")

    @st.cache_data(ttl=300)
    def _load_news():
        return nf.fetch_stock_news(max_per_ticker=2)

    col_n1, col_n2 = st.columns([1, 3])
    with col_n1:
        run_news = st.button("載入最新新聞", use_container_width=True, type="primary")
    with col_n2:
        st.caption("每 30 分鐘自動快取一次，點按鈕強制重新抓取")

    if run_news:
        st.cache_data.clear()

    with st.spinner("抓取新聞中（約 1-2 秒）…"):
        news_list = _load_news()

    if not news_list:
        st.warning("新聞暫時無法載入，請稍後再試。")
    else:
        # 是否有 API Key（決定是否顯示「AI 解析」按鈕）
        has_api = bool(nf.get_api_key())
        if has_api:
            st.caption("點「AI 解析」讓 Claude 用中文分析每則新聞的台股影響（需 ANTHROPIC_API_KEY）")
        else:
            st.caption("設定 ANTHROPIC_API_KEY 可啟用每則新聞 AI 中文解析功能")

        for idx, news_item in enumerate(news_list):
            impact  = nf.tag_news_impact(news_item["title"])
            color   = impact.get("color", "#475569")
            theme   = impact.get("theme", "")
            tw_list = impact.get("tw_stocks", [])
            border  = color if theme else "#374151"

            tw_chips = ""
            if tw_list:
                tw_chips = (
                    f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:5px">'
                    f'<span style="color:#64748b;font-size:0.7em;align-self:center">台股影響 →</span>'
                    + "".join(
                        f'<span style="background:#0f172a;border:1px solid {color}55;'
                        f'color:#e2e8f0;border-radius:4px;padding:2px 8px;font-size:0.7em">{n}</span>'
                        for _, n in tw_list[:4]
                    )
                    + '</div>'
                )
            theme_badge = (
                f'<span style="background:{color}22;color:{color};border-radius:4px;'
                f'padding:1px 8px;font-size:0.7em;font-weight:600">{theme}</span>'
            ) if theme else ""

            # 取出 session 中已存的 AI 解析
            cache_key = f"news_zh_{idx}"
            saved_zh  = st.session_state.get(cache_key, "")

            col_news, col_ai = st.columns([6, 1])
            with col_news:
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:8px;padding:10px 14px;'
                    f'border-left:3px solid {border};">'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
                    f'  <span style="color:#64748b;font-size:0.7em">🇹🇼 {news_item["time"]}</span>' f'&nbsp;·&nbsp;' f'  <span style="color:#475569;font-size:0.7em">🇺🇸 {news_item.get("time_us","")}</span>'
                    f'  <span style="color:#475569;font-size:0.7em">{news_item["publisher"][:18]}</span>'
                    f'  {theme_badge}'
                    f'</div>'
                    f'<div style="color:#e2e8f0;font-size:0.88em;font-weight:500">'
                    f'  <a href="{news_item["url"]}" target="_blank" '
                    f'     style="color:#e2e8f0;text-decoration:none">{news_item["title"]}</a>'
                    f'</div>'
                    f'{tw_chips}'
                    + (
                        f'<div style="margin-top:8px;padding:8px 12px;background:#0f172a;'
                        f'border-radius:6px;color:#c7d2fe;font-size:0.85em;'
                        f'line-height:1.7;white-space:pre-wrap">'
                        f'{saved_zh}</div>'
                        if saved_zh else ""
                    )
                    + '</div>',
                    unsafe_allow_html=True,
                )
            if not saved_zh:
                with col_ai:
                    if st.button("AI 解析", key=f"news_ai_{idx}", use_container_width=True):
                        if not has_api:
                            st.session_state[cache_key] = "⚠️ 需設定 ANTHROPIC_API_KEY"
                        else:
                            with st.spinner("分析中…"):
                                zh = nf.zh_news_analysis(news_item, impact)
                            st.session_state[cache_key] = zh

    st.caption("⚠️ 景氣循環判斷為輔助參考，不構成投資建議。")


# ── Route to page ─────────────────────────────────────────════════════════
p = st.session_state.page
if p == "景氣循環 & 明日台股":
    page_cycle()
elif p == "即時大盤":
    page_market()
elif p == "自選股列表":
    page_watchlist()
elif p == "個股深度分析":
    page_detail()
elif p == "外資籌碼追蹤":
    page_institutional()
elif p == "美股信號 → 台股影響":
    page_us_signal()
elif p == "族群分析":
    page_sector()
elif p == "台美對照 & 供應鏈":
    page_twus()

st.divider()
st.caption("⚠️ 本系統僅供技術分析參考，不構成任何投資建議。資料來源：Yahoo Finance / TWSE / TAIFEX。")

# ── 手機底部導覽列（桌機版隱藏）────────────────────────────────────
_cur = st.session_state.page
_nav_items = [
    ("即時大盤",        "📡", "即時大盤"),
    ("自選股列表",      "⭐", "自選股"),
    ("個股深度分析",    "🔬", "個股"),
    ("外資籌碼追蹤",    "💰", "外資"),
    ("美股信號 → 台股影響", "🔗", "美股"),
    ("族群分析",        "🏭", "族群"),
]
_nav_html = '<nav id="mobile-nav">'
for _page, _icon, _label in _nav_items:
    _active = 'active' if _cur == _page else ''
    _nav_html += (
        f'<a class="{_active}" onclick="window.parent.document.querySelector'
        f'(\'[data-testid=\"stRadio\"] input[value=\"{_page}\"]\')?.click()">'
        f'<span class="icon">{_icon}</span>{_label}</a>'
    )
_nav_html += '</nav>'
st.markdown(_nav_html, unsafe_allow_html=True)
