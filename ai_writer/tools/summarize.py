"""長い文章を要約する。"""

from __future__ import annotations

import streamlit as st

from ..core import prompts, ui

TOOL_KEY = "summary"
TOOL_LABEL = "文章要約"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは要約の専門家です。原文にある情報だけを使い、"
    "結論・根拠・数字を優先して残します。原文にない解釈や推測は加えません。"
    "重要な固有名詞と数値は必ず保持してください。"
)

FORMATS = {
    "箇条書き": "重要な点を箇条書きで示す",
    "1段落の要約文": "つながりのある文章として1段落でまとめる",
    "3行まとめ": "3行以内で要点だけを書く",
    "議事録スタイル": "「決定事項」「議論の要点」「次のアクション」の見出しに分けて整理する",
    "見出し + 要点": "話題ごとに見出しを立て、その下に要点を箇条書きで書く",
}


def _read_upload(file) -> str:
    raw = file.read()
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def render() -> None:
    ui.page_header("📄", "文章要約", "長い記事・議事録・メールを、目的に合った形に要約します。")
    if not ui.api_key_guard():
        return

    upload = st.file_uploader("テキストファイルを読み込む（任意）", type=["txt", "md", "csv"])
    default_text = _read_upload(upload) if upload else ""
    source = st.text_area(
        "要約したい文章",
        value=default_text,
        height=280,
        placeholder="ここに文章を貼り付けてください。",
    )
    ui.word_count(source)

    col1, col2 = st.columns(2)
    fmt = col1.selectbox("形式", list(FORMATS))
    mode = col2.radio("長さの決め方", ["原文からの割合", "文字数で指定"], horizontal=True)

    length = None
    ratio = ""
    if mode == "原文からの割合":
        ratio = st.select_slider(
            "どれくらい短く",
            options=["ぎゅっと（原文の5%）", "短め（10%）", "標準（20%）", "詳しめ（35%）"],
            value="標準（20%）",
        )
    else:
        suggested = max(100, min(3000, round(len(source) * 0.2 / 50) * 50)) if source else 400
        length = ui.length_picker(
            "summary",
            default=suggested,
            label="要約の文字数",
            minimum=50,
            maximum=10000,
            step=50,
        )

    audience = st.text_input("誰に向けた要約か（任意）", placeholder="例: 内容を知らない上司に報告する")
    keep = st.text_input("必ず残したい観点（任意）", placeholder="例: 金額と納期、リスク")

    run = st.button("要約する", type="primary", width="stretch")

    prompt = None
    if run:
        if not source.strip():
            st.warning("要約する文章を入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                "次の文章を要約してください。",
                "",
                prompts.block("原文", source),
                prompts.block("要約を読む人", audience),
                prompts.block("必ず残す観点", keep),
                prompts.rules(
                    FORMATS[fmt],
                    *(
                        prompts.length_rules(length[0], length[1], length[2], unit="要約")
                        if length
                        else [f"分量の目安は「{ratio}」"]
                    ),
                    "原文に書かれていないことは足さない",
                    "数値・日付・固有名詞はそのまま残す",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=SYSTEM,
        length=length,
        meta={
            "形式": fmt,
            "長さ": f"{length[0]:,}字" if length else ratio,
            "原文文字数": len(source),
        },
    )
