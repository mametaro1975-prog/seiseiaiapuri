"""過去の生成結果を見返す・削除する。"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from ..core import history, richcopy, ui
from ..core import photos as photolib

UNDO_KEY = "history_undo"


def _format_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%m/%d %H:%M")
    except ValueError:
        return value


def _undo_bar() -> None:
    """直前に削除したものを戻すための案内。"""
    pending = st.session_state.get(UNDO_KEY)
    if not pending:
        return
    with st.container(border=True):
        message, undo, close = st.columns([5, 2, 1])
        message.markdown(
            f"🗑️ **{pending.get('tool')}**（{_format_time(pending.get('created_at', ''))}）を削除しました。"
        )
        if undo.button("↩️ 元に戻す", width="stretch"):
            history.restore(pending)
            del st.session_state[UNDO_KEY]
            st.rerun()
        if close.button("✕", width="stretch", help="この案内を閉じる"):
            del st.session_state[UNDO_KEY]
            st.rerun()


def _delete(entry: dict) -> None:
    st.session_state[UNDO_KEY] = entry
    history.delete(entry["id"])
    st.rerun()


def _entry_row(entry: dict) -> None:
    """1件ぶんの行。開かなくても右の 🗑️ で消せる。"""
    body, actions = st.columns([12, 1], vertical_alignment="top")

    text = entry.get("output", "")
    head = text.strip().replace("\n", " ")[:40]
    label = f"**{entry.get('tool')}**　{_format_time(entry.get('created_at', ''))}　— {head}…"

    with body, st.expander(label):
        meta = dict(entry.get("meta") or {})
        generated = meta.pop("images", [])  # サムネイルとして生成した画像
        photos = photolib.from_meta(meta.pop("photos", []))  # 記事に入れた写真
        if meta:
            st.caption(" / ".join(f"{k}: {v}" for k, v in meta.items() if v))

        for name in generated:
            data = history.image_bytes(name)
            if data is None:
                st.caption(f"（画像 {name} は削除されています）")
                continue
            st.image(data, width="stretch")
            st.download_button(
                "⬇️ 画像をダウンロード",
                data=data,
                file_name=name,
                mime="image/png",
                key=f"img::{entry['id']}::{name}",
                width="stretch",
            )

        # 記事に入れた写真は、本文の目印の位置に差し込んで表示する
        photolib.render(text, photos)

        st.divider()
        richcopy.copy_button(
            photolib.to_note_text(text, photos) if photos else text,
            label="📋 note・メールに貼る用にコピー（書式つき）",
            note="見出し・太字・箇条書きが書式のまま貼り付けられます。"
            + ("　写真は「📷 ここに写真1」の行に、下の写真をドラッグしてください。" if photos else ""),
        )

        with st.expander("📝 そのままのテキスト（Markdown）"):
            st.code(text, language=None, wrap_lines=True)

        if photos:
            with st.expander(f"🖼️ 写真をダウンロード（{len(photos)}枚 / note にドラッグする用）"):
                columns = st.columns(min(len(photos), 3))
                for position, photo in enumerate(photos):
                    with columns[position % len(columns)]:
                        st.image(photo.data, caption=photo.marker, width="stretch")
                        st.download_button(
                            "⬇️ 保存",
                            data=photo.data,
                            file_name=photo.filename,
                            mime=photo.mime,
                            key=f"photo::{entry['id']}::{photo.index}",
                            width="stretch",
                        )

        buttons = st.columns(3 if photos else 2)
        buttons[0].download_button(
            "⬇️ Markdown",
            data=photolib.to_markdown(text, photos) if photos else text,
            file_name=f"{entry.get('tool')}-{entry.get('id')}.md",
            mime="text/markdown",
            key=f"dl::{entry['id']}",
            width="stretch",
        )
        if photos:
            buttons[1].download_button(
                "🗜️ 写真ごと ZIP",
                data=photolib.to_zip(text, photos, basename=str(entry.get("tool"))),
                file_name=f"{entry.get('tool')}-{entry.get('id')}.zip",
                mime="application/zip",
                key=f"zip::{entry['id']}",
                width="stretch",
            )
        if buttons[-1].button("🗑️ 削除", key=f"del-in::{entry['id']}", width="stretch"):
            _delete(entry)

    if actions.button("🗑️", key=f"del::{entry['id']}", help="この履歴を削除", width="stretch"):
        _delete(entry)


def _cleanup_images() -> None:
    """どの履歴からも参照されていない画像を掃除する。"""
    orphans = history.unused_images()
    if not orphans:
        return
    with st.expander(f"🖼️ どの履歴にも紐づいていない画像が {len(orphans)} 件あります"):
        st.caption("履歴を消したあとに残った画像ファイルです。消してもほかの履歴には影響しません。")
        st.code("\n".join(orphans), language=None, wrap_lines=True)
        if st.button("この画像を削除する", key="cleanup_images"):
            removed = history.delete_images(orphans)
            st.toast(f"画像を {removed} 件削除しました。", icon="🗑️")
            st.rerun()


def render() -> None:
    ui.page_header("🗂️", "履歴", "これまでの生成結果を見返し、1件ずつ削除できます。")

    _undo_bar()

    entries = history.load()
    if not entries:
        st.info("まだ履歴がありません。どれかのツールで文章を作ると、ここに残ります。", icon="📭")
        _cleanup_images()
        return

    col1, col2 = st.columns([2, 1])
    selected_tools = col1.multiselect("ツールで絞り込む", history.tools())
    keyword = col2.text_input("キーワード検索", placeholder="本文を検索")

    shown = [
        e
        for e in entries
        if (not selected_tools or e.get("tool") in selected_tools)
        and (not keyword or keyword.lower() in e.get("output", "").lower())
    ]
    st.caption(f"{len(shown)} 件 / 全 {len(entries)} 件　—　右の 🗑️ で1件ずつ削除できます")

    for entry in shown:
        _entry_row(entry)

    st.divider()
    _cleanup_images()

    col3, col4 = st.columns(2)
    col3.download_button(
        "📦 全履歴を JSON で書き出す",
        data=json.dumps(entries, ensure_ascii=False, indent=2),
        file_name="ai-writer-history.json",
        mime="application/json",
        width="stretch",
    )
    with col4.popover("🧹 履歴をすべて削除", width="stretch"):
        st.warning("元に戻せません。よろしいですか？")
        if st.button("削除する", type="primary"):
            history.clear()
            st.session_state.pop(UNDO_KEY, None)
            st.rerun()
