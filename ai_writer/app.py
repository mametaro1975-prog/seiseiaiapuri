"""AI ライティングツール（個人用）のエントリポイント。

起動: streamlit run ai_writer/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_writer.core import config, ui  # noqa: E402
from ai_writer.tools import (  # noqa: E402
    blog,
    brainstorm,
    catchcopy,
    chat,
    email_reply,
    history_view,
    note_article,
    proofread,
    rewrite,
    social,
    summarize,
    thumbnail,
    translate,
)

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="centered",
    initial_sidebar_state="expanded",
)

# (モジュール, タイトル, アイコン, URLパス, ひとこと説明)
TOOLS = {
    "書く": [
        (blog, "ブログ記事作成", "📝", "blog", "構成案から本文まで一気に書く"),
        (note_article, "note記事作成", "🖊️", "note", "メモから note の語り口で書く"),
        (email_reply, "メール返信作成", "📧", "email", "受信メールに合わせた返信文を作る"),
        (social, "SNS投稿文", "📱", "social", "各SNSの作法に合わせた投稿案を出す"),
    ],
    "整える": [
        (summarize, "文章要約", "📄", "summary", "長文を目的に合った形に短くする"),
        (proofread, "校正・推敲", "🔍", "proofread", "誤字と表現を直し、理由も示す"),
        (rewrite, "リライト・言い換え", "🔄", "rewrite", "トーンや長さを変えて書き直す"),
        (translate, "翻訳", "🌐", "translate", "自然さを指定して翻訳する"),
    ],
    "考える": [
        (catchcopy, "タイトル・コピー", "💡", "copy", "切り口違いのタイトル案をまとめて出す"),
        (brainstorm, "アイデア出し", "🧠", "idea", "企画やネタを切り口ごとに出す"),
        (chat, "AIチャット", "💬", "chat", "文章の相談や壁打ちをする"),
    ],
    "画像": [
        (thumbnail, "サムネイル作成", "🖼️", "thumbnail", "note・ブログ・SNS 別の比率で画像を作る"),
    ],
}


def home() -> None:
    st.title(f"{config.APP_ICON} {config.APP_TITLE}")
    st.caption("書く・整える・考える。文章まわりの作業を Gemini にまかせるための個人用ツールです。")

    if not config.current().ready:
        st.warning("まずは左のサイドバーで Gemini APIキーを設定してください。", icon="🔑")

    for group, items in TOOLS.items():
        st.subheader(group)
        columns = st.columns(2)
        for index, (_, title, icon, url_path, description) in enumerate(items):
            with columns[index % 2].container(border=True):
                st.markdown(f"### {icon} {title}")
                st.caption(description)
                if st.button("開く", key=f"go::{url_path}", width="stretch"):
                    st.switch_page(PAGES[url_path])
        st.write("")

    with st.expander("使い方のヒント"):
        st.markdown(
            """
- **サイドバーの設定は全ツール共通**です。迷ったら Flash + 創造性 0.7 のままで大丈夫です。
- 事実を扱う文章（要約・翻訳・メール）は **創造性を 0.3 前後**に下げると安定します。
- アイデア出しやコピーは **1.0 以上**に上げると発想が広がります。
- 生成結果は自動で **履歴** に残ります。あとから探したいときはサイドバーの「履歴」へ。
- 結果は AI が書いた下書きです。**事実と固有名詞は必ず自分で確認**してから使ってください。
            """
        )


PAGES: dict[str, st.Page] = {}
for group, items in TOOLS.items():
    for module, title, icon, url_path, _ in items:
        PAGES[url_path] = st.Page(module.render, title=title, icon=icon, url_path=url_path)

navigation = {
    "ホーム": [st.Page(home, title="ホーム", icon="🏠", url_path="home", default=True)],
    **{
        group: [PAGES[url_path] for _, _, _, url_path, _ in items]
        for group, items in TOOLS.items()
    },
    "記録": [st.Page(history_view.render, title="履歴", icon="🗂️", url_path="history")],
}

ui.sidebar_settings()
# expanded=True でツールが増えても「View more」に隠れないようにする
st.navigation(navigation, expanded=True).run()
