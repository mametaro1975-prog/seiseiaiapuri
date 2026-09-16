"""企画・ネタのアイデア出し。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "brainstorm"
TOOL_LABEL = "アイデア出し"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは企画会議のファシリテーターです。ありきたりな案で埋めず、"
    "実行できる具体性のある案を、切り口を変えながら出します。"
    "各案は「誰の何を解決するか」が分かる粒度で書いてください。"
)

KINDS = {
    "ブログ記事のネタ": "検索需要がありそうなテーマと、それぞれの狙う読者",
    "SNS投稿のネタ": "続けやすく、反応が取りやすい投稿テーマ",
    "動画・配信の企画": "見たくなる企画と、その一言説明",
    "商品・サービスの企画": "誰のどんな困りごとを解決するかを明確にした企画",
    "イベント・キャンペーン案": "目的と参加者の動機がはっきりした施策",
    "文章の切り口・構成案": "同じテーマを別角度から書くための切り口",
}


def render() -> None:
    ui.page_header("🧠", "アイデア出し", "テーマを渡すと、切り口を変えた企画案をまとめて出します。")
    if not ui.api_key_guard():
        return

    kind = st.selectbox("出したいもの", list(KINDS))
    theme = st.text_area(
        "テーマ・前提",
        height=140,
        placeholder="例: 個人でやっている在宅ワーク系のブログ。読者は20〜30代の会社員。",
    )

    col1, col2 = st.columns(2)
    count = col1.slider("案の数", 3, 20, 8)
    constraint = col2.text_input("制約（任意）", placeholder="例: 予算ゼロ、1人で回せること")

    detail = st.toggle("各案に「なぜ効くか」の解説を付ける", value=True)

    run = st.button("アイデアを出す", type="primary", width="stretch")

    prompt = None
    if run:
        if not theme.strip():
            st.warning("テーマを入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                f"{kind}を {count} 個出してください。",
                "",
                prompts.block("テーマ・前提", theme),
                prompts.block("制約", constraint),
                prompts.rules(
                    KINDS[kind],
                    "案ごとに番号とタイトルを付ける",
                    "各案に「なぜ効くのか」を1〜2文で添える" if detail else "説明は付けず、案のタイトルだけを並べる",
                    "似た案を並べず、切り口を意図的に散らす",
                    "最後に「まず手を付けるならこの3つ」として優先順位と理由を書く",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        meta={"種類": kind, "案の数": count},
    )
