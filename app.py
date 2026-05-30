import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

from config import DEFAULT_TW_STOCKS, DEFAULT_US_STOCKS, ALERT_DEFAULTS, INDICATOR_COLORS
from data_fetcher import fetch_stock_info, fetch_history, fetch_batch_prices, name_to_ticker
from indicators import compute_all, get_signals
import ai_analyst
import sector_data as sd
import sector_predictor
import market_index as mi
import tw_us_map
import supply_chain as sc
import institutional as inst
import us_tw_impact as uti

# ── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="股票監控系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
/* ── 台股卡片：藍色邊框 ── */
.card-tw {
    background: #0f1e3a;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
/* ── 美股卡片：金色邊框 ── */
.card-us {
    background: #1c1200;
    border-left: 4px solid #f59e0b;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
/* ── 通用卡片 ── */
.card-base {
    background: #16213e;
    border-left: 4px solid #4f46e5;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.stock-name  { font-size: 1em;   font-weight: 600; color: #f1f5f9; }
.stock-code  { font-size: 0.72em; color: #94a3b8; }
.stock-price { font-size: 1.45em; font-weight: 700; color: #ffffff; }
.stock-up    { color: #4ade80; font-weight: 600; }
.stock-dn    { color: #f87171; font-weight: 600; }
.stock-note  { font-size: 0.75em; color: #64748b; margin-top: 3px; }
.signal-box  {
    background: #1a1a2e;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 8px;
    white-space: pre-wrap;
    color: #e2e8f0;
    font-size: 0.9em;
    line-height: 1.6;
}
.theme-tag {
    display: inline-block;
    background: #1e3a5f;
    color: #93c5fd;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 0.72em;
    margin: 2px 2px 2px 0;
    font-weight: 500;
}
.section-header {
    font-size: 0.8em;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 12px 0 6px 0;
}
/* ── 手機版調整 ── */
@media (max-width: 768px) {
    .block-container { padding: 0.5rem 0.5rem !important; }
    .stock-price     { font-size: 1.2em !important; }
    .stColumn        { padding: 2px !important; }
    [data-testid="stSidebar"] { width: 240px !important; }
    .stButton button { font-size: 0.8em; padding: 6px 10px; }
}
</style>""", unsafe_allow_html=True)

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
    st.session_state.detail_name = name
    st.session_state.page = "個股深度分析"


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 股票監控系統")
    st.divider()

    _pages = [
        "即時大盤",
        "自選股列表",
        "個股深度分析",
        "外資籌碼追蹤",
        "美股信號 → 台股影響",
        "族群分析",
        "台美對照 & 供應鏈",
    ]
    page = st.radio("頁面", _pages,
        index=_pages.index(st.session_state.page)
              if st.session_state.page in _pages else 0,
        key="nav_radio")
    st.session_state.page = page

    st.divider()
    st.markdown("**快速搜尋個股**")
    with st.form("sidebar_search", clear_on_submit=True):
        search_q = st.text_input("輸入股票名稱或代碼",
                                  placeholder="台積電 / 輝達 / 2330 / NVDA",
                                  label_visibility="collapsed")
        if st.form_submit_button("搜尋分析", use_container_width=True):
            q = search_q.strip()
            if q:
                ticker_resolved, _ = name_to_ticker(q)
                st.session_state.detail_ticker = ticker_resolved
                st.session_state.page = "個股深度分析"
                st.rerun()

    st.divider()
    st.markdown("**自選股管理**")
    new_ticker = st.text_input("新增代碼", placeholder="2330.TW 或 AAPL",
                               key="add_ticker", label_visibility="collapsed")
    new_name = st.text_input("名稱（選填）", placeholder="台積電",
                             key="add_name", label_visibility="collapsed")
    if st.button("加入自選股", use_container_width=True):
        t = new_ticker.strip().upper()
        n = new_name.strip() or t
        if t and not any(w["ticker"] == t for w in st.session_state.watchlist):
            st.session_state.watchlist.append({"ticker": t, "name": n})
            st.success(f"已加入 {n}")
        elif t:
            st.warning("已在清單中")

    st.session_state.pending_remove = st.multiselect(
        "移除股票",
        options=[w["ticker"] for w in st.session_state.watchlist],
        default=[t for t in st.session_state.pending_remove
                 if any(w["ticker"] == t for w in st.session_state.watchlist)],
        format_func=lambda t: next(
            (w["name"] for w in st.session_state.watchlist if w["ticker"] == t), t),
        key="remove_ms",
    )
    if st.session_state.pending_remove:
        if st.button("🗑️ 確認刪除", use_container_width=True, type="secondary"):
            st.session_state.watchlist = [
                w for w in st.session_state.watchlist
                if w["ticker"] not in st.session_state.pending_remove
            ]
            st.session_state.pending_remove = []
            st.rerun()

    st.divider()
    st.caption(f"最後更新 {pd.Timestamp.now().strftime('%H:%M:%S')}")
    if st.button("🔄 手動刷新", use_container_width=True):
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
            st.plotly_chart(fig_cmp, use_container_width=True)

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
            st.plotly_chart(fig_tw, use_container_width=True)

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


# ══════════════════════════════════════════════════════════════════════════
# PAGE 1: 自選股列表
# ══════════════════════════════════════════════════════════════════════════
def page_watchlist():
    st.title("自選股列表")

    watchlist = st.session_state.watchlist
    if not watchlist:
        st.info("請在左側新增自選股。"); return

    tickers = [w["ticker"] for w in watchlist]
    with st.spinner("載入報價…"):
        prices = _batch_prices(tuple(tickers))

    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        sort_by = st.radio("排序", ["自訂順序", "漲幅高低", "跌幅高低"], horizontal=True)
    with col_b:
        alert_pct = st.slider("警示門檻(%)", 1.0, 10.0, 3.0, 0.5)
    with col_c:
        cols_n = st.select_slider("欄數", [2, 3, 4], value=4)

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

    # ── 搜尋欄（支援中文名稱）───────────────────────────────────────────
    with st.form("detail_search_form", clear_on_submit=False):
        col_t, col_btn = st.columns([4, 1])
        with col_t:
            ticker_input = st.text_input("輸入名稱或代碼",
                value=st.session_state.get("detail_ticker", ""),
                placeholder="台積電 / 鴻海 / 輝達 / 2330 / NVDA",
                label_visibility="collapsed")
        with col_btn:
            do_search = st.form_submit_button("查詢", use_container_width=True)

    raw_q = ticker_input.strip()
    if do_search and raw_q:
        resolved, _ = name_to_ticker(raw_q)
        st.session_state.detail_ticker = resolved
        st.rerun()

    # 用 session state 中的代碼（可能剛被 resolved）
    ticker = st.session_state.get("detail_ticker", "").strip().upper()
    if not ticker:
        st.info("輸入股票名稱或代碼後按「查詢」")
        st.markdown("**直接點選常用股票：**")
        examples = [
            ("2330.TW","台積電"), ("2317.TW","鴻海"), ("2454.TW","聯發科"),
            ("NVDA","輝達"),      ("AAPL","蘋果"),     ("TSLA","特斯拉"),
            ("MU","美光"),        ("SMCI","超微電腦"),  ("AMD","超微"),
        ]
        ecols = st.columns(3)
        for i, (t, n) in enumerate(examples):
            with ecols[i % 3]:
                if st.button(f"{n}", key=f"ex_{t}", use_container_width=True):
                    st.session_state.detail_ticker = t
                    st.rerun()
        return

    st.session_state.detail_ticker = ticker

    # ── 載入資料 ─────────────────────────────────────────────────────────
    with st.spinner(f"載入 {ticker} 資料中…"):
        info = fetch_stock_info(ticker)
        df_h = fetch_history(ticker, period="6mo")

    if not info.get("valid") or df_h is None:
        st.error(f"找不到 {ticker} 的資料，請確認代碼正確（台股要加 .TW，如 2330.TW）")
        return

    # K 線區間選擇
    period_options = ["3 個月", "6 個月", "1 年", "2 年", "自訂區間"]
    period_map     = {"3 個月": "3mo", "6 個月": "6mo", "1 年": "1y", "2 年": "2y"}
    period_label   = st.radio("K 線區間", period_options, index=1, horizontal=True)

    if period_label == "自訂區間":
        import datetime as _dt
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            custom_start = st.date_input("開始日期",
                value=_dt.date.today() - _dt.timedelta(days=365),
                max_value=_dt.date.today() - _dt.timedelta(days=2))
        with col_d2:
            custom_end = st.date_input("結束日期",
                value=_dt.date.today(),
                max_value=_dt.date.today())
        try:
            stock_obj = __import__("yfinance").Ticker(ticker)
            df_h = stock_obj.history(start=str(custom_start), end=str(custom_end))
            if not df_h.empty:
                df_h.index = __import__("pandas").to_datetime(df_h.index).tz_localize(None)
        except Exception:
            df_h = fetch_history(ticker, period="1y")
    else:
        period = period_map[period_label]
        if period != "6mo":
            df_h = fetch_history(ticker, period=period)

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
        fig.update_layout(template="plotly_dark", height=650, showlegend=True,
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
            margin=dict(l=10,r=10,t=30,b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

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
                st.plotly_chart(fm, use_container_width=True)

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
                st.plotly_chart(fig_inst, use_container_width=True)

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
                    if st.button(f"{n}\n{t}", key=f"sc_jump_{t}", use_container_width=True):
                        goto_detail(t, n); st.rerun()
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
                            btn_label = "🌳 展開供應鏈" if has_chain else "🔬 深度分析"
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
        st.plotly_chart(fig, use_container_width=True)

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
                st.plotly_chart(fig_bc, use_container_width=True)
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
                st.plotly_chart(fig_sc, use_container_width=True)

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

    with tab_rank:
        st.markdown("#### 各族群近期漲跌排行")
        col_load, col_info = st.columns([1, 3])
        with col_load:
            load_perf = st.button("📊 載入族群績效", type="primary", use_container_width=True)
        with col_info:
            st.caption("每族群取前 5 支代表股計算平均（約 30-60 秒）")

        if load_perf:
            with st.spinner("計算各族群績效…"):
                perf_df = sd.compute_all_sector_perf(all_stocks_df, top_n=5)
                st.session_state["sector_perf_df"] = perf_df

        perf_df = st.session_state.get("sector_perf_df", pd.DataFrame())
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
                height=max(400, len(perf_sorted)*22),
                title="各族群近 1 週漲跌幅排行",
                margin=dict(l=10, r=70, t=40, b=20),
                xaxis_title="漲跌幅 (%)")
            st.plotly_chart(fig_hm, use_container_width=True)

            display = perf_df.copy()
            display["排名"] = range(1, len(display)+1)
            display["近1週"] = display["ret_1w"].apply(lambda x: f"{'▲' if x>=0 else '▼'} {x:+.2f}%")
            display["近1月"] = display["ret_1m"].apply(lambda x: f"{'▲' if x>=0 else '▼'} {x:+.2f}%" if x is not None else "—")
            st.dataframe(display[["排名","sector","近1週","近1月","n_stocks"]].rename(
                columns={"sector":"族群","n_stocks":"樣本數"}),
                use_container_width=True, hide_index=True)

    with tab_detail:
        sel_sector = st.selectbox("選擇族群", sector_list)
        sector_stocks = sd.get_stocks_in_sector(all_stocks_df, sel_sector)
        st.markdown(f"**{sel_sector}** 共 {len(sector_stocks)} 檔")

        fetch_btn = st.button("📈 查詢族群近期表現", use_container_width=True)
        with st.expander(f"成分股清單", expanded=True):
            st.dataframe(sector_stocks[["code","short_name","ticker"]].rename(
                columns={"code":"代碼","short_name":"名稱","ticker":"Yahoo代碼"}),
                use_container_width=True, hide_index=True)

        if fetch_btn:
            with st.spinner("取得族群績效…"):
                perf = sd.fetch_sector_performance(sector_stocks, top_n=15)
            if not perf.empty:
                perf_s = perf.sort_values("ret_1w")
                colors_s = ["#22c55e" if (v is not None and v>=0) else "#ef4444" for v in perf_s["ret_1w"]]
                fig_s = go.Figure(go.Bar(
                    y=perf_s["name"], x=perf_s["ret_1w"],
                    orientation="h", marker_color=colors_s,
                    text=[f"{v:+.1f}%" if v else "" for v in perf_s["ret_1w"]],
                    textposition="outside",
                ))
                fig_s.update_layout(template="plotly_dark",
                    height=max(280, len(perf_s)*26),
                    margin=dict(l=10, r=60, t=10, b=20),
                    xaxis_title="近1週漲跌%")
                st.plotly_chart(fig_s, use_container_width=True)

                add_sel = st.multiselect("加入自選股", options=perf["ticker"].tolist(),
                    format_func=lambda t: perf.loc[perf["ticker"]==t,"name"].values[0] if not perf.loc[perf["ticker"]==t].empty else t)
                if st.button("➕ 加入", key="sector_add_btn"):
                    for t in add_sel:
                        n = perf.loc[perf["ticker"]==t,"name"].values
                        if not any(w["ticker"]==t for w in st.session_state.watchlist):
                            st.session_state.watchlist.append({"ticker":t,"name":n[0] if len(n) else t})
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
                if st.button("🔬", key=f"twus_tw_{t}", help=f"分析 {n}"):
                    goto_detail(t, n); st.rerun()

        with col_us:
            st.markdown("##### 🇺🇸 對應美股")
            for t, n, note in mapping["us"]:
                st.markdown(_card(t, n, note, "#f59e0b"), unsafe_allow_html=True)
                if st.button("🔬", key=f"twus_us_{t}", help=f"分析 {n}"):
                    goto_detail(t, n); st.rerun()

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
    )
    with st.expander("美股漲跌總覽圖（含題材）", expanded=True):
        st.plotly_chart(fig_bar, use_container_width=True)

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
                if st.button("🔬", key=f"uss_{sym}_{t}_{i}", help=f"分析 {n}",
                             use_container_width=True):
                    goto_detail(t, n); st.rerun()

        st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)

    st.caption("⚠️ 題材連動為市場慣性參考，不代表必然漲跌。投資有風險，請審慎評估。")


# ── Route to page ─────────────────────────────────────────════════════════
p = st.session_state.page
if p == "即時大盤":
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
