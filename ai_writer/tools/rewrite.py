"""文章のトーン変換・リライト。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "rewrite"
TOOL_LABEL = "リライト"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたはリライトの専門家です。元の文章の情報と意図を保ったまま、"
    "指定されたトーン・長さ・読者に合わせて書き直します。"
)

PURPOSES = {
    "トーンを変える": "情報は保ったまま、指定した文体・雰囲気に書き直す",
    "短くする": "重要な情報を落とさずに、大幅に短くする",
    "詳しくふくらませる": "具体例や補足を足して、内容を厚くする",
    "やさしく言い換える": "専門用語を避け、前提知識がない人にも分かるようにする",
    "説得力を上げる": "根拠・数字・具体例を補い、主張が伝わる構成に組み替える",
    "箇条書きにする": "文章を構造化し、見出しと箇条書きに整理する",
    "文章にする": "箇条書きやメモを、つながりのある文章にする",
}


def render() -> None:
    ui.page_header("🔄", "リライト・言い換え", "同じ内容を、別のトーン・長さ・読者向けに書き直します。")
    if not ui.api_key_guard():
        return

    source = st.text_area("元の文章", height=240, placeholder="書き直したい文章を貼り付けてください。")
    ui.word_count(source)

    purpose = st.selectbox("目的", list(PURPOSES))
    col1, col2 = st.columns(2)
    tone = col1.selectbox("トーン", prompts.TONES)
    audience = col2.text_input("想定読者（任意）", placeholder="例: 高校生 / 取引先の役員")

    extra = st.text_input("追加の指示（任意）", placeholder="例: 一人称は「私」。絵文字は使わない。")

    length = None
    if st.toggle("文字数を指定する", value=False):
        suggested = max(100, round(len(source) / 100) * 100) if source else 800
        length = ui.length_picker(
            "rewrite",
            default=min(suggested, 20000),
            label="書き直したあとの文字数",
            minimum=50,
            maximum=20000,
            step=100,
        )

    run = st.button("リライトする", type="primary", width="stretch")

    prompt = None
    if run:
        if not source.strip():
            st.warning("元の文章を入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                "次の文章をリライトしてください。書き直した文章だけを出力し、解説は不要です。",
                "",
                prompts.block("元の文章", source),
                prompts.block("読者", audience),
                prompts.block("追加の指示", extra),
                prompts.rules(
                    PURPOSES[purpose],
                    f"トーンは「{tone}」",
                    *(prompts.length_rules(length[0], length[1], length[2]) if length else []),
                    "元の文章にない事実は足さない",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        length=length,
        meta={"目的": purpose, "トーン": tone,
              **({"文字数": f"{length[0]:,}字"} if length else {})},
    )
