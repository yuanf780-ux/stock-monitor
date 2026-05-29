import os
import anthropic
import pandas as pd
from sector_data import GLOBAL_THEME_MAP, SECTOR_NAME_MAP


def _build_prediction_prompt(perf_df: pd.DataFrame) -> str:
    top5    = perf_df.head(5)[["sector", "ret_1w", "ret_1m"]].to_string(index=False)
    bottom5 = perf_df.tail(5)[["sector", "ret_1w", "ret_1m"]].to_string(index=False)
    all_rank = perf_df[["sector", "ret_1w", "ret_1m"]].to_string(index=False)

    themes = "\n".join(f"- {t}：涉及族群 {', '.join(s)}" for t, s in GLOBAL_THEME_MAP.items())

    return f"""你是一位擅長台灣股市族群輪動分析的投資策略師。
請根據以下近期各族群實際漲跌數據及全球市場主題，推算「未來 1~3 個月」最可能輪動上漲的族群。

━━━ 近期各族群績效排名 ━━━
{all_rank}

績效最佳 Top 5：
{top5}

績效最差 Bottom 5：
{bottom5}

━━━ 全球市場主題與台股族群對應 ━━━
{themes}

請以繁體中文回答，依照以下格式輸出（每點簡潔 2-3 句）：

## 🔥 最可能啟動的族群（前 3 名）
1. **[族群名稱]** — 理由：...（結合數據 + 全球趨勢）
2. **[族群名稱]** — 理由：...
3. **[族群名稱]** — 理由：...

## ⚠️ 需要觀察的族群
- 說明已強勢但可能遇到壓力的族群，以及原因

## 📌 輪動邏輯摘要
- 2-3 句說明當前市場輪動的主要驅動力

## ⚠️ 風險提示
- 1-2 句主要風險因素

注意：以上僅為技術與趨勢分析，不構成投資建議。"""


def predict_hot_sectors(perf_df: pd.DataFrame) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠️ 請設定 ANTHROPIC_API_KEY 環境變數以啟用 AI 族群預測功能。"

    if perf_df.empty:
        return "❌ 無族群績效資料，無法進行預測。"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prediction_prompt(perf_df)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except anthropic.AuthenticationError:
        return "❌ ANTHROPIC_API_KEY 無效，請重新確認。"
    except Exception as e:
        return f"❌ AI 預測失敗：{e}"
