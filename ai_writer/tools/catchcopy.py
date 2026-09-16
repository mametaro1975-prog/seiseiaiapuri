"""タイトル・キャッチコピーの案出し。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "catchcopy"
TOOL_LABEL = "タイトル・コピー"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたはコピーライターです。ありふれた言い回しを避け、"
    "読み手の得か不安に具体的に触れる言葉を選びます。誇大表現や根拠のない断定はしません。"
)

USES = {
    "ブログ記事のタイトル": "検索されるキーワードを自然に含め、32文字前後に収める",
    "YouTube のタイトル": "サムネと合わせて機能する、30文字前後の引きのある表現",
    "メールの件名": "開封したくなる、25文字以内の具体的な件名",
    "商品・サービスのキャッチコピー": "短く記憶に残る一文。言い切る",
    "広告の見出し": "得られる結果を具体的に示す。数字を使う",
    "プレゼンのタイトル": "聞き手が得るものが分かる、簡潔で品のある表現",
    "本・note のタイトル": "続きが気になる、余韻のある表現",
}

ANGLES = [
    "ベネフィット（得られる結果）",
    "悩み・不安への共感",
    "意外性・常識のくつがえし",
    "数字・具体性",
    "手軽さ・時短",
    "権威・実績",
    "問いかけ",
    "ストーリー性",
]


def render() -> None:
    ui.page_header("💡", "タイトル・キャッチコピー", "同じ題材から、切り口の違う案をまとめて出します。")
    if not ui.api_key_guard():
        return

    use = st.selectbox("用途", list(USES))
    subject = st.text_area(
        "何についてのコピーか",
        height=140,
        placeholder="例: 在宅ワークで集中力を保つ方法を解説したブログ記事。ポモドーロと環境づくりが中心。",
    )

    col1, col2 = st.columns(2)
    target = col1.text_input("ターゲット（任意）", placeholder="例: 在宅勤務2年目の会社員")
    count = col2.slider("案の数", 3, 20, 10)

    angles = st.multiselect("使いたい切り口", ANGLES, default=ANGLES[:4])
    ng = st.text_input("使いたくない言葉（任意）", placeholder="例: 神, 最強, ヤバい")

    run = st.button("案を出す", type="primary", width="stretch")

    prompt = None
    if run:
        if not subject.strip():
            st.warning("題材を入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                f"{use}の案を {count} 個作ってください。",
                "",
                prompts.block("題材", subject),
                prompts.block("ターゲット", target),
                prompts.block("使ってほしい切り口", "\n".join(f"- {a}" for a in angles)),
                prompts.block("使わない言葉", ng),
                prompts.rules(
                    USES[use],
                    "番号付きリストで出し、案ごとに「切り口: ◯◯」を括弧書きで添える",
                    "似た表現の案を並べず、切り口を散らす",
                    "最後に「おすすめ3つ」として、特に強い案とその理由を書く",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        meta={"用途": use, "案の数": count},
    )
