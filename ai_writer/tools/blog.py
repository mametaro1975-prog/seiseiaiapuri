"""ブログ記事の構成づくりと執筆。"""

from __future__ import annotations

import streamlit as st

from ..core import gemini, prompts, ui
from ..core import photos as photolib

TOOL_KEY = "blog"
TOOL_LABEL = "ブログ記事"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは検索から流入するブログ記事を得意とするライターです。"
    "見出しは内容を具体的に示し、各セクションには実例・数字・手順など読者が使える情報を入れます。"
    "一般論の水増しや、同じ内容の言い換えによる文字数稼ぎは避けてください。"
)

# SEOモードのときに SYSTEM に上乗せする指示。
# キーワードの詰め込みではなく「検索した人の疑問がこの1ページで解決するか」を軸にしている。
SEO_SYSTEM = (
    "この記事は検索エンジン経由の流入を狙います。ただしキーワードを不自然に詰め込むことは"
    "逆効果なので絶対にしないでください。評価されるのは次の2点です。"
    "(a) 検索した人の疑問が、このページだけで最後まで解決すること。"
    "(b) 書き手にしか書けない一次情報（実体験・実際に試した結果・具体的な数字や事例）が入っていること。"
    "そのうえで必ず守ること: "
    "検索意図に対する結論を記事の冒頭で先に示す。"
    "見出しは、検索する人が実際に打ち込む言葉で書く。"
    "各見出しの直下2〜3文で、その見出しが立てた問いに先に答える。"
    "「〜が大切です」「人それぞれです」のような、読んでも行動が変わらない一般論を書かない。"
    "根拠のない数値や出典を捏造しない。数字を出せない箇所は書かないか〔要確認〕と明記する。"
)

# 検索意図ごとに、記事の骨格が変わる
SEARCH_INTENTS = {
    "知りたい（情報収集）": "用語や背景を、前提知識のない人にも分かるように定義から順に説明する",
    "やり方を知りたい（手順）": "手順を番号付きで示し、各手順につまずきやすい点とその対処を添える",
    "比べたい（比較検討）": "比較表を入れ、選ぶ基準と「こういう人にはこちらが向く」を明示する",
    "選びたい・買いたい（購入直前）": "選定基準、メリットだけでなくデメリットと向かない人まで正直に書く",
    "解決したい（トラブル）": "原因の切り分け手順を先に示し、原因ごとに対処を分けて書く",
}

# 本文に加えて出力させるパーツ
SEO_SECTIONS = {
    "タイトル案（32字以内）": "## タイトル案\n"
    "検索結果で途切れない32字以内の案を5つ。メインキーワードをなるべく前半に置く。"
    "煽り表現は使わず、記事の中身と一致させる",
    "メタディスクリプション": "## メタディスクリプション\n"
    "120字前後。検索結果に並んだときにクリックしたくなる要約を1つ",
    "結論の先出し（冒頭用）": "## この記事の結論\n"
    "本文の前に置く、3〜5行で結論だけを述べたブロック",
    "よくある質問（FAQ）": "## よくある質問\n"
    "この検索をする人が続けて調べる質問を4つ選び、それぞれ2〜3文で簡潔に答える",
    "内部リンク案": "## 内部リンク案\n"
    "この記事から繋げるべき別記事のテーマを3〜5個。アンカーテキストの案も添える",
}


def _system(seo: dict | None) -> str:
    """SEOモードのときだけ、システムプロンプトに SEO の層を足す。"""
    return SYSTEM + SEO_SYSTEM if seo else SYSTEM


def _seo_settings() -> dict | None:
    """SEO向けの追加設定。オフのときは None を返す。"""
    if not st.toggle("SEOを意識して書く", value=False, key="blog_seo"):
        return None

    with st.container(border=True):
        main_keyword = st.text_input(
            "メインキーワード（検索窓に打ち込まれる言葉）",
            placeholder="例: 在宅ワーク 集中できない",
        )
        intent = st.selectbox("検索した人が求めていること", list(SEARCH_INTENTS))
        strength = st.text_area(
            "自分だけが書ける材料（一次情報）",
            height=80,
            placeholder="例: 3年間の在宅勤務で試した5つの方法と、続かなかった理由。作業ログの実データあり。",
            help="ここが埋まっているほど、ありきたりでない記事になります。",
        )
        sections = st.multiselect(
            "本文と一緒に出力するもの",
            list(SEO_SECTIONS),
            default=["タイトル案（32字以内）", "メタディスクリプション", "よくある質問（FAQ）"],
        )
    return {
        "main_keyword": main_keyword,
        "intent": intent,
        "strength": strength,
        "sections": sections,
    }


