"""誤字脱字・表現のチェックと修正。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "proofread"
TOOL_LABEL = "校正・推敲"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは出版社の校正者です。書き手の意図と個性は変えずに、"
    "誤りと読みにくさだけを直します。直した箇所は必ず理由とセットで示してください。"
)

CHECKS = {
    "誤字脱字・変換ミス": "誤字脱字、変換ミス、送り仮名の誤りを直す",
    "文法・係り受け": "主語と述語のねじれ、係り受けの不明瞭さを直す",
    "敬語の使い方": "尊敬語・謙譲語・丁寧語の誤用を直す",
    "冗長な表現": "重複表現や回りくどい言い回しを簡潔にする",
    "表記ゆれの統一": "漢字/ひらがな、送り仮名、英数字の全角半角などの表記を統一する",
    "読みやすさ": "一文が長すぎる箇所を分割し、リズムを整える",
}


def render() -> None:
    ui.page_header("🔍", "校正・推敲", "誤字脱字から言い回しまでチェックし、修正版と修正理由を出します。")
    if not ui.api_key_guard():
        return

    source = st.text_area("チェックしたい文章", height=280, placeholder="ここに文章を貼り付けてください。")
    ui.word_count(source)

    selected = st.multiselect("チェックする観点", list(CHECKS), default=list(CHECKS)[:4])
    col1, col2 = st.columns(2)
    strength = col1.radio(
        "直す強さ",
        ["最小限（明らかな誤りだけ）", "標準", "しっかり（読みやすさまで踏み込む）"],
        index=1,
    )
    style = col2.text_input("文体の指定（任意）", placeholder="例: ですます調で統一")

    run = st.button("校正する", type="primary", width="stretch")

    prompt = None
    if run:
        if not source.strip():
            st.warning("文章を入力してください。", icon="⚠️")
        elif not selected:
            st.warning("チェックする観点を1つ以上選んでください。", icon="⚠️")
        else:
            prompt = prompts.build(
                "次の文章を校正してください。出力は必ず以下の2部構成にしてください。",
                "",
                "## 修正後の文章",
                "（修正を反映した全文。そのまま使える状態で）",
                "",
                "## 修正した点",
                "（表形式で「元の表現 / 修正後 / 理由」を1行ずつ。修正がなければ「修正点なし」と書く）",
                "",
                prompts.block("対象の文章", source),
                prompts.block("チェック観点", "\n".join(f"- {CHECKS[c]}" for c in selected)),
                prompts.rules(
                    f"直す強さは「{strength}」",
                    f"文体は「{style}」に合わせる" if style.strip() else "元の文体は変えない",
                    "書き手の主張や事実関係は変えない",
                    "内容の追加や削除はしない",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        meta={"観点": ", ".join(selected), "強さ": strength},
    )
