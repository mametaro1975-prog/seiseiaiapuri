"""受信メールへの返信文を作る。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "email"
TOOL_LABEL = "メール返信"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは日本のビジネスメールに精通した秘書です。"
    "相手との関係性に合った敬語を使い、用件が一読で伝わる構成にします。"
    "件名・宛名・挨拶・本文・結び・署名の順で、そのまま送れる完成形を出力します。"
    "受信メールに書かれていない事実（日程・金額・固有名詞など）を勝手に作らず、"
    "埋めるべき箇所は〔　〕で空欄にしてください。"
)

RELATIONS = [
    "社外・取引先",
    "社外・初めて連絡する相手",
    "社内・上司",
    "社内・同僚",
    "お客様（カスタマーサポート）",
    "友人・カジュアル",
]

POLITENESS = ["標準（ですます）", "かなり丁寧（謙譲語多め）", "簡潔・事務的", "やわらかい・親しみ"]


def render() -> None:
    ui.page_header("📧", "メール返信作成", "受け取ったメールと伝えたい要点から、送れる状態の返信文を作ります。")
    if not ui.api_key_guard():
        return

    received = st.text_area(
        "受け取ったメール（本文を貼り付け）",
        height=220,
        placeholder="お世話になっております。株式会社◯◯の△△です。……",
    )
    ui.word_count(received)

    points = st.text_area(
        "返信で伝えたいこと（箇条書きでOK）",
        height=120,
        placeholder="・打ち合わせは来週火曜の14時なら可能\n・資料は前日までに送る\n・日程変更のお詫び",
    )

    col1, col2 = st.columns(2)
    relation = col1.selectbox("相手との関係", RELATIONS)
    politeness = col2.selectbox("敬語のレベル", POLITENESS)

    variations = st.radio("案の数", [1, 2, 3], index=0, horizontal=True)
    length = ui.length_picker(
        "email",
        default=350,
        label="本文の文字数の目安",
        minimum=50,
        maximum=3000,
        step=50,
    )
    st.caption("件名と署名を除いた、本文だけの文字数です。")

    signature = st.text_input("署名に使う名前・所属（任意）", placeholder="株式会社□□ 営業部 山田太郎")

    run = st.button("返信文を作る", type="primary", width="stretch")

    prompt = None
    if run:
        if not received.strip() and not points.strip():
            st.warning("受け取ったメールか、伝えたいことのどちらかは入力してください。", icon="⚠️")
        else:
            variation_rule = (
                f"トーンの違う返信案を{variations}パターン作り、それぞれ「## 案1: （特徴）」の見出しで区切る"
                if variations > 1
                else "返信案は1つだけ作る"
            )
            prompt = prompts.build(
                "次の受信メールに対する返信文を作成してください。",
                "",
                prompts.block("受信したメール", received),
                prompts.block("返信で必ず伝えたい内容", points),
                prompts.rules(
                    f"相手は「{relation}」",
                    f"敬語のレベルは「{politeness}」",
                    *prompts.length_rules(
                        length[0], length[1], length[2], unit="返信本文（件名と署名を除く）"
                    ),
                    variation_rule,
                    "件名（Re: を含む）から署名まで、コピーしてそのまま送れる形にする",
                    f"署名は「{signature}」を使う" if signature.strip() else "署名は〔署名〕とだけ書く",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        length=length if variations == 1 else None,
        meta={"相手": relation, "敬語": politeness, "案の数": variations,
              "文字数": f"{length[0]:,}字"},
    )
