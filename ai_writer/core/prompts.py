"""プロンプトを組み立てるための共通部品。"""

from __future__ import annotations

BASE_SYSTEM = (
    "あなたは日本語のプロのライター兼編集者です。"
    "読み手にとって価値のある、具体的で自然な日本語を書きます。"
    "指示された条件（文体・長さ・形式）は必ず守ってください。"
    "前置きや「承知しました」などの返事は書かず、成果物だけを出力します。"
    "事実が不確かな箇所は断定せず、必要なら〔要確認〕と明記してください。"
)

TONES = [
    "丁寧・ですます調",
    "カジュアル・親しみやすい",
    "ビジネス・簡潔",
    "専門的・論理的",
    "熱量高め・エモーショナル",
    "やさしく噛み砕いた説明",
]


def block(label: str, value: str | None) -> str:
    """値があるときだけ見出しつきのブロックにする。"""
    if not value or not str(value).strip():
        return ""
    return f"# {label}\n{str(value).strip()}\n\n"


def build(*parts: str) -> str:
    """空でないブロックだけを、改行を挟んでつなげる。"""
    return "\n".join(p for p in parts if p and p.strip()).strip()


def rules(*lines: str, label: str = "守ること") -> str:
    """守ってほしい条件を箇条書きにまとめる。

    1つのプロンプトに条件のまとまりが2つ以上あるときは label を変えて区別する。
    """
    body = "\n".join(f"- {line}" for line in lines if line)
    return block(label, body)


def length_rules(
    target: int,
    low: int,
    high: int,
    *,
    unit: str = "全体",
    sections: int | None = None,
) -> list[str]:
    """文字数を守らせるための指示。prompts.rules(*length_rules(...)) の形で使う。"""
    lines = [
        f"{unit}の文字数は約 {target:,} 字（{low:,}〜{high:,} 字）に収める。この範囲は必ず守る",
        "文字数には見出し・箇条書き・記号もすべて含めて数える",
        "書き終えたら文字数を数え、範囲から外れていれば加筆または削除して調整してから出力する",
        "文字数を埋めるための同じ内容の繰り返しや、意味のない前置きは書かない",
    ]
    if sections:
        lines.insert(
            1,
            f"目安として大見出しを {sections} 個ほど立て、1つのセクションにつき"
            f"約 {target // sections:,} 字を配分する",
        )
    return lines


def suggest_sections(target: int) -> int:
    """文字数から見出しの本数の目安を出す。"""
    return max(2, min(8, round(target / 700)))
