"""生成結果をローカルの JSON ファイルに保存する簡易履歴。"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from .config import DATA_DIR

HISTORY_FILE = DATA_DIR / "history.json"
MAX_ENTRIES = 300


def _read() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(entries: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(entries[:MAX_ENTRIES], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load() -> list[dict[str, Any]]:
    """新しい順の履歴。"""
    return _read()


def add(tool: str, output: str, meta: dict[str, Any] | None = None) -> None:
    entries = _read()
    entries.insert(
        0,
        {
            "id": uuid.uuid4().hex[:12],
            "tool": tool,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "output": output,
            "meta": meta or {},
        },
    )
    _write(entries)


def delete(entry_id: str) -> None:
    _write([e for e in _read() if e.get("id") != entry_id])


def restore(entry: dict[str, Any]) -> None:
    """削除した履歴を元の位置に戻す。"""
    entries = _read()
    if any(e.get("id") == entry.get("id") for e in entries):
        return
    entries.append(entry)
    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    _write(entries)


def clear() -> None:
    _write([])


def tools() -> list[str]:
    """履歴に登場するツール名の一覧。"""
    seen: list[str] = []
    for entry in _read():
        tool = entry.get("tool", "")
        if tool and tool not in seen:
            seen.append(tool)
    return seen


# --- 生成した画像の保存 ---------------------------------------------------

IMAGE_DIR = DATA_DIR / "images"
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def save_image(data: bytes, mime: str) -> str:
    """画像を data/images/ に保存し、ファイル名を返す。"""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{_EXTENSIONS.get(mime, '.png')}"
    (IMAGE_DIR / name).write_bytes(data)
    return name


def save_photo(data: bytes, mime: str) -> str:
    """記事に添えた写真を保存する。

    内容のハッシュをファイル名にするので、同じ写真を何度使っても増えない。
    """
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"photo-{hashlib.sha1(data).hexdigest()[:16]}{_EXTENSIONS.get(mime, '.png')}"
    path = IMAGE_DIR / name
    if not path.is_file():
        path.write_bytes(data)
    return name


def image_bytes(name: str) -> bytes | None:
    """保存済み画像を読み出す。消されていれば None。"""
    path = IMAGE_DIR / name
    return path.read_bytes() if path.is_file() else None


def unused_images() -> list[str]:
    """どの履歴からも参照されていない画像ファイル名。"""
    if not IMAGE_DIR.is_dir():
        return []
    used = {
        name
        for entry in _read()
        for name in (entry.get("meta") or {}).get("images", [])
    }
    return sorted(p.name for p in IMAGE_DIR.iterdir() if p.is_file() and p.name not in used)


def delete_images(names: list[str]) -> int:
    """画像ファイルを削除して、消せた数を返す。"""
    removed = 0
    for name in names:
        path = IMAGE_DIR / name
        if path.is_file():
            path.unlink()
            removed += 1
    return removed
