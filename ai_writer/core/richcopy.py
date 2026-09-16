"""記事を「書式つき」でクリップボードにコピーするボタン。

note やメールの編集画面は Markdown をそのままは解釈しないため、
`## 見出し` が文字のまま貼られてしまう。HTML としてクリップボードに載せると、
見出し・太字・箇条書きが書式として貼り付けられる。
"""

from __future__ import annotations

import html as html_lib
import json
import re

import markdown
import streamlit as st

EXTENSIONS = ["extra", "nl2br", "sane_lists"]

# 行頭の # が、後ろに空白なしで続くもの（= ハッシュタグ）
HASHTAG_LINE = re.compile(r"^(#{1,6})(?=[^\s#])", flags=re.MULTILINE)


def protect_hashtags(text: str) -> str:
    """行頭のハッシュタグを見出しと誤解させないようにする。

    Markdown の見出しは「## 見出し」のように # のあとに空白が入る。
    空白のない「#無印良品」はハッシュタグなので、エスケープして守る。
    これをしないと、ハッシュタグが巨大な見出しとして貼り付けられてしまう。
    """
    return HASHTAG_LINE.sub(lambda m: "".join("\\" + c for c in m.group(1)), text)


def _converter() -> markdown.Markdown:
    converter = markdown.Markdown(extensions=EXTENSIONS)
    # 「文章の次の行に --- 」を見出しとみなす記法を切る。
    # 区切り線のつもりで入れた --- のせいで、直前の1行が巨大な見出しになるのを防ぐ。
    converter.parser.blockprocessors.deregister("setextheader")
    return converter


def to_html(text: str) -> str:
    """Markdown を HTML に変換する。

    本文は生成AIの出力なので、先に HTML エスケープしてタグを無効化してから変換する。
    """
    return _converter().convert(protect_hashtags(html_lib.escape(text)))


def copy_button(
    text: str,
    *,
    label: str = "📋 書式つきでコピー",
    note: str = "見出し・太字・箇条書きが、書式のまま貼り付けられます。",
) -> None:
    if not text.strip():
        return

    payload = json.dumps({"html": to_html(text), "plain": text}).replace("</", "<\\/")

    st.iframe(
        f"""
<style>
  body {{ margin: 0; font-family: "Helvetica Neue", Arial, sans-serif; }}
  #copy {{
    width: 100%; padding: 0.5rem 1rem; font-size: 0.9rem; cursor: pointer;
    border: 1px solid rgba(49,51,63,0.2); border-radius: 0.5rem;
    background: #fff; color: rgb(49,51,63);
  }}
  #copy:hover {{ border-color: #4F6DF5; color: #4F6DF5; }}
  #msg {{ font-size: 0.78rem; color: rgba(49,51,63,0.6); margin-top: 0.35rem; }}
</style>
<button id="copy">{label}</button>
<div id="msg">{note}</div>
<script>
  const payload = {payload};
  const button = document.getElementById("copy");
  const message = document.getElementById("msg");
  button.onclick = async () => {{
    try {{
      await navigator.clipboard.write([new ClipboardItem({{
        "text/html": new Blob([payload.html], {{ type: "text/html" }}),
        "text/plain": new Blob([payload.plain], {{ type: "text/plain" }}),
      }})]);
      message.textContent = "コピーしました。貼り付け先で Cmd+V（Ctrl+V）してください。";
    }} catch (error) {{
      try {{
        await navigator.clipboard.writeText(payload.plain);
        message.textContent = "書式なしでコピーしました（この環境では書式つきコピーが使えません）。";
      }} catch (fallbackError) {{
        message.textContent = "コピーできませんでした: " + fallbackError.message;
      }}
    }}
  }};
</script>
""",
        height=76,
    )
