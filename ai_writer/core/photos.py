"""記事に写真を差し込むための共通部品。

アップロード欄（ドラッグ&ドロップ対応）、AI に位置を決めさせるための指示、
本文中の [[写真1]] を実際の画像に置き換えたプレビュー、書き出しをまとめて扱う。
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from . import history, prompts

try:  # iPhone や Mac の写真（HEIC）を開けるようにする
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # noqa: BLE001 - 入っていなければ HEIC だけ諦める
    HEIF_SUPPORTED = False

PATTERN = re.compile(r"\[\[写真(\d+)\]\]")
ACCEPTED = ["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff"]
if HEIF_SUPPORTED:
    ACCEPTED += ["heic", "heif"]

# ブラウザがそのまま表示できる形式。これ以外は JPEG に変換する
WEB_SAFE = {"PNG", "JPEG", "WEBP", "GIF"}
# API に送るときの長辺の上限（元の写真はそのまま保持して、送る用だけ縮める）
API_MAX_EDGE = 1600


@dataclass
class Photo:
    index: int
    filename: str
    data: bytes  # 表示・書き出しに使う（必要なら JPEG に変換済み）
    mime: str
    caption: str
    api_data: bytes  # Gemini に送る縮小版

    @property
    def marker(self) -> str:
        return f"[[写真{self.index}]]"


@st.cache_data(show_spinner=False, max_entries=60)
def _prepare(raw: bytes, filename: str) -> tuple[bytes, str, str, bytes]:
    """写真を読み込んで整える。

    戻り値は (表示用バイト列, MIME, ファイル名, API送信用バイト列)。
    HEIC など、ブラウザが表示できない形式は JPEG に変換する。
    再実行のたびに変換が走らないようキャッシュする。
    """
    with Image.open(io.BytesIO(raw)) as image:
        fmt = (image.format or "").upper()

        if fmt in WEB_SAFE:
            display, mime, name = raw, Image.MIME.get(fmt, "image/png"), filename
        else:
            buffer = io.BytesIO()
            ImageOps.exif_transpose(image).convert("RGB").save(buffer, "JPEG", quality=92)
            display = buffer.getvalue()
            mime = "image/jpeg"
            name = f"{Path(filename).stem}.jpg"

        # API に送る用は長辺 1600px の JPEG に縮める（枚数が多くても通るように）
        small = ImageOps.exif_transpose(image).convert("RGB")
        small.thumbnail((API_MAX_EDGE, API_MAX_EDGE))
        buffer = io.BytesIO()
        small.save(buffer, "JPEG", quality=85)

    return display, mime, name, buffer.getvalue()


def uploader(key: str, *, label: str = "記事に入れる写真（任意）") -> list[Photo]:
    """写真のアップロード欄。枠内にドラッグ&ドロップできる。"""
    files = st.file_uploader(
        label,
        type=ACCEPTED,
        accept_multiple_files=True,
        key=f"photos::{key}",
        help="枠の中に写真をドラッグ&ドロップするか、クリックして選びます。複数まとめて入れられます。"
        + ("　iPhone の写真（HEIC）もそのまま入れられます。" if HEIF_SUPPORTED else ""),
    )
    if not files:
        st.caption("写真を入れると、AI が内容を見て本文の合う位置に配置します。")
        return []

    st.caption(
        f"{len(files)} 枚。並び順が写真1、写真2…になります。"
        "説明を書いておくと配置の精度が上がります（空欄でもAIが画像を見て判断します）。"
    )

    photos: list[Photo] = []
    columns = st.columns(min(len(files), 3))
    for position, file in enumerate(files):
        index = position + 1
        try:
            display, mime, name, api_data = _prepare(file.getvalue(), file.name)
        except Exception as exc:  # noqa: BLE001 - 壊れた画像や未対応形式
            st.error(f"「{file.name}」は読み込めませんでした（{exc}）。別の形式で保存し直してください。", icon="🚫")
            continue

        with columns[position % len(columns)]:
            st.image(display, caption=f"写真{index}", width="stretch")
            caption = st.text_input(
                f"写真{index} の説明",
                key=f"caption::{key}::{file.name}",
                placeholder="例: 朝の散歩コース",
                label_visibility="collapsed",
            )
        photos.append(
            Photo(
                index=index,
                filename=name,
                data=display,
                mime=mime,
                caption=caption,
                api_data=api_data,
            )
        )
    return photos


# --- プロンプト側 ---------------------------------------------------------


def prompt_block(photos: list[Photo]) -> str:
    if not photos:
        return ""
    body = "\n".join(
        f"- {p.marker}: {p.caption.strip() or '（説明なし。添付画像を見て内容を判断する）'}"
        for p in photos
    )
    return prompts.block("本文に入れる写真", body)


def prompt_rules(photos: list[Photo]) -> list[str]:
    if not photos:
        return []
    return [
        f"添付した写真 {len(photos)} 枚を、本文の内容に合う位置にすべて1回ずつ入れる",
        "写真を入れる位置には、その写真の目印だけを独立した1行として書く（例: [[写真1]]）",
        "目印の次の行に、その写真の説明文を「*〜*」で囲んで20〜40字で書く",
        "同じ写真を2回入れない。写真の内容と関係のない位置には入れない",
        "写真を入れた前後の文章は、その写真の内容に自然につながるように書く",
    ]


def to_meta(photos: list[Photo]) -> list[dict]:
    """履歴に残すための情報。画像は data/images/ に保存してファイル名だけ持つ。"""
    return [
        {
            "name": history.save_photo(p.data, p.mime),
            "index": p.index,
            "filename": p.filename,
            "mime": p.mime,
            "caption": p.caption,
        }
        for p in photos
    ]


def from_meta(items: list[dict]) -> list[Photo]:
    """履歴に保存した情報から Photo を組み立て直す。消えた画像は飛ばす。"""
    photos: list[Photo] = []
    for item in items or []:
        data = history.image_bytes(item.get("name", ""))
        if data is None:
            continue
        photos.append(
            Photo(
                index=item.get("index", len(photos) + 1),
                filename=item.get("filename", item.get("name", "photo.jpg")),
                data=data,
                mime=item.get("mime", "image/jpeg"),
                caption=item.get("caption", ""),
                api_data=b"",
            )
        )
    return photos


def to_note_text(text: str, photos: list[Photo]) -> str:
    """note に貼ったときに写真の位置が分かるテキスト。

    note の編集画面には画像を貼り付けできないので、
    「ここに写真1を入れる」という目印に置き換えておき、あとから写真をドラッグしてもらう。
    """
    by_index = {p.index: p for p in photos}

    def swap(match: re.Match[str]) -> str:
        photo = by_index.get(int(match.group(1)))
        if not photo:
            return match.group(0)
        label = photo.caption.strip() or photo.filename
        return f"📷 ここに写真{photo.index}（{label}）"

    return PATTERN.sub(swap, text)


def as_parts(photos: list[Photo]) -> list[tuple[bytes, str]]:
    """Gemini に渡す (バイト列, MIMEタイプ) の並び。縮小版を送る。"""
    return [(p.api_data, "image/jpeg") for p in photos]


# --- 表示・書き出し -------------------------------------------------------


def render(text: str, photos: list[Photo]) -> None:
    """[[写真N]] を実際の画像に置き換えて表示する。"""
    if not photos:
        st.markdown(text)
        return

    by_index = {p.index: p for p in photos}
    used: set[int] = set()
    cursor = 0

    for match in PATTERN.finditer(text):
        chunk = text[cursor : match.start()]
        if chunk.strip():
            st.markdown(chunk)
        number = int(match.group(1))
        photo = by_index.get(number)
        if photo:
            st.image(photo.data, caption=photo.caption or None, width="stretch")
            used.add(number)
        else:
            st.warning(f"{match.group(0)} に対応する写真がありません。", icon="⚠️")
        cursor = match.end()

    rest = text[cursor:]
    if rest.strip():
        st.markdown(rest)

    missing = [p for p in photos if p.index not in used]
    if missing:
        st.info(
            "本文に入らなかった写真: "
            + "、".join(p.marker for p in missing)
            + "　（下の「写真の位置を調整する」で、入れたい場所に目印を書き足せます）",
            icon="🖼️",
        )


def position_editor(state_key: str, tool_key: str, photos: list[Photo]) -> None:
    """[[写真N]] の位置を手で動かすための編集欄。"""
    if not photos:
        return
    with st.expander("🖼️ 写真の位置を調整する"):
        st.caption(
            "本文の中の "
            + "、".join(p.marker for p in photos)
            + " を、入れたい場所の行に移動すると、上のプレビューがすぐ切り替わります。"
        )
        edited = st.text_area(
            "本文",
            value=st.session_state.get(state_key, ""),
            height=320,
            key=f"edit::{tool_key}",
            label_visibility="collapsed",
        )
        if edited != st.session_state.get(state_key, ""):
            st.session_state[state_key] = edited
            st.rerun()


def to_markdown(text: str, photos: list[Photo]) -> str:
    """目印を Markdown の画像記法に置き換える。"""
    by_index = {p.index: p for p in photos}

    def swap(match: re.Match[str]) -> str:
        photo = by_index.get(int(match.group(1)))
        if not photo:
            return match.group(0)
        return f"![{photo.caption or photo.filename}](images/{photo.filename})"

    return PATTERN.sub(swap, text)


def to_zip(text: str, photos: list[Photo], *, basename: str = "article") -> bytes:
    """記事の Markdown と写真をまとめた ZIP を作る。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{basename}.md", to_markdown(text, photos))
        for photo in photos:
            archive.writestr(f"images/{photo.filename}", photo.data)
    return buffer.getvalue()
