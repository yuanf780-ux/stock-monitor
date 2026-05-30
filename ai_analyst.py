import os
import anthropic
import pandas as pd

def _get_api_key():
    # 優先從環境變數取，再嘗試 Streamlit secrets
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def _build_prompt(ticker: str, name: str, info: dict, df: pd.DataFrame, signals: dict) -> str:
    recent = df.tail(20)[["Close", "Volume", "ma5", "ma20", "ma60", "rsi", "macd", "macd_signal"]].round(2)
    price     = info.get("price", "N/A")
    change    = info.get("change", 0)
    change_pct = info.get("change_pct", 0)
    signal_text = "\n".join(signals.get("signals", [])) or "無明顯交叉信號"

    return f"""你是一位專業的股票技術分析師，請根據以下數據對股票進行趨勢分析。

股票：{name}（{ticker}）
當前價格：{price}
今日漲跌：{change:+.2f}（{change_pct:+.2f}%）

技術信號：
{signal_text}

最近 20 日數據（收盤/成交量/MA5/MA20/MA60/RSI/MACD/Signal）：
{recent.to_string()}

請用繁體中文回覆，分析以下三點（每點 2-3 句，語氣專業且簡潔）：
1. **短線趨勢**（近 5 日走勢方向）
2. **中線判斷**（MA 均線排列與技術指標綜合）
3. **操作建議**（謹慎提示，並說明主要風險）

注意：此為技術分析參考，非投資建議，請用戶自行判斷。"""


def analyze(ticker: str, name: str, info: dict, df: pd.DataFrame, signals: dict) -> str:
    api_key = _get_api_key()
    if not api_key:
        return "請設定 ANTHROPIC_API_KEY 以啟用 AI 分析（環境變數或 Streamlit secrets）。"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(ticker, name, info, df, signals)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except anthropic.AuthenticationError:
        return "❌ ANTHROPIC_API_KEY 無效，請重新確認。"
    except Exception as e:
        if "credit" in str(e).lower() or "balance" in str(e).lower():
            return "💳 Anthropic 額度不足，請到 https://console.anthropic.com/settings/billing 充值（最低 $5）後再試。"
        return f"❌ AI 分析失敗：{e}"
