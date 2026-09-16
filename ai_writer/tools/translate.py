"""翻訳とニュアンス調整。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "translate"
TOOL_LABEL = "翻訳"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは実務翻訳者です。直訳ではなく、その言語の話者が自然だと感じる表現に置き換えます。"
    "固有名詞・数値・単位は正確に保ち、原文にない情報は足しません。"
)

LANGUAGES = [
    "日本語",
    "英語",
    "中国語（簡体字）",
    "中国語（繁体字）",
    "韓国語",
    "フランス語",
    "ドイツ語",
    "スペイン語",
    "ポルトガル語",
    "イタリア語",
    "タイ語",
    "ベトナム語",
]

STYLES = {
    "自然な表現優先": "多少意訳してでも、その言語として自然な表現にする",
    "原文に忠実": "構造と情報を原文どおりに保つ。意訳は最小限にする",
    "ビジネス文書": "フォーマルな語彙と定型表現を使い、丁寧で簡潔にする",
    "カジュアル・口語": "日常会話で使う自然な言い回しにする",
    "技術文書": "用語の一貫性を最優先し、曖昧さを残さない",
}


def render() -> None:
    ui.page_header("🌐", "翻訳", "自然さや文体を指定して翻訳し、必要なら補足も出します。")
    if not ui.api_key_guard():
        return

    col1, col2 = st.columns(2)
    src = col1.selectbox("翻訳元", ["自動判定"] + LANGUAGES)
    dst = col2.selectbox("翻訳先", LANGUAGES, index=1)

    source = st.text_area("翻訳したい文章", height=240, placeholder="ここに文章を貼り付けてください。")
    ui.word_count(source)

    style = st.selectbox("スタイル", list(STYLES))
    glossary = st.text_area(
        "用語集（任意・1行1組）",
        height=80,
        placeholder="生成AI = generative AI\n弊社 = our company",
    )
    explain = st.toggle("訳の意図・別案の解説を付ける", value=False)

    run = st.button("翻訳する", type="primary", width="stretch")

    prompt = None
    if run:
        if not source.strip():
            st.warning("翻訳する文章を入力してください。", icon="⚠️")
        else:
            src_label = "原文の言語を自動で判定し" if src == "自動判定" else f"{src}から"
            prompt = prompts.build(
                f"次の文章を{src_label}{dst}に翻訳してください。",
                "",
                prompts.block("原文", source),
                prompts.block("用語集（必ずこの訳語を使う）", glossary),
                prompts.rules(
                    STYLES[style],
                    "訳文だけを出力する" if not explain else
                    "まず「## 訳文」として訳を出し、その後「## 補足」で訳し分けた理由や別案を簡潔に説明する",
                    "レイアウト（改行・箇条書き・見出し）は原文どおりに保つ",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        meta={"翻訳先": dst, "スタイル": style},
    )
