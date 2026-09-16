"""アプリ全体の設定と、APIキー・モデル設定の受け渡し。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"

load_dotenv(APP_ROOT / ".env")

APP_TITLE = "AI ライティングツール"
APP_ICON = "✍️"

# 表示名 -> モデルID
MODELS: dict[str, str] = {
    "Gemini 2.5 Flash（速い・普段づかい）": "gemini-2.5-flash",
    "Gemini 2.5 Pro（賢い・長文向き）": "gemini-2.5-pro",
    "Gemini 2.5 Flash-Lite（最速・軽い作業）": "gemini-2.5-flash-lite",
}
DEFAULT_MODEL_LABEL = "Gemini 2.5 Flash（速い・普段づかい）"


@dataclass(frozen=True)
class Settings:
    """サイドバーで選んだ生成条件。"""

    api_key: str
    model: str
    temperature: float
    fast_mode: bool

    @property
    def ready(self) -> bool:
        return bool(self.api_key)


def env_api_key() -> str:
    """.env / 環境変数 / secrets.toml から APIキーを探す。"""
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    try:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            if name in st.secrets:
                return str(st.secrets[name]).strip()
    except Exception:
        # secrets.toml が無い環境では st.secrets へのアクセスが例外になる
        pass
    return ""


def current() -> Settings:
    """いま有効な設定を返す。サイドバー未描画でも安全に呼べる。"""
    return Settings(
        api_key=st.session_state.get("api_key") or env_api_key(),
        model=st.session_state.get("model_id", MODELS[DEFAULT_MODEL_LABEL]),
        temperature=float(st.session_state.get("temperature", 0.7)),
        fast_mode=bool(st.session_state.get("fast_mode", False)),
    )
