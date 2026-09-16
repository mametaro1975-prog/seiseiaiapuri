"""SNS 投稿文の作成。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "social"
TOOL_LABEL = "SNS投稿"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは SNS 運用の担当者です。最初の1〜2行で手を止めさせる書き出しを作り、"
    "プラットフォームごとの文化と文字数に合わせて書き分けます。誇張や煽りは避けます。"
)

PLATFORMS: dict[str, dict] = {
    "X（旧Twitter）": {
        "chars": 130,
        "limit": 140,
        "guide": "1投稿で完結させる。改行を活かし、ハッシュタグは多くても2つ",
    },
    "X・連続ポスト（スレッド）": {
        "chars": 130,
        "limit": 140,
        "guide": "1投稿ずつに分け、1本目でフックを作る。投稿ごとに「1/5」のように番号を振る",
        "per_post": True,
    },
    "Instagram": {
        "chars": 600,
        "guide": "冒頭2行で引きを作り、その後に改行を多めに使った読みやすい本文。"
        "最後にハッシュタグをまとめる",
    },
    "LinkedIn": {
        "chars": 800,
        "guide": "実務的な学びや知見を、落ち着いたトーンで。宣伝色は抑えめに",
    },
    "Facebook": {
        "chars": 500,
        "guide": "少し長めの語りかけ調。エピソードから入る",
    },
    "note・ブログ告知": {
        "chars": 400,
        "guide": "記事に興味を持たせる紹介文。内容の核心は少しだけ見せる",
    },
}


def render() -> None:
    ui.page_header("📱", "SNS投稿文", "伝えたいことを、各SNSの作法に合わせた投稿文にします。")
    if not ui.api_key_guard():
        return

    platform = st.selectbox("投稿先", list(PLATFORMS))
    preset = PLATFORMS[platform]
    topic = st.text_area(
        "投稿したい内容・元ネタ",
        height=160,
        placeholder="例: 新しく書いたブログ記事「在宅ワークの集中術」を紹介したい。ポモドーロが効いた話。",
    )

    col1, col2 = st.columns(2)
    tone = col1.selectbox("トーン", prompts.TONES, index=1)
    count = col2.slider("案の数", 1, 5, 3)

    col3, col4 = st.columns(2)
    hashtags = col3.slider("ハッシュタグの数", 0, 10, 3)
    emoji = col4.toggle("絵文字を使う", value=True)

    cta = st.text_input("入れたいリンク・行動喚起（任意）", placeholder="例: 記事はプロフィールのリンクから")

    unit = "1投稿あたりの文字数" if preset.get("per_post") else "投稿の文字数"
    target, low, high = ui.length_picker(
        f"social::{platform}",
        default=preset["chars"],
        label=unit,
        minimum=30,
        maximum=3000,
        step=10,
        tolerance="±10%（きっちり）" if preset.get("limit") else "±20%（ふつう）",
    )
    if preset.get("limit"):
        high = min(high, preset["limit"])
        st.caption(f"{platform} の上限は {preset['limit']} 字です。上限は超えないように作ります。")

    run = st.button("投稿文を作る", type="primary", width="stretch")

    prompt = None
    if run:
        if not topic.strip():
            st.warning("投稿したい内容を入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                f"{platform} 向けの投稿文を {count} 案作ってください。",
                "",
                prompts.block("投稿したい内容", topic),
                prompts.block("入れたい行動喚起", cta),
                prompts.rules(
                    preset["guide"],
                    *prompts.length_rules(target, low, high, unit=unit.replace("の文字数", "")),
                    f"1投稿は必ず {preset['limit']} 字以内に収める" if preset.get("limit") else "",
                    f"トーンは「{tone}」",
                    f"ハッシュタグは {hashtags} 個" if hashtags else "ハッシュタグは付けない",
                    "絵文字を適度に使う" if emoji else "絵文字は使わない",
                    "案ごとに「## 案1」の見出しを付け、見出しの横に狙い（切り口）を一言添える",
                    "各案の最後に (◯文字) と文字数を書く",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        meta={"投稿先": platform, "案の数": count, "文字数": f"{target:,}字"},
    )
