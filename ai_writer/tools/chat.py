"""自由に相談できるチャット（文章の壁打ち用）。"""

from __future__ import annotations

import streamlit as st

from ..core import gemini, prompts, ui

TOOL_KEY = "chat"
TOOL_LABEL = "AIチャット"
STATE_KEY = "chat_messages"

ROLES = {
    "編集者": "あなたはベテランの編集者です。相手の文章や企画に率直な意見を返し、"
    "良い点と直すべき点を具体的に指摘します。曖昧な褒め言葉は使いません。",
    "ライターの相棒": "あなたは書き手の相棒です。一緒に考えながら、"
    "書き出しや構成の候補を出し、詰まっている理由を言語化します。",
    "厳しい読者": "あなたは批判的な読者です。書かれた内容に対して、"
    "納得できない点・根拠が薄い点・退屈な点を遠慮なく指摘します。",
    "何でも相談": "あなたは有能なアシスタントです。質問に的確に答え、"
    "必要なら例を示します。",
}


def render() -> None:
    ui.page_header("💬", "AIチャット", "文章の相談、続きの執筆、質問など自由に対話できます。")
    if not ui.api_key_guard():
        return

    col1, col2 = st.columns([3, 1])
    role = col1.selectbox("相手の役割", list(ROLES), label_visibility="collapsed")
    if col2.button("会話をリセット", width="stretch"):
        st.session_state[STATE_KEY] = []
        st.rerun()

    messages: list[dict] = st.session_state.setdefault(STATE_KEY, [])

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("メッセージを入力（Shift+Enter で改行）")
    if not user_input:
        return

    messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(
                gemini.chat_stream(
                    messages,
                    system_instruction=prompts.BASE_SYSTEM + ROLES[role],
                )
            )
        except gemini.GeminiError as exc:
            st.error(str(exc), icon="🚫")
            messages.pop()
            return

    messages.append({"role": "assistant", "content": reply})