def _conditions(theme, keywords, audience, tone, length, extra, seo=None) -> str:
    target, low, high = length
    seo_rules: list[str] = []
    if seo:
        if seo["main_keyword"].strip():
            seo_rules += [
                f"メインキーワードは「{seo['main_keyword'].strip()}」。"
                "タイトル・導入の1文目・見出しのいずれかに自然な形で入れる",
                "同じキーワードを本文で繰り返し過ぎない。文章として不自然になるくらいなら入れない",
            ]
        seo_rules += [
            SEARCH_INTENTS[seo["intent"]],
            "各見出しの直下2〜3文で、その見出しの問いに先に答える",
            "冒頭に検索意図に対する結論を先に置く",
        ]
        if keywords and keywords.strip():
            seo_rules.append("関連キーワードは、意味が通る箇所にだけ使う。全部を無理に入れない")

    return prompts.build(
        prompts.block("記事のテーマ", theme),
        prompts.block("メインキーワード", seo["main_keyword"] if seo else ""),
        prompts.block("関連キーワード", keywords),
        prompts.block("想定読者", audience),
        prompts.block("この記事だけが持つ材料（必ず本文に活かす）", seo["strength"] if seo else ""),
        prompts.block("追加の指示", extra),
        prompts.rules(
            f"文体は「{tone}」で統一する",
            *seo_rules,
            *prompts.length_rules(
                target,
                low,
                high,
                unit="本文（タイトル案やFAQなどの付随パーツを除く）" if seo else "記事全体",
                sections=prompts.suggest_sections(target),
            ),
            "Markdown で書き、見出しは ## と ### を使う",
            "冒頭に読者の悩みに触れるリード文を置く",
            "最後にまとめと、読者が次に取る行動を書く",
        ),
    )


def render() -> None:
    ui.page_header("📝", "ブログ記事作成", "テーマから構成案を作り、その構成に沿って本文を書きます。")
    if not ui.api_key_guard():
        return

    theme = st.text_input("テーマ・タイトル案", placeholder="例: 在宅ワークで集中力を保つ方法")
    col1, col2 = st.columns(2)
    keywords = col1.text_input("キーワード（カンマ区切り）", placeholder="在宅ワーク, 集中力, ポモドーロ")
    audience = col2.text_input("想定読者", placeholder="例: 在宅勤務を始めたばかりの会社員")

    tone = st.selectbox("文体", prompts.TONES)
    length = ui.length_picker("blog", default=2500, minimum=300, maximum=20000)
    extra = st.text_area(
        "追加の指示（任意）",
        placeholder="例: 自分の体験談を交えて。専門用語は使わない。",
        height=80,
    )

    st.divider()
    seo = _seo_settings()

    st.divider()
    photos = photolib.uploader("blog")

    st.divider()
    step1, step2 = st.columns(2)
    make_outline = step1.button("① 構成案を作る", width="stretch")
    write_article = step2.button("② この構成で記事を書く", type="primary", width="stretch")

    if make_outline:
        if not theme.strip():
            st.warning("テーマを入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                "次の条件でブログ記事の構成案（見出しと各セクションの要点）だけを作ってください。本文は書かないでください。",
                "",
                _conditions(theme, keywords, audience, tone, length, extra, seo),
            )
            try:
                with st.spinner("構成案を考えています…"):
                    st.session_state["blog_outline"] = gemini.generate_text(
                        prompt, system_instruction=_system(seo)
                    )
            except gemini.GeminiError as exc:
                st.error(str(exc), icon="🚫")

    outline = st.text_area(
        "構成案（自由に書き換えてから②を押せます）",
        key="blog_outline",
        height=260,
        placeholder="①を押すと構成案が入ります。自分で書いた構成を貼り付けてもOKです。",
    )

    prompt = None
    if write_article:
        if not theme.strip():
            st.warning("テーマを入力してください。", icon="⚠️")
        else:
            instruction = "次の条件と構成案にもとづいて、ブログ記事の本文を最後まで書いてください。"
            structure = ""
            if seo and seo["sections"]:
                instruction = (
                    "次の条件と構成案にもとづいて記事一式を作ってください。"
                    "出力は以下の見出しをこの順に使い、指示どおりの中身を書きます。"
                )
                order = [SEO_SECTIONS[name] for name in SEO_SECTIONS if name in seo["sections"]]
                # 「結論の先出し」は本文の直前、それ以外の後付けパーツは本文の後ろに置く
                before = [b for b in order if b.startswith("## この記事の結論")]
                after = [b for b in order if not b.startswith("## この記事の結論")]
                head = [b for b in after if b.startswith(("## タイトル案", "## メタディスクリプション"))]
                tail = [b for b in after if b not in head]
                structure = "\n\n".join(
                    head + before + ["## 本文\n記事の本文。ここが中心なので最も厚く書く"] + tail
                )

            prompt = prompts.build(
                instruction,
                "",
                structure,
                "",
                _conditions(theme, keywords, audience, tone, length, extra, seo),
                prompts.block("構成案", outline or "（構成案なし。適切な構成を自分で決めてよい）"),
                photolib.prompt_block(photos),
                prompts.rules(*photolib.prompt_rules(photos), label="写真の入れ方"),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=_system(seo),
        length=length,
        photos=photos,
        meta={
            "テーマ": theme,
            "文体": tone,
            "分量": f"{length[0]:,}字",
            **({"写真": f"{len(photos)}枚"} if photos else {}),
            **({"SEO": seo["main_keyword"] or "あり"} if seo else {}),
        },
    )
