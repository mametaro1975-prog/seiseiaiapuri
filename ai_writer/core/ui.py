"""各ツールで共通して使う UI 部品。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from . import config, gemini, history, richcopy
from . import photos as photos_mod


def sidebar_settings() -> config.Settings:
    """サイドバーに生成条件を描画し、確定した設定を返す。"""
    with st.sidebar:
        st.subheader("⚙️ 設定")

        env_key = config.env_api_key()
        if env_key:
            st.session_state.setdefault("api_key", env_key)
            st.success("APIキーを .env から読み込みました", icon="🔑")
        else:
            st.text_input(
                "Gemini APIキー",
                type="password",
                key="api_key",
                help="https://aistudio.google.com/apikey で取得できます。"
                "`.env` に GEMINI_API_KEY を書いておけば毎回の入力は不要です。",
                placeholder="AIza...",
            )
            if not st.session_state.get("api_key"):
                st.warning("APIキーを入力すると使えるようになります。", icon="⚠️")

        _model_selector()

        st.slider(
            "創造性（temperature）",
            min_value=0.0,
            max_value=1.5,
            value=0.7,
            step=0.1,
            key="temperature",
            help="低いほど堅実で正確、高いほど自由な発想になります。",
        )
        st.toggle(
            "高速モード",
            key="fast_mode",
            help="Flash 系モデルで思考プロセスを省き、速さを優先します。",
        )

        st.divider()
        st.caption("履歴はこの PC の `ai_writer/data/history.json` にだけ保存されます。")

    return config.current()


TOLERANCES = {
    "±10%（きっちり）": 0.10,
    "±20%（ふつう）": 0.20,
    "±30%（ゆるめ）": 0.30,
}


def _model_label(model_id: str) -> str:
    note = gemini.MODEL_NOTES.get(model_id)
    return f"{model_id}（{note}）" if note else model_id


def _model_selector() -> None:
    """APIキーで実際に使えるモデルを並べる。取れなければ既定の一覧を使う。"""
    api_key = config.current().api_key
    models = gemini.text_models(api_key) if api_key else []

    if models:
        previous = st.session_state.get("model_id")
        # 前に選んでいたモデルが一覧から消えていたら、先頭（既定）に戻す
        index = models.index(previous) if previous in models else 0
        st.session_state["model_id"] = st.selectbox(
            "モデル", models, index=index, format_func=_model_label
        )
        st.caption(f"✅ このAPIキーで使えるモデル {len(models)} 個から選べます。")
    else:
        label = st.selectbox(
            "モデル",
            list(config.MODELS),
            index=list(config.MODELS).index(config.DEFAULT_MODEL_LABEL),
        )
        st.session_state["model_id"] = config.MODELS[label]
        if api_key:
            st.warning(
                "使えるモデルの一覧を取得できませんでした。この一覧は仮のもので、"
                "選んだモデルが使えないことがあります。下の接続テストを試してください。",
                icon="⚠️",
            )

    with st.expander("🔧 接続テスト"):
        st.caption("「モデルが見つかりません」と出るときは、ここで使えるモデルを確認できます。")
        if st.button("使えるモデルを調べる", width="stretch"):
            if not api_key:
                st.warning("先にAPIキーを入力してください。")
            else:
                with st.spinner("問い合わせています…"):
                    ok, message = gemini.probe(api_key)
                if ok:
                    st.success("接続できました。使えるモデル:")
                    st.markdown(message)
                else:
                    st.error(message)


def length_picker(
    key: str,
    *,
    default: int,
    label: str = "文字数の目安",
    minimum: int = 50,
    maximum: int = 20000,
    step: int = 100,
    tolerance: str = "±20%（ふつう）",
) -> tuple[int, int, int]:
    """文字数の目安を選ぶ入力欄。(目標, 下限, 上限) を返す。"""
    col1, col2 = st.columns([2, 1])
    target = int(
        col1.number_input(
            label,
            min_value=minimum,
            max_value=maximum,
            value=default,
            step=step,
            key=f"len::{key}",
            help="AI は指定ちょうどには書けないため、下の許容幅の範囲を狙わせます。",
        )
    )
    tolerance_label = col2.selectbox(
        "許容幅",
        list(TOLERANCES),
        index=list(TOLERANCES).index(tolerance),
        key=f"tol::{key}",
    )
    ratio = TOLERANCES[tolerance_label]
    low, high = int(target * (1 - ratio)), int(target * (1 + ratio))
    st.caption(f"狙う範囲: {low:,} 〜 {high:,} 字")
    return target, low, high


def page_header(icon: str, title: str, description: str) -> None:
    st.title(f"{icon} {title}")
    st.caption(description)


def api_key_guard() -> bool:
    """APIキーが無ければ案内を出して False を返す。"""
    if config.current().ready:
        return True
    st.info("左のサイドバーで Gemini APIキーを入力してください。", icon="🔑")
    return False


def _state_key(tool_key: str) -> str:
    return f"result::{tool_key}"


def render_output(
    tool_key: str,
    tool_label: str,
    *,
    prompt: str | None = None,
    system: str | None = None,
    meta: dict[str, Any] | None = None,
    max_output_tokens: int | None = None,
    length: tuple[int, int, int] | None = None,
    photos: list["photos_mod.Photo"] | None = None,
) -> None:
    """生成結果の表示・保存・再表示をまとめて担当する。

    prompt を渡したときだけ新しく生成し、それ以外は前回の結果を表示する。
    """
    state_key = _state_key(tool_key)
    st.subheader("生成結果")
    box = st.container(border=True)

    if prompt is not None:
        with box:
            slot = st.empty()
            try:
                with slot.container():
                    text = st.write_stream(
                        gemini.stream_text(
                            prompt,
                            system_instruction=system,
                            max_output_tokens=max_output_tokens,
                            images=photos_mod.as_parts(photos) if photos else None,
                        )
                    )
            except gemini.GeminiError as exc:
                st.error(str(exc), icon="🚫")
                return
        text = text if isinstance(text, str) else "".join(map(str, text))
        if not text.strip():
            st.warning("結果が空でした。入力内容を変えてもう一度試してください。", icon="⚠️")
            return
        st.session_state[state_key] = text
        st.session_state[f"length::{tool_key}"] = length
        entry_meta = dict(meta or {})
        if photos:
            # 履歴からも写真つきで見返せるように、画像そのものを保存する
            entry_meta["photos"] = photos_mod.to_meta(photos)
        history.add(tool_label, text, entry_meta)
        if photos:
            # 写真の目印を実際の画像に置き換えて描き直す
            slot.empty()
            with slot.container():
                photos_mod.render(text, photos)
    elif st.session_state.get(state_key):
        with box:
            photos_mod.render(st.session_state[state_key], photos or [])
    else:
        with box:
            st.caption("ここに生成結果が表示されます。")
        return

    photos_mod.position_editor(state_key, tool_key, photos or [])
    result_actions(state_key, tool_key, photos=photos)


def result_actions(
    state_key: str, tool_key: str, *, photos: list["photos_mod.Photo"] | None = None
) -> None:
    """コピー・ダウンロード・クリアのボタン群。"""
    text = st.session_state.get(state_key, "")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    _length_report(text, st.session_state.get(f"length::{tool_key}"))

    note_text = photos_mod.to_note_text(text, photos) if photos else text
    richcopy.copy_button(
        note_text,
        label="📋 note・メールに貼る用にコピー（書式つき）",
        note="見出し・太字・箇条書きが書式のまま貼り付けられます。"
        + ("　写真は「📷 ここに写真1」の行に、あとからドラッグしてください。" if photos else ""),
    )

    with st.expander("📝 そのままのテキスト（Markdown）"):
        st.code(text, language=None, wrap_lines=True)

    if photos:
        left, middle, right = st.columns(3)
        middle.download_button(
            "🗜️ 写真ごと ZIP で保存",
            data=photos_mod.to_zip(text, photos, basename=tool_key),
            file_name=f"{tool_key}-{stamp}.zip",
            mime="application/zip",
            width="stretch",
            help="記事の Markdown と images/ フォルダをまとめた ZIP です。",
        )
        markdown_text = photos_mod.to_markdown(text, photos)
    else:
        left, right = st.columns(2)
        markdown_text = text

    left.download_button(
        "⬇️ Markdown で保存",
        data=markdown_text,
        file_name=f"{tool_key}-{stamp}.md",
        mime="text/markdown",
        width="stretch",
    )
    if right.button("🗑️ 結果を消す", key=f"clear::{tool_key}", width="stretch"):
        st.session_state.pop(state_key, None)
        st.session_state.pop(f"edit::{tool_key}", None)
        st.rerun()


def _length_report(text: str, length: tuple[int, int, int] | None) -> None:
    """実際の文字数と、指定した範囲に収まったかを表示する。"""
    actual = len(text)
    if not length:
        st.caption(f"{actual:,} 字")
        return
    target, low, high = length
    if low <= actual <= high:
        st.caption(f"✅ {actual:,} 字（目安 {target:,} 字 / 範囲 {low:,}〜{high:,} 字）")
    else:
        gap = actual - target
        direction = "多い" if gap > 0 else "少ない"
        st.caption(
            f"⚠️ {actual:,} 字（目安 {target:,} 字より {abs(gap):,} 字{direction}）"
            "　— もう一度生成するか、リライトで調整できます"
        )


def word_count(text: str) -> None:
    """入力欄の下に文字数を出す。"""
    st.caption(f"{len(text)} 文字")
