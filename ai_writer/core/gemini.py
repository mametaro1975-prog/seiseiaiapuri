"""Gemini API の薄いラッパー。"""

from __future__ import annotations

from collections.abc import Iterator

import streamlit as st
from google import genai
from google.genai import types

from . import config


class GeminiError(RuntimeError):
    """UI にそのまま出せる日本語のエラー。"""


@st.cache_resource(show_spinner=False)
def _client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def _build_config(
    settings: config.Settings,
    system_instruction: str | None,
    max_output_tokens: int | None,
) -> types.GenerateContentConfig:
    kwargs: dict = {
        "temperature": settings.temperature,
        # ツールは使わないので、自動関数呼び出しの警告が出ないよう明示的に無効化する
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
    }
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    if settings.fast_mode and "flash" in settings.model:
        # Flash 系のみ思考をオフにできる（Pro は常に思考する）
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def _friendly(exc: Exception, model: str = "", *, with_models: bool = True) -> GeminiError:
    """API の例外を、原因が分かる日本語メッセージに変える。

    原因の切り分けができるよう、API が返した生のメッセージも必ず末尾に残す。
    """
    message = str(exc)
    detail = f"\n\n詳細: {message[:400]}"
    where = f"モデル「{model}」" if model else "指定したモデル"

    if "API key not valid" in message or "API_KEY_INVALID" in message:
        return GeminiError("APIキーが正しくないようです。サイドバーで確認してください。" + detail)
    if "RESOURCE_EXHAUSTED" in message or "429" in message:
        return GeminiError(
            "APIの利用上限に達しました。しばらく待つか、軽いモデルに変えてください。" + detail
        )
    if "PERMISSION_DENIED" in message or "403" in message:
        return GeminiError(
            f"{where}を使う権限がありません。APIキーを発行したプロジェクトで "
            "Generative Language API が有効か確認してください。" + detail
        )
    if "NOT_FOUND" in message or "404" in message:
        return GeminiError(
            f"{where}は、このAPIキーでは使えません。"
            "サイドバーで下のモデルに変えてください。"
            + (_available_listing() if with_models else "")
            + detail
        )
    return GeminiError(f"生成に失敗しました。{detail}")


def _available_listing(limit: int = 12) -> str:
    """404 のときに、実際に使えるモデルをその場に並べる。"""
    try:
        models = text_models(config.current().api_key)
    except Exception:  # noqa: BLE001 - 一覧が引けなくても本来のエラーは伝える
        return ""
    if not models:
        return ""
    shown = "\n".join(f"　・{m}" for m in models[:limit])
    more = f"\n　…ほか {len(models) - limit} 個" if len(models) > limit else ""
    return f"\n\n使えるモデル:\n{shown}{more}"


# --- 使えるモデルの取得 ---------------------------------------------------

# 表示のときに添える短い説明（一覧に出てきたものだけ使う）
MODEL_NOTES: dict[str, str] = {
    "gemini-2.5-flash": "速い・普段づかい",
    "gemini-2.5-pro": "賢い・長文向き",
    "gemini-2.5-flash-lite": "最速・軽い作業",
    "gemini-2.0-flash": "ひと世代前・安定",
    "gemini-3-pro-preview": "最上位",
    "gemini-3-flash-preview": "新しい高速モデル",
}
# 一覧の先頭に置きたい順番
PREFERRED = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.0-flash",
]
# 文章生成には使わないモデル
_EXCLUDE = ("embedding", "aqa", "imagen", "veo", "tts", "-image", "learnlm", "gemma")


@st.cache_data(show_spinner=False, ttl=3600)
def _list_models(api_key: str) -> tuple[list[str], str]:
    """(使えるモデルID, エラーメッセージ) を返す。

    失敗もキャッシュしたいので例外は投げない。投げると毎回の再実行で
    ネットワーク呼び出しが走り、サイドバーが重くなる。
    """
    try:
        models = [
            model.name.removeprefix("models/")
            for model in _client(api_key).models.list()
            if model.name and "generateContent" in (model.supported_actions or [])
        ]
    except Exception as exc:  # noqa: BLE001
        return [], str(_friendly(exc, with_models=False))
    return models, ""


