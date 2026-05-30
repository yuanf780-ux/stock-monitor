import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

from config import DEFAULT_TW_STOCKS, DEFAULT_US_STOCKS, ALERT_DEFAULTS, INDICATOR_COLORS
from data_fetcher import (fetch_stock_info, fetch_history, fetch_batch_prices,
                          name_to_ticker, get_all_stock_options, option_to_ticker)
from indicators import compute_all, get_signals
import ai_analyst
import sector_data as sd
import sector_predictor
import market_index as mi
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
    initial_sidebar_state="auto",
)

st.markdown("""<style>
.stock-name  { font-size:1em; font-weight:600; color:#f1f5f9; }
.stock-code  { font-size:.72em; color:#94a3b8; }
.stock-price { font-size:1.4em; font-weight:700; color:#fff; }
.theme-tag {
    display:inline-block; background:#1e3a5f; color:#93c5fd;
    border-radius:4px; padding:2px 7px; font-size:.72em; margin:2px 2px 2px 0; font-weight:500;
}
.signal-box {
    background:#1a1a2e; border:1px solid #374151; border-radius:8px;
    padding:14px 16px; margin-top:8px; white-space:pre-wrap;
    color:#e2e8f0; font-size:.9em; line-height:1.6;
}
.kpi-card {
    background:#1e293b; border-radius:10px; padding:12px 14px; margin-bottom:8px;
}
/* ── 手機版 ── */
@media(max-width:768px){
    .block-container{padding:.4rem .4rem 5rem!important;max-width:100%!important}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:6px!important}
    [data-testid="column"]{min-width:calc(50% - 6px)!important;flex:0 0 calc(50% - 6px)!important}
    .stock-price{font-size:1.2em!important}
    button{min-height:44px!important;touch-action:manipulation}
    h1{font-size:1.5em!important}h2{font-size:1.2em!important}
}
#mobile-nav{display:none}
@media(max-width:768px){
    #mobile-nav{display:flex!important;position:fixed;bottom:0;left:0;right:0;
        background:#1e293b;border-top:1px solid #334155;z-index:9999}
    #mobile-nav a{flex:1;display:flex;flex-direction:column;align-items:center;
        justify-content:center;padding:8px 2px;color:#94a3b8;text-decoration:none;
        font-size:.62em;font-weight:500;min-height:56px}
    #mobile-nav a span.icon{font-size:1.4em;line-height:1;margin-bottom:2px}
    #mobile-nav a.active{color:#3b82f6}
}
</style>""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────
if "watchlist"      not in st.session_state:
    st.session_state.watchlist = [*DEFAULT_TW_STOCKS, *DEFAULT_US_STOCKS]
if "page"           not in st.session_state:
    st.session_state.page = "今日晨報"
if "detail_ticker"  not in st.session_state:
    st.session_state.detail_ticker = ""
if "pending_remove" not in st.session_state:
    st.session_state.pending_remove = []


def goto_detail(ticker: str, name: str = ""):
    st.session_state.detail_ticker = ticker
    st.session_state.page = "個股研究"


# ══════════════════════════════════════════════════════════════════════════
# ── Sidebar ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 股票監控")
    st.divider()

    _pages = ["今日晨報", "景氣 & 波段", "個股研究", "自選清單", "外資籌碼"]
    page = st.radio("功能", _pages,
        index=_pages.index(st.session_state.page)
              if st.session_state.page in _pages else 0,
        key="nav_radio")
    st.session_state.page = page

    st.divider()
    st.markdown("**快速查個股**")

    @st.cache_data(ttl=3600)
    def _opts():
        return get_all_stock_options()

    sel = st.selectbox("輸入名稱或代碼", ["— 請輸入 —"] + _opts(),
                       index=0, key="sidebar_sel", label_visibility="collapsed")
    if sel and sel != "— 請輸入 —":
        t, n = option_to_ticker(sel)
        if st.button("查看分析", use_container_width=True, type="primary"):
            st.session_state.detail_ticker = t
            st.session_state.page = "個股研究"
            st.rerun()

    st.divider()
    st.markdown("**自選股**")
    with st.form("add_watch", clear_on_submit=True):
        new_sel = st.selectbox("新增", ["— 搜尋股票 —"] + _opts(),
                               key="add_sel", label_visibility="collapsed")
        if st.form_submit_button("加入"):
            if new_sel and new_sel != "— 搜尋股票 —":
                t, n = option_to_ticker(new_sel)
                if not any(w["ticker"] == t for w in st.session_state.watchlist):
                    st.session_state.watchlist.append({"ticker": t, "name": n})
                    st.success(f"已加入 {n}"); st.rerun()

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
        if st.button("確認刪除", use_container_width=True, type="secondary"):
            st.session_state.watchlist = [
                w for w in st.session_state.watchlist
                if w["ticker"] not in st.session_state.pending_remove
            ]
            st.session_state.pending_remove = []; st.rerun()

    st.divider()
    st.caption(f"更新：{pd.Timestamp.now().strftime('%H:%M')}")
    if st.button("刷新資料", use_container_width=True):
        st.cache_data.clear(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# ── Shared helpers ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def _batch_prices(tickers_tuple):
    return fetch_batch_prices(list(tickers_tuple))


def _price_chip(ticker, prices, show_name=""):
    p = prices.get(ticker, {})
    if not p:
        return f'<span style="color:#475569">{show_name or ticker} —</span>'
    pct = p["pct"]; color = "#4ade80" if pct >= 0 else "#f87171"
    ar  = "▲" if pct >= 0 else "▼"
    label = show_name or ticker
    return (f'<span style="color:#e2e8f0;font-weight:600">{label}</span>'
            f' <span style="color:{color};font-size:.82em">{ar}{pct:+.1f}%</span>')


def _sparkline(series, height=60):
    if series is None or len(series) < 2: return None
    base = float(series.iloc[0])
    pct  = (series / base - 1) * 100
    up   = float(pct.iloc[-1]) >= 0
    lc, fc = ("#22c55e", "rgba(34,197,94,.12)") if up else ("#ef4444","rgba(239,68,68,.12)")
    fig = go.Figure(go.Scatter(y=pct.values, mode="lines",
        line=dict(color=lc, width=1.8), fill="tozeroy", fillcolor=fc))
    fig.update_layout(height=height, margin=dict(l=0,r=0,t=0,b=0),
        xaxis_visible=False, yaxis_visible=False, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


# ══════════════════════════════════════════════════════════════════════════
# PAGE 1 — 今日晨報
# 邏輯：美股昨夜 → 新聞分析 → 景氣快覽 → 明日台股標的
# ══════════════════════════════════════════════════════════════════════════
def page_briefing():
    st.title("今日晨報")
    st.caption("美股動向 → AI 新聞解讀 → 景氣位置 → 明日台股可能標的")

    # ── 載入所有資料 ─────────────────────────────────────────────────
    @st.cache_data(ttl=300)
    def _us_p():   return fetch_batch_prices(uti.US_WATCHLIST)
    @st.cache_data(ttl=900)
    def _inds():
        r = {}
        for sym in cyc.INDICATORS: r[sym] = cyc.fetch_indicator(sym)
        return r
    @st.cache_data(ttl=1800)          # 30 分鐘 cache，減少 API 呼叫
    def _news():   return nf.fetch_stock_news(max_per_ticker=2)  # 每股只取 2 則

    # 市場資料優先顯示，新聞延遲載入
    with st.spinner("載入市場資料…"):
        us_prices  = _us_p()
        indicators = _inds()

    # 新聞在背景 cache 中取，不阻塞主流程
    news_list = _news()

    cycle_result = cyc.compute_cycle_score(indicators)
    phase        = cycle_result["phase"]
    phase_info   = cycle_result["phase_info"]
    morning      = cyc.morning_signal(us_prices)

    # ════ 第一排：景氣速覽 + 美股三指數 ════════════════════════════════
    st.markdown("### 市場快覽")
    c0, c1, c2, c3 = st.columns([1.4, 1, 1, 1])

    # 景氣指示燈
    with c0:
        pcolor = phase_info["color"]
        st.markdown(
            f'<div class="kpi-card" style="border-left:5px solid {pcolor};">'
            f'<div style="font-size:.72em;color:#64748b">景氣循環</div>'
            f'<div style="font-size:1.4em;font-weight:800;color:{pcolor}">'
            f'{phase_info["emoji"]} {phase}</div>'
            f'<div style="font-size:.78em;color:#94a3b8">{phase_info["desc"][:28]}…</div>'
            f'</div>', unsafe_allow_html=True)

    for sym, col in zip(["^GSPC","^DJI","^IXIC"], [c1, c2, c3]):
        d = mi.fetch_us_index(sym)
        if not d.get("valid"): continue
        pct = d["pct"]; color = "#4ade80" if pct >= 0 else "#f87171"
        ar  = "▲" if pct >= 0 else "▼"
        with col:
            st.markdown(
                f'<div class="kpi-card" style="border-left:3px solid {d["color"]};">'
                f'<div style="font-size:.72em;color:#64748b">{d["short"]}</div>'
                f'<div style="font-size:1.1em;font-weight:700;color:#fff">{d["price"]:,.2f}</div>'
                f'<div style="color:{color};font-size:.85em">{ar} {pct:+.2f}%</div>'
                f'</div>', unsafe_allow_html=True)
            s = mi.fetch_intraday(sym)
            fig = _sparkline(s, 50)
            if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    st.divider()

    # ════ 第二排：AI 晨報 + 新聞列表 ═══════════════════════════════════
    col_ai, col_news = st.columns([3, 2])

    with col_ai:
        st.markdown("### AI 今日關鍵訊號")
        run_brief = st.button("產生 AI 晨報分析", type="primary", use_container_width=True)
        if run_brief:
            with st.spinner("Claude 分析新聞與市場走勢…"):
                analysis = nf.ai_news_briefing(news_list, morning, phase)
            st.session_state["ai_brief"] = analysis

        saved = st.session_state.get("ai_brief", "")
        if saved:
            st.markdown(f'<div class="signal-box">{saved}</div>', unsafe_allow_html=True)
        else:
            # 沒有 AI 就顯示美股信號摘要
            if morning:
                for sig in morning[:4]:
                    pct = sig["pct"]; color = "#22c55e" if pct > 0 else "#ef4444"
                    arrow = "▲" if pct > 0 else "▼"
                    st.markdown(
                        f'<div style="background:#1e293b;border-left:3px solid {color};'
                        f'border-radius:6px;padding:8px 12px;margin-bottom:6px;">'
                        f'<span style="color:#e2e8f0;font-weight:600">{sig["name"]}</span>'
                        f' <span style="color:{color}">{arrow}{abs(pct):.1f}%</span>'
                        f' <span style="background:#1e3a5f;color:#93c5fd;border-radius:3px;'
                        f'padding:1px 6px;font-size:.72em;margin-left:4px">'
                        f'{sig["theme"].split("/")[0][:10]}</span><br>'
                        f'<span style="color:#64748b;font-size:.78em">{sig["reason"][:55]}…</span>'
                        f'</div>', unsafe_allow_html=True)
            else:
                st.info("按「產生 AI 晨報分析」取得今日重點（需設定 ANTHROPIC_API_KEY）")

    with col_news:
        st.markdown("### 今日財經新聞")
        if news_list:
            for n in news_list[:8]:
                sym_badge = f'<span style="background:#1e3a5f;color:#93c5fd;border-radius:3px;padding:1px 5px;font-size:.68em">{n["ticker"]}</span>'
                st.markdown(
                    f'{sym_badge} <span style="color:#64748b;font-size:.72em">{n["time"]}</span><br>'
                    f'<a href="{n["url"]}" target="_blank" style="color:#e2e8f0;font-size:.85em;'
                    f'text-decoration:none">{n["title"][:60]}{"…" if len(n["title"])>60 else ""}</a>',
                    unsafe_allow_html=True)
                st.markdown('<hr style="border-color:#1e293b;margin:5px 0">', unsafe_allow_html=True)
        else:
            st.info("新聞載入中…")

    st.divider()

    # ════ 第三排：明日台股可能標的 ═════════════════════════════════════
    st.markdown("### 明日台股可能強勢標的")
    st.caption("根據美股今日漲跌幅 >±1.5%，推算台股供應鏈 / 同業連動標的")

    if not morning:
        st.info("目前美股無顯著信號（>±1.5%），請稍後再查。")
    else:
        # 收集所有台股 ticker 批次取價
        all_tw = []
        for sig in morning[:6]:
            all_tw.extend(t for t, _, _ in sig["tw_stocks"]
                          if not any(k in t for k in ["廠","牌","PANASONIC"]))
        tw_prices = _batch_prices(tuple(sorted(set(all_tw))))

        for sig in morning[:6]:
            pct   = sig["pct"]
            color = "#22c55e" if pct > 0 else "#ef4444"
            arrow = "▲" if pct > 0 else "▼"
            intensity = "強" if abs(pct) >= 5 else "中" if abs(pct) >= 2 else "弱"

            with st.expander(
                f'{sig["name"]} ({sig["sym"]})  {arrow}{abs(pct):.1f}%  '
                f'【{sig["theme"].split("/")[0][:12]}】  信號強度：{intensity}',
                expanded=(abs(pct) >= 3)):

                st.caption(sig["reason"])
                tw_list = sig["tw_stocks"]
                if tw_list:
                    cols = st.columns(min(len(tw_list), 3))
                    for i, (t, n, note) in enumerate(tw_list[:6]):
                        p = tw_prices.get(t, {})
                        pstr = (f'{p["price"]:,.2f}  {"▲" if p["pct"]>=0 else "▼"}{p["pct"]:+.1f}%'
                                if p else "—")
                        tc = "#4ade80" if p.get("pct", 0) >= 0 else "#f87171"
                        with cols[i % 3]:
                            st.markdown(
                                f'<div style="background:#0f172a;border-left:3px solid {color};'
                                f'border-radius:6px;padding:7px 10px;margin-bottom:4px;">'
                                f'<div style="font-size:.7em;color:#475569">{t}</div>'
                                f'<div style="font-weight:600;color:#e2e8f0">{n}</div>'
                                f'<div style="color:{tc};font-size:.82em">{pstr}</div>'
                                f'<div style="color:#475569;font-size:.68em">{note[:22]}</div>'
                                f'</div>', unsafe_allow_html=True)
                            if st.button("分析", key=f"br_{t}_{i}", use_container_width=True):
                                goto_detail(t, n); st.rerun()

    st.caption("⚠️ 以上為技術分析輔助，不構成投資建議。")


# ══════════════════════════════════════════════════════════════════════════
# PAGE 2 — 景氣 & 波段
# ══════════════════════════════════════════════════════════════════════════
def page_cycle():
    st.title("景氣循環 & 波段方向")
    st.caption("判斷目前在哪個循環，決定做短波段還是長線持有，以及選哪些族群")

    @st.cache_data(ttl=900)
    def _inds():
        r = {}
        for sym in cyc.INDICATORS: r[sym] = cyc.fetch_indicator(sym)
        return r
    @st.cache_data(ttl=300)
    def _us_p():   return fetch_batch_prices(uti.US_WATCHLIST)

    with st.spinner("載入指標…"):
        indicators = _inds()
        us_prices  = _us_p()

    cr    = cyc.compute_cycle_score(indicators)
    phase = cr["phase"]; info = cr["phase_info"]; score = cr["score"]

    # ── 循環儀錶板 ────────────────────────────────────────────────────
    pcolor = info["color"]
    gauge_pct = min(100, max(0, (score + 10) / 20 * 100))

    st.markdown(
        f'<div style="background:#1e293b;border-radius:14px;padding:20px 24px;'
        f'border-left:6px solid {pcolor};margin-bottom:16px;">'
        f'<div style="font-size:.8em;color:#94a3b8;font-weight:600">目前景氣循環 · 綜合評分 {score:+d}/10</div>'
        f'<div style="font-size:2.2em;font-weight:800;color:{pcolor}">{info["emoji"]} {phase}</div>'
        f'<div style="color:#cbd5e1;margin-top:4px">{info["desc"]}</div>'
        f'<div style="margin-top:12px;background:#0f172a;border-radius:8px;height:16px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#ef4444,#f59e0b,#22c55e,#3b82f6);'
        f'height:100%;width:100%;position:relative">'
        f'<div style="position:absolute;top:0;left:{gauge_pct:.0f}%;transform:translateX(-50%);'
        f'background:#fff;width:3px;height:100%"></div>'
        f'</div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:.7em;color:#475569;margin-top:3px">'
        f'<span>衰退</span><span>高峰</span><span>復甦</span><span>擴張</span></div>'
        f'</div>', unsafe_allow_html=True)

    # 判斷依據
    with st.expander("判斷依據（共 7 個指標）"):
        for r in cr["reasons"]:
            pos = any(k in r for k in ["多頭","正斜","平靜","樂觀","強","站穩","看好","偏弱黃金"])
            c = "#4ade80" if pos else "#f87171"
            st.markdown(f'<span style="color:{c}">{"▲" if pos else "▼"}</span> {r}',
                        unsafe_allow_html=True)

    st.divider()

    # ── 關鍵指標 ──────────────────────────────────────────────────────
    st.markdown("#### 總體指標儀表板")
    ind_def = [("^GSPC","S&P 500"),("^VIX","VIX"),("^TNX","10Y利率"),("^IRX","3M利率"),
               ("DX-Y.NYB","美元DXY"),("GC=F","黃金"),("CL=F","原油"),("^TWII","台股")]
    rows = [ind_def[i:i+4] for i in range(0,len(ind_def),4)]
    for row in rows:
        cols = st.columns(4)
        for col, (sym, label) in zip(cols, row):
            d = indicators.get(sym, {})
            if not d:
                with col: st.markdown(f'<div class="kpi-card"><div style="color:#475569">{label} —</div></div>', unsafe_allow_html=True)
                continue
            pct = d.get("pct",0); pc = "#4ade80" if pct>=0 else "#f87171"
            vs200 = d.get("vs_ma200_pct")
            with col:
                vs200_html = f'<div style="font-size:.68em;color:#475569">vs MA200: {vs200}%</div>' if vs200 else ""
                st.markdown(
                    f'<div class="kpi-card">'
                    f'<div style="font-size:.7em;color:#64748b">{label}</div>'
                    f'<div style="font-size:1.1em;font-weight:700;color:#fff">{d["price"]:,.2f}</div>'
                    f'<div style="color:{pc};font-size:.82em">{"▲" if pct>=0 else "▼"} {pct:+.2f}%</div>'
                    f'{vs200_html}'
                    f'</div>', unsafe_allow_html=True)

    # 殖利率曲線
    y10 = indicators.get("^TNX",{}).get("price")
    y3m = indicators.get("^IRX",{}).get("price")
    if y10 and y3m:
        spread = y10 - y3m
        sc2 = "#4ade80" if spread > 0 else "#ef4444"
        warn = " ⚠️ 殖利率倒掛，歷史上衰退前兆" if spread < 0 else " ✓ 正常曲線"
        st.markdown(
            f'<div class="kpi-card" style="border-left:3px solid {sc2}">'
            f'<span style="color:#94a3b8">10Y - 3M 殖利率曲線：</span>'
            f'<span style="color:{sc2};font-weight:700"> {spread:+.2f}%</span>'
            f'<span style="color:{sc2};font-size:.8em">{warn}</span>'
            f'</div>', unsafe_allow_html=True)

    st.divider()

    # ── 這個階段的操作策略 ─────────────────────────────────────────
    st.markdown(f"#### {info['emoji']} {phase} — 你現在的操作方向")

    strategies = {
        "復甦期": {
            "short": "短波段：買技術面突破的半導體、AI Server 族群，跌深反彈優先",
            "long":  "長線：分批建倉台積電、聯發科、輝達等成長股，等景氣確認上行",
            "risk":  "注意：尚在底部，波動大，控制倉位不超過 50%",
        },
        "擴張期": {
            "short": "短波段：追強勢族群（AI、半導體、航運），突破高點加碼",
            "long":  "長線：持有高成長股，不輕易停利，追蹤外資持續買超的股票",
            "risk":  "注意：過熱跡象出現時（VIX 極低、估值過高）提前減碼",
        },
        "高峰期": {
            "short": "短波段：做空弱勢股或高估值科技股，操作要快進快出",
            "long":  "長線：逐步轉換至防禦型（金融、食品、醫療），降低整體倉位",
            "risk":  "注意：隨時準備應對大幅回調，現金比例提升至 30-50%",
        },
        "衰退期": {
            "short": "短波段：做多防禦型反彈，或等待超跌反彈機會（需快速出場）",
            "long":  "長線：等待真正底部確認（VIX 見頂回落+外資回補），才重新建倉",
            "risk":  "注意：不要接飛刀，等出現連續 3 天外資回補再入場",
        },
    }
    strat = strategies.get(phase, {})
    for label, key, color in [("短波段操作","short","#3b82f6"),
                                ("長線策略","long","#22c55e"),
                                ("風險提示","risk","#f59e0b")]:
        st.markdown(
            f'<div class="kpi-card" style="border-left:3px solid {color};margin-bottom:6px">'
            f'<div style="font-size:.72em;color:{color};font-weight:600">{label}</div>'
            f'<div style="color:#e2e8f0;font-size:.9em">{strat.get(key,"—")}</div>'
            f'</div>', unsafe_allow_html=True)

    st.divider()

    # 優先族群
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**現在優先關注（台股）**")
        for s in info["tw_buy"]:
            st.markdown(f'<span class="theme-tag" style="background:#14532d;color:#86efac;font-size:.88em">▲ {s}</span>', unsafe_allow_html=True)
        st.markdown("  \n**暫時迴避**")
        for s in info["tw_avoid"]:
            st.markdown(f'<span class="theme-tag" style="background:#450a0a;color:#fca5a5;font-size:.88em">▼ {s}</span>', unsafe_allow_html=True)
    with c2:
        st.markdown("**現在優先關注（美股）**")
        for s in info["us_buy"]:
            p = us_prices.get(s, {})
            pstr = f' {p["price"]:,.0f} {("▲" if p["pct"]>=0 else "▼")}{p["pct"]:+.1f}%' if p else ""
            st.markdown(f'<span class="theme-tag" style="background:#14532d;color:#86efac;font-size:.88em">▲ {s}{pstr}</span>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 3 — 個股研究
# ══════════════════════════════════════════════════════════════════════════
def page_detail():
    st.title("個股研究")

    # ── 搜尋 ─────────────────────────────────────────────────────────
    @st.cache_data(ttl=3600)
    def _detail_opts(): return get_all_stock_options()

    all_opts = _detail_opts()
    cur = st.session_state.get("detail_ticker", "")
    default_idx = 0
    if cur:
        for i, opt in enumerate(all_opts):
            if cur in opt: default_idx = i; break

    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        selected_opt = st.selectbox("股票搜尋", all_opts, index=default_idx,
            key="detail_select", label_visibility="collapsed",
            help="輸入中文名稱、英文代碼或股票代號，即時篩選")
    with col_btn:
        if st.button("查詢", use_container_width=True, type="primary"):
            t, _ = option_to_ticker(selected_opt)
            st.session_state.detail_ticker = t
            st.rerun()

    ticker = st.session_state.get("detail_ticker", "").strip().upper()
    if not ticker:
        st.info("在上方選股後按「查詢」")
        ecols = st.columns(3)
        for i, (t, n) in enumerate([("2330.TW","台積電"),("NVDA","輝達"),("MU","美光"),
                                      ("2317.TW","鴻海"),("AAPL","蘋果"),("AMD","超微")]):
            with ecols[i%3]:
                if st.button(n, key=f"ex_{t}", use_container_width=True):
                    st.session_state.detail_ticker = t; st.rerun()
        return

    # ── 載入股票資料 ─────────────────────────────────────────────────
    with st.spinner(f"載入 {ticker}…"):
        info = fetch_stock_info(ticker)
        df_h = fetch_history(ticker, period="6mo")

    if not info.get("valid") or df_h is None or df_h.empty:
        st.error(f"找不到 {ticker}，台股請加 .TW（如 2330.TW）"); return

    is_tw  = ticker.endswith(".TW") or ticker.endswith(".TWO")
    border = "#3b82f6" if is_tw else "#f59e0b"
    bg     = "#0f1e3a" if is_tw else "#1c1200"
    mkt    = "台股" if is_tw else "美股"

    # K 線區間
    import datetime as _dt
    period_opts = ["3 個月", "6 個月", "1 年", "2 年", "自訂"]
    period_map  = {"3 個月":"3mo","6 個月":"6mo","1 年":"1y","2 年":"2y"}
    period_sel  = st.radio("K 線區間", period_opts, index=1, horizontal=True)
    if period_sel == "自訂":
        dc1, dc2 = st.columns(2)
        with dc1: cs = st.date_input("起始", _dt.date.today()-_dt.timedelta(days=365))
        with dc2: ce = st.date_input("結束", _dt.date.today())
        try:
            import yfinance as yf
            df_h = yf.Ticker(ticker).history(start=str(cs), end=str(ce))
            df_h.index = pd.to_datetime(df_h.index).tz_localize(None)
        except Exception: pass
    elif period_map.get(period_sel) != "6mo":
        df_h = fetch_history(ticker, period=period_map[period_sel]) or df_h

    df   = compute_all(df_h)
    sigs = get_signals(df)
    themes = sc.get_themes(ticker)

    # ── 股票頭部 ──────────────────────────────────────────────────────
    pct  = info["change_pct"]; color = "#4ade80" if pct >= 0 else "#f87171"
    st.markdown(
        f'<div style="background:{bg};border-radius:12px;padding:16px 20px;'
        f'border-left:5px solid {border};margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div><span style="background:{border};color:#fff;border-radius:4px;'
        f'padding:2px 8px;font-size:.7em">{mkt}</span>'
        f' <span style="color:#94a3b8;font-size:.8em">{ticker}</span>'
        f'<div style="font-size:1.4em;font-weight:700;color:#f1f5f9;margin-top:4px">'
        f'{info.get("name", ticker)}</div></div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:2.2em;font-weight:800;color:#fff">{info["price"]:,.2f}</div>'
        f'<div style="color:{color};font-weight:700">{"▲" if pct>=0 else "▼"} {info["change"]:+.2f} ({pct:+.2f}%)</div>'
        f'</div></div>'
        + "".join(f'<span class="theme-tag">{t}</span>' for t in themes[:4]) +
        '</div>', unsafe_allow_html=True)

    # ── 8 個關鍵數字 ────────────────────────────────────────────────
    from indicators import _momentum_score_safe
    mom = _momentum_score_safe(df) if hasattr(sys.modules.get('indicators', None) or __import__('indicators'), '_momentum_score_safe') else None

    last = df.iloc[-1]
    hi52 = df["High"].max(); lo52 = df["Low"].min()
    vol_avg = df["Volume"].tail(20).mean()
    vol_today = last.get("Volume", 0)
    vol_ratio = vol_today / vol_avg if vol_avg else 0
    rsi_val = last.get("rsi")
    ma20 = last.get("ma20")

    def _kpi(col, label, val, note="", vc="#fff"):
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div style="font-size:.7em;color:#64748b">{label}</div>'
                f'<div style="font-size:1.1em;font-weight:700;color:{vc}">{val}</div>'
                f'<div style="font-size:.68em;color:#475569">{note}</div>'
                f'</div>', unsafe_allow_html=True)

    r1 = st.columns(4)
    _kpi(r1[0], "今日開盤",  f"{last['Open']:,.2f}")
    _kpi(r1[1], "今日最高",  f"{last['High']:,.2f}", f"區間高 {hi52:,.2f}")
    _kpi(r1[2], "今日最低",  f"{last['Low']:,.2f}",  f"區間低 {lo52:,.2f}")
    _kpi(r1[3], "量 vs 均量", f"{vol_ratio:.1f}x",
         f"{int(vol_today/1000):,}K",
         "#4ade80" if vol_ratio > 1.5 else "#94a3b8")

    r2 = st.columns(4)
    rsi_c = "#f87171" if (rsi_val and rsi_val>70) else "#4ade80" if (rsi_val and rsi_val<30) else "#94a3b8"
    _kpi(r2[0], "RSI 14",
         f"{rsi_val:.1f}" if rsi_val else "—",
         ">70超買 <30超賣", rsi_c)
    ma20_c = "#4ade80" if (ma20 and last["Close"]>ma20) else "#f87171"
    _kpi(r2[1], "MA20",
         f"{ma20:,.2f}" if ma20 else "—",
         f'{"站上" if (ma20 and last["Close"]>ma20) else "跌破"} MA20', ma20_c)
    hi_pct = (info["price"]/hi52-1)*100
    _kpi(r2[2], "距區間高點",
         f"{hi_pct:+.1f}%",
         f"高點 {hi52:,.2f}",
         "#f87171" if hi_pct < -20 else "#4ade80")
    macd = last.get("macd"); sig_v = last.get("macd_signal")
    macd_c = "#4ade80" if (macd and sig_v and macd > sig_v) else "#f87171"
    _kpi(r2[3], "MACD",
         "多方" if (macd and sig_v and macd > sig_v) else "空方",
         f"{macd:.3f}" if macd else "—", macd_c)

    # ── K 線圖 ────────────────────────────────────────────────────────
    dtab1, dtab2, dtab3 = st.tabs(["K 線技術分析", "法人籌碼", "供應鏈"])

    with dtab1:
        for sig in sigs.get("signals", []):
            st.info(f"📌 {sig}")

        show_vol = st.checkbox("顯示成交量", True, key="dv")
        nr = 3 if show_vol else 2
        rh = [.55,.2,.25] if show_vol else [.65,.35]
        fig = make_subplots(rows=nr,cols=1,shared_xaxes=True,
            row_heights=rh, vertical_spacing=.03,
            subplot_titles=["價格","量","RSI"][:nr])
        fig.add_trace(go.Candlestick(x=df.index,open=df["Open"],high=df["High"],
            low=df["Low"],close=df["Close"],name="K線",
            increasing_line_color="#22c55e",decreasing_line_color="#ef4444"),row=1,col=1)
        for n, ck in [(5,"ma5"),(20,"ma20"),(60,"ma60")]:
            if ck in df.columns:
                fig.add_trace(go.Scatter(x=df.index,y=df[ck],name=f"MA{n}",
                    line=dict(color=INDICATOR_COLORS[ck],width=1.2)),row=1,col=1)
        if "bb_upper" in df.columns:
            fig.add_trace(go.Scatter(x=df.index,y=df["bb_upper"],name="布林上",
                line=dict(color="#9B59B6",width=1,dash="dot")),row=1,col=1)
            fig.add_trace(go.Scatter(x=df.index,y=df["bb_lower"],name="布林下",
                line=dict(color="#9B59B6",width=1,dash="dot"),
                fill="tonexty",fillcolor="rgba(155,89,182,.06)"),row=1,col=1)
        if show_vol:
            vc2 = ["#22c55e" if c>=o else "#ef4444" for c,o in zip(df["Close"],df["Open"])]
            fig.add_trace(go.Bar(x=df.index,y=df["Volume"],marker_color=vc2,opacity=.7,name="量"),row=2,col=1)
        rr = 3 if show_vol else 2
        if "rsi" in df.columns:
            fig.add_trace(go.Scatter(x=df.index,y=df["rsi"],name="RSI",
                line=dict(color="#f59e0b",width=1.5)),row=rr,col=1)
            fig.add_hline(y=70,line_dash="dot",line_color="#ef4444",opacity=.4,row=rr,col=1)
            fig.add_hline(y=30,line_dash="dot",line_color="#22c55e",opacity=.4,row=rr,col=1)
        fig.update_layout(template="plotly_dark",height=620,showlegend=True,
            legend=dict(orientation="h",y=1.02,x=1,xanchor="right"),
            margin=dict(l=10,r=10,t=30,b=10),xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # AI 分析
        if st.button("Claude AI 個股分析", type="primary"):
            with st.spinner("分析中…"):
                r = ai_analyst.analyze(ticker, info.get("name",""), info, df, sigs)
            st.markdown(f'<div class="signal-box">{r}</div>', unsafe_allow_html=True)

    with dtab2:
        code = ticker.replace(".TW","").replace(".TWO","")
        if not code.isdigit():
            st.info("法人籌碼資料僅支援台股")
        else:
            with st.spinner("載入法人資料…"):
                inst_df = inst.get_stock_institutional(code, n_days=10)
            if inst_df.empty:
                st.warning("暫無法人資料")
            else:
                inst_df["date_str"] = pd.to_datetime(inst_df["date"]).dt.strftime("%m/%d")
                fi_total = inst_df["fi_net"].sum()
                it_total = inst_df["it_net"].sum()
                tot      = inst_df["total_net"].sum()
                c1,c2,c3 = st.columns(3)
                for col,lab,val in [(c1,"外資累計",fi_total),(c2,"投信累計",it_total),(c3,"三大法人",tot)]:
                    vc = "#4ade80" if val>=0 else "#f87171"
                    with col:
                        st.markdown(
                            f'<div class="kpi-card" style="border-left:3px solid {vc}">'
                            f'<div style="font-size:.72em;color:#64748b">{lab}</div>'
                            f'<div style="font-size:1.2em;font-weight:700;color:{vc}">'
                            f'{"▲" if val>=0 else "▼"} {abs(val)//1000:.1f}K 張</div>'
                            f'</div>', unsafe_allow_html=True)

                last_row = inst_df.iloc[-1]
                fi_days = 0
                sign = 1 if last_row["fi_net"] > 0 else -1
                for v in inst_df["fi_net"].values[::-1]:
                    if v * sign > 0: fi_days += 1
                    else: break
                action = "建倉" if sign > 0 else "減倉"
                ac = "#4ade80" if sign > 0 else "#f87171"
                st.markdown(
                    f'<div class="kpi-card" style="border-left:3px solid {ac};margin:12px 0">'
                    f'外資連續 <b style="color:{ac}">{fi_days} 日{action}</b>，'
                    f'今日 <b style="color:{ac}">{last_row["fi_net"]/1000:+.1f}K 張</b>'
                    f'</div>', unsafe_allow_html=True)

                fc = ["#4ade80" if v>=0 else "#f87171" for v in inst_df["fi_net"]]
                fig_i = go.Figure()
                fig_i.add_trace(go.Bar(x=inst_df["date_str"],y=inst_df["fi_net"]/1000,
                    name="外資",marker_color=fc,opacity=.9))
                ic = ["#86efac" if v>=0 else "#fca5a5" for v in inst_df["it_net"]]
                fig_i.add_trace(go.Bar(x=inst_df["date_str"],y=inst_df["it_net"]/1000,
                    name="投信",marker_color=ic,opacity=.7))
                fig_i.update_layout(template="plotly_dark",height=250,barmode="group",
                    margin=dict(l=10,r=10,t=10,b=10),yaxis_title="千張",
                    legend=dict(orientation="h"))
                st.plotly_chart(fig_i, use_container_width=True)

    with dtab3:
        chain = sc.get_supply_chain(ticker)
        if not chain:
            st.info(f"尚無 {ticker} 供應鏈資料。支援：台積電、鴻海、廣達、聯發科、輝達、蘋果等")
            st.markdown("**已建立供應鏈的股票：**")
            sc_cols = st.columns(4)
            for i, t2 in enumerate(sorted(sc.SUPPLY_CHAIN.keys())):
                n2 = sc.SUPPLY_CHAIN[t2].get("name", t2)
                with sc_cols[i % 4]:
                    if st.button(n2, key=f"scjump_{t2}", use_container_width=True):
                        goto_detail(t2, n2); st.rerun()
        else:
            # ── 批次取所有供應鏈股票報價 ─────────────────────────────
            _skip_kw = ["廠","牌","消費","企業","PANASONIC","ALB","NIO","小米","OPPO","vivo"]
            ct = set()
            for key in ("upstream","midstream","downstream","related"):
                for t2, _, _ in chain.get(key, []):
                    if t2 and not any(k in t2 for k in _skip_kw):
                        ct.add(t2)
            ct.add(ticker)
            with st.spinner("載入供應鏈報價…"):
                cp = _batch_prices(tuple(sorted(ct)))

            # ── Sankey 流向圖（上游→本股→中游→下游）───────────────────
            st.markdown(f"**{chain.get('name', ticker)} 供應鏈流向圖**")
            st.caption(chain.get("desc", ""))

            layer_def = [
                ("upstream",   "上游",   "#3b82f6"),
                ("core",       "本股",   "#f97316"),
                ("midstream",  "中游",   "#8b5cf6"),
                ("downstream", "下游",   "#10b981"),
            ]
            nodes, node_colors = [], []
            node_idx = {}

            def _add_node(label, color):
                if label not in node_idx:
                    node_idx[label] = len(nodes)
                    nodes.append(label)
                    node_colors.append(color)
                return node_idx[label]

            sources, targets, values, link_colors = [], [], [], []

            # 本股節點
            p_self = cp.get(ticker, {})
            core_pct = p_self.get("pct", info.get("change_pct", 0))
            core_price = p_self.get("price", info.get("price", 0))
            core_label = f'{chain.get("name","")}\n{core_price:,.0f} {"▲" if core_pct>=0 else "▼"}{abs(core_pct):.1f}%'
            core_idx = _add_node(core_label, "#f97316")

            # 上游 → 本股
            for t2, n2, _ in chain.get("upstream", []):
                if any(k in t2 for k in _skip_kw): continue
                p2 = cp.get(t2, {})
                pct2 = p2.get("pct", 0)
                lbl = f'{n2}\n{p2["price"]:,.0f} {"▲" if pct2>=0 else "▼"}{abs(pct2):.1f}%' if p2 else n2
                idx = _add_node(lbl, "#3b82f6")
                sources.append(idx); targets.append(core_idx)
                values.append(2)
                link_colors.append("rgba(59,130,246,0.25)")

            # 本股 → 中游
            for t2, n2, _ in chain.get("midstream", []):
                if any(k in t2 for k in _skip_kw): continue
                p2 = cp.get(t2, {})
                pct2 = p2.get("pct", 0)
                lbl = f'{n2}\n{p2["price"]:,.0f} {"▲" if pct2>=0 else "▼"}{abs(pct2):.1f}%' if p2 else n2
                idx = _add_node(lbl, "#8b5cf6")
                sources.append(core_idx); targets.append(idx)
                values.append(2)
                link_colors.append("rgba(139,92,246,0.25)")

            # 本股（或中游）→ 下游
            dn_source = core_idx
            for t2, n2, _ in chain.get("downstream", []):
                if any(k in t2 for k in _skip_kw + ["消費者","全球","企業"]): continue
                p2 = cp.get(t2, {})
                pct2 = p2.get("pct", 0)
                lbl = f'{n2}\n{p2["price"]:,.0f} {"▲" if pct2>=0 else "▼"}{abs(pct2):.1f}%' if p2 else n2
                idx = _add_node(lbl, "#10b981")
                sources.append(dn_source); targets.append(idx)
                values.append(2)
                link_colors.append("rgba(16,185,129,0.25)")

            if sources:
                fig_sk = go.Figure(go.Sankey(
                    arrangement="snap",
                    node=dict(
                        label=nodes, color=node_colors,
                        pad=20, thickness=20,
                        line=dict(color="#1e293b", width=1),
                    ),
                    link=dict(
                        source=sources, target=targets, value=values,
                        color=link_colors,
                    ),
                ))
                fig_sk.update_layout(
                    template="plotly_dark", height=420,
                    margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="#0f172a",
                    font=dict(size=11, color="#e2e8f0"),
                )
                st.plotly_chart(fig_sk, use_container_width=True)

            # ── 詳細卡片（可點擊）─────────────────────────────────────
            def _cnode(t2, n2, note, bc, prices):
                p2 = prices.get(t2, {})
                pl = f'{p2["price"]:,.2f} {"▲" if p2["pct"]>=0 else "▼"}{abs(p2["pct"]):.1f}%' if p2 else "—"
                pc2 = "#4ade80" if p2.get("pct", 0) >= 0 else "#f87171"
                return (f'<div style="background:#1e293b;border-left:3px solid {bc};'
                        f'border-radius:7px;padding:8px 10px;margin:3px 0">'
                        f'<div style="font-size:.7em;color:#475569">{t2}</div>'
                        f'<div style="font-weight:600;color:#e2e8f0;font-size:.88em">{n2}</div>'
                        f'<div style="color:{pc2};font-size:.82em">{pl}</div>'
                        f'<div style="font-size:.68em;color:#475569">{note[:28]}</div>'
                        f'</div>')

            def _csection(title, color, items):
                if not items: return
                st.markdown(f"**{title}**")
                cs2 = st.columns(min(len(items), 3))
                for i, (t2, n2, note) in enumerate(items):
                    with cs2[i % 3]:
                        st.markdown(_cnode(t2, n2, note, color, cp), unsafe_allow_html=True)
                        if sc.get_supply_chain(t2):
                            if st.button("展開供應鏈", key=f"sc_{t2}_{i}", use_container_width=True):
                                goto_detail(t2, n2); st.rerun()
                        elif st.button("分析", key=f"sca_{t2}_{i}", use_container_width=True):
                            goto_detail(t2, n2); st.rerun()

            st.divider()
            _csection("上游 — 設備 / 材料 / 零件", "#3b82f6", chain.get("upstream", []))
            _csection("中游 — 封裝 / 加工 / 整合", "#8b5cf6", chain.get("midstream", []))
            _csection("下游 — 客戶 / 品牌 / 終端", "#10b981", chain.get("downstream", []))
            if chain.get("related"):
                st.divider()
                _csection("同業 / 競爭 / 相關公司", "#f59e0b", chain.get("related", []))


# ══════════════════════════════════════════════════════════════════════════
# PAGE 4 — 自選清單
# ══════════════════════════════════════════════════════════════════════════
def page_watchlist():
    st.title("自選清單")
    watchlist = st.session_state.watchlist
    if not watchlist:
        st.info("左側新增股票"); return

    tickers = [w["ticker"] for w in watchlist]
    with st.spinner("載入報價…"):
        prices = _batch_prices(tuple(tickers))

    c_sort, c_cols, c_alert = st.columns([2, 1, 2])
    with c_sort:
        sort_by = st.radio("排序", ["自訂","漲幅","跌幅"], horizontal=True)
    with c_cols:
        cols_n = st.select_slider("欄數", [2,3,4], value=2)
    with c_alert:
        alert_pct = st.slider("警示 %", 1.0, 10.0, 3.0, .5)

    items = list(watchlist)
    if sort_by == "漲幅": items.sort(key=lambda w: prices.get(w["ticker"],{}).get("pct",0), reverse=True)
    elif sort_by == "跌幅": items.sort(key=lambda w: prices.get(w["ticker"],{}).get("pct",0))

    alerts = []
    for row in [items[i:i+cols_n] for i in range(0,len(items),cols_n)]:
        cols = st.columns(cols_n)
        for col, stock in zip(cols, row):
            tk = stock["ticker"]
            p  = prices.get(tk,{})
            pct = p.get("pct",0); price = p.get("price",0); chg = p.get("change",0)
            is_tw = tk.endswith(".TW") or tk.endswith(".TWO")
            bg2   = "#0f1e3a" if is_tw else "#1c1200"
            brd   = "#3b82f6" if is_tw else "#f59e0b"
            mkt_t = '<span style="background:#1e3a5f;color:#93c5fd;border-radius:3px;padding:1px 5px;font-size:.65em">台股</span>' if is_tw else \
                    '<span style="background:#3b1500;color:#fcd34d;border-radius:3px;padding:1px 5px;font-size:.65em">美股</span>'
            pc4 = "#4ade80" if pct>=0 else "#f87171"
            themes2 = sc.get_themes(tk)
            if not themes2 and not is_tw:
                ui = uti.US_TW_IMPACT.get(tk,{}).get("theme","")
                if ui: themes2 = [ui.split("/")[0][:14]]
            th_html = "".join(f'<span class="theme-tag">{t}</span>' for t in themes2[:2])
            if abs(pct)>=alert_pct and p: alerts.append(f"注意 **{stock['name']}** {pct:+.2f}%")
            with col:
                st.markdown(
                    f'<div style="background:{bg2};border-radius:10px;padding:12px 14px;'
                    f'border-left:4px solid {brd};margin-bottom:6px;">'
                    f'<div style="display:flex;justify-content:space-between">'
                    f'<span class="stock-code">{tk}</span>{mkt_t}</div>'
                    f'<div class="stock-name">{stock["name"]}</div>'
                    f'<div class="stock-price">{price:,.2f}</div>'
                    f'<div style="color:{pc4};font-weight:600;font-size:.9em">{"▲" if pct>=0 else "▼"} {chg:+.2f} ({pct:+.2f}%)</div>'
                    f'<div style="margin-top:5px">{th_html}</div>'
                    f'</div>', unsafe_allow_html=True)
                if st.button("分析", key=f"wl_{tk}", use_container_width=True):
                    goto_detail(tk, stock["name"]); st.rerun()

    if alerts:
        st.divider()
        for a in alerts: st.warning(a)


# ══════════════════════════════════════════════════════════════════════════
# PAGE 5 — 外資籌碼
# ══════════════════════════════════════════════════════════════════════════
def page_institutional():
    st.title("外資籌碼追蹤")
    st.caption("台股三大法人（外資/投信/自營商）買賣超排行，TWSE 每日更新")

    n_days = st.radio("統計天數", [3,5,10,20], index=1, horizontal=True)
    if st.button("載入籌碼資料", type="primary", use_container_width=True):
        with st.spinner(f"抓取近 {n_days} 日法人資料（約 15-30 秒）…"):
            cum_df = inst.fetch_cumulative(n_days=n_days)
            st.session_state["inst_df"] = cum_df
            st.session_state["inst_days"] = n_days

    cum_df = st.session_state.get("inst_df", pd.DataFrame())
    if cum_df.empty: st.info("點上方按鈕載入資料"); return

    st.success(f"共 {len(cum_df)} 檔  ·  近 {st.session_state.get('inst_days', n_days)} 個交易日")
    tab_acc, tab_dis, tab_consec = st.tabs(["外資建倉排行","外資減倉排行","連買連賣天數"])

    def _ibar(df_sub, col, title, uid, top_n=20):
        d = df_sub.head(top_n).copy()
        if d.empty: st.info("暫無資料"); return
        vals   = d[col]/1000
        labels = [f"{r['name']} ({r['code']})" for _,r in d.iterrows()]
        colors = ["#22c55e" if v>=0 else "#ef4444" for v in vals]
        fig = go.Figure(go.Bar(y=labels,x=vals,orientation="h",
            marker_color=colors,opacity=.88,
            text=[f"{v:+.0f}K" for v in vals],textposition="outside"))
        fig.update_layout(template="plotly_dark",height=max(300,len(d)*28),title=title,
            margin=dict(l=10,r=80,t=40,b=20),xaxis_title="千張",
            yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
        show = d[["code","name","fi_cum","it_cum","total_cum","fi_consec"]].copy()
        show.columns = ["代碼","名稱","外資累計","投信累計","三大法人","外資連買日"]
        for c in ["外資累計","投信累計","三大法人"]:
            show[c] = show[c].apply(lambda v: f"{'▲' if v>=0 else '▼'} {abs(v)//1000:.0f}K")
        st.dataframe(show.reset_index(drop=True), use_container_width=True, hide_index=True)
        sel = st.selectbox("選股查看分析", ["—"]+labels, key=f"is_{uid}")
        if sel != "—" and st.button("查看個股", key=f"ib_{uid}"):
            code2 = sel.split("(")[-1].replace(")","").strip()
            goto_detail(code2+".TW", sel.split("(")[0].strip()); st.rerun()

    with tab_acc:
        _ibar(inst.get_top_accumulation(cum_df,20), "fi_cum", "外資建倉前20名（累計買超千張）","acc")
    with tab_dis:
        top_dis = inst.get_top_distribution(cum_df,20)
        _ibar(top_dis.iloc[::-1].reset_index(drop=True), "fi_cum", "外資減倉前20名（累計賣超千張）","dis")
    with tab_consec:
        c1,c2 = st.columns(2)
        bc = cum_df[cum_df["fi_consec"]>0].nlargest(15,"fi_consec")
        sc2 = cum_df[cum_df["fi_consec"]<0].nsmallest(15,"fi_consec")
        with c1:
            st.markdown("**連續買超最多天**")
            if not bc.empty:
                fig_b = go.Figure(go.Bar(y=bc["name"],x=bc["fi_consec"],orientation="h",
                    marker_color="#22c55e",text=bc["fi_consec"].astype(str)+"日",
                    textposition="outside"))
                fig_b.update_layout(template="plotly_dark",height=max(250,len(bc)*26),
                    margin=dict(l=10,r=60,t=10,b=20),xaxis_title="天",
                    yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_b, use_container_width=True)
        with c2:
            st.markdown("**連續賣超最多天**")
            if not sc2.empty:
                fig_s2 = go.Figure(go.Bar(y=sc2["name"],x=sc2["fi_consec"].abs(),orientation="h",
                    marker_color="#ef4444",text=sc2["fi_consec"].abs().astype(int).astype(str)+"日",
                    textposition="outside"))
                fig_s2.update_layout(template="plotly_dark",height=max(250,len(sc2)*26),
                    margin=dict(l=10,r=60,t=10,b=20),xaxis_title="天",
                    yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_s2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# ── Route ─────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
p = st.session_state.page
if   p == "今日晨報":   page_briefing()
elif p == "景氣 & 波段": page_cycle()
elif p == "個股研究":   page_detail()
elif p == "自選清單":   page_watchlist()
elif p == "外資籌碼":   page_institutional()
else:                    page_briefing()

st.divider()
st.caption("⚠️ 本系統僅供技術分析輔助，不構成投資建議。資料：Yahoo Finance / TWSE / TAIFEX")

# ── 手機底部導覽 ───────────────────────────────────────────────────────────
_cur = st.session_state.page
_items = [("今日晨報","📰","晨報"),("景氣 & 波段","🔄","景氣"),
          ("個股研究","🔬","個股"),("自選清單","⭐","自選"),("外資籌碼","💰","外資")]
_nav = '<nav id="mobile-nav">'
for _pg, _ic, _lb in _items:
    _act = "active" if _cur == _pg else ""
    _nav += (f'<a class="{_act}" onclick="window.parent.document.querySelector'
             f'(\'[data-testid=\\\"stRadio\\\"] input[value=\\\"{_pg}\\\"]\')?.click()">'
             f'<span class="icon">{_ic}</span>{_lb}</a>')
_nav += '</nav>'
st.markdown(_nav, unsafe_allow_html=True)