def _sorted(models: list[str]) -> list[str]:
    head = [m for m in PREFERRED if m in models]
    tail = sorted(m for m in models if m not in head)
    return head + tail


def text_models(api_key: str) -> list[str]:
    """文章生成に使えるモデルの一覧。取得できなければ空リスト。"""
    models, _ = _list_models(api_key)
    return _sorted([m for m in models if not any(x in m for x in _EXCLUDE)])


def image_models(api_key: str) -> list[str]:
    """画像生成に使えるモデルの一覧。取得できなければ空リスト。"""
    models, _ = _list_models(api_key)
    return sorted(m for m in models if "image" in m and "embedding" not in m)


def probe(api_key: str) -> tuple[bool, str]:
    """接続テスト。(成功したか, 表示するメッセージ) を返す。"""
    _list_models.clear()
    models, error = _list_models(api_key)
    if error:
        return False, error
    if not models:
        return False, "接続できましたが、使えるモデルが1つも見つかりませんでした。"
    return True, "\n".join(f"- `{m}`" for m in models)


def stream_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    max_output_tokens: int | None = None,
    images: list[tuple[bytes, str]] | None = None,
) -> Iterator[str]:
    """本文を少しずつ返すジェネレータ。st.write_stream にそのまま渡せる。

    images を渡すと、その画像を見たうえで文章を書かせられる。
    """
    settings = config.current()
    if not settings.ready:
        raise GeminiError("APIキーが未設定です。サイドバーから入力してください。")

    contents: object = prompt
    if images:
        contents = [types.Part(text=prompt)] + [
            types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images
        ]

    try:
        stream = _client(settings.api_key).models.generate_content_stream(
            model=settings.model,
            contents=contents,
            config=_build_config(settings, system_instruction, max_output_tokens),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except GeminiError:
        raise
    except Exception as exc:  # noqa: BLE001 - API 由来の例外は種類が多い
        raise _friendly(exc, settings.model) from exc


def generate_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    max_output_tokens: int | None = None,
    images: list[tuple[bytes, str]] | None = None,
) -> str:
    """一括で結果を受け取る版。"""
    return "".join(
        stream_text(
            prompt,
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            images=images,
        )
    )


def chat_stream(messages: list[dict], *, system_instruction: str | None = None) -> Iterator[str]:
    """会話履歴つきの生成。messages は {"role": "user"|"assistant", "content": str}。"""
    settings = config.current()
    if not settings.ready:
        raise GeminiError("APIキーが未設定です。サイドバーから入力してください。")

    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    try:
        stream = _client(settings.api_key).models.generate_content_stream(
            model=settings.model,
            contents=contents,
            config=_build_config(settings, system_instruction, None),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc, settings.model) from exc


# --- 画像生成 -------------------------------------------------------------

IMAGE_MODELS: dict[str, str] = {
    "Nano Banana Pro（文字がきれい・高品質）": "gemini-3-pro-image-preview",
    "Nano Banana（速い・軽い）": "gemini-2.5-flash-image",
}
DEFAULT_IMAGE_MODEL_LABEL = "Nano Banana Pro（文字がきれい・高品質）"


def generate_image(
    prompt: str,
    *,
    model: str,
    aspect_ratio: str = "16:9",
    image_size: str = "2K",
) -> tuple[list[tuple[bytes, str]], str]:
    """画像を生成して [(バイト列, MIMEタイプ), ...] と補足テキストを返す。"""
    settings = config.current()
    if not settings.ready:
        raise GeminiError("APIキーが未設定です。サイドバーから入力してください。")

    try:
        response = _client(settings.api_key).models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc, model) from exc

    images: list[tuple[bytes, str]] = []
    notes: list[str] = []
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            if part.inline_data and part.inline_data.data:
                images.append(
                    (part.inline_data.data, part.inline_data.mime_type or "image/png")
                )
            elif part.text:
                notes.append(part.text)

    if not images:
        reason = " ".join(notes).strip()
        raise GeminiError(
            "画像が生成されませんでした。" + (f"モデルの応答: {reason[:200]}" if reason else
            "指示の内容を変えて、もう一度試してください。")
        )
    return images, "\n".join(notes).strip()
