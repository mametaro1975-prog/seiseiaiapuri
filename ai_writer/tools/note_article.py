"""note 向けの記事作成。"""

from __future__ import annotations

import streamlit as st

from ..core import gemini, prompts, ui
from ..core import photos as photolib

TOOL_KEY = "note"
TOOL_LABEL = "note記事"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは note で読まれる記事を書き慣れたライターです。"
    "note の読者は、書き手個人の視点・実感・失敗談に価値を感じます。"
    "検索対策のための水増しやテンプレ的な言い回しは避け、"
    "一人の人間が語っていると感じられる文章を書いてください。"
    "装飾は控えめにし、見出し・改行・余白で読みやすさを作ります。"
)

ARTICLE_TYPES = {
    "体験談・エッセイ": "実際の出来事を時系列で語り、そのとき何を感じ何を学んだかを軸にする",
    "ノウハウ・やり方": "読者がそのまま真似できる手順を示す。つまずきやすい点も書く",
    "考察・オピニオン": "主張を先に置き、根拠と反論への配慮を添えて論じる",
    "まとめ・紹介": "選んだ基準を明示し、それぞれの良さと向き不向きを書く",
    "告知・宣伝": "売り込み口調にせず、相手にとっての価値と背景の物語を伝える",
    "日記・記録": "その日の出来事と気持ちを、飾らない言葉で書く",
}

PERSONS = ["私", "僕", "俺", "自分", "わたし", "指定しない"]

# note は Google 検索と note 内（検索・おすすめ・ハッシュタグ）の両方から読まれる。
# 両方に効かせつつ、note らしい語り口を壊さないための指示。
SEO_SYSTEM = (
    "この記事は Google 検索と note 内の両方から読まれることを狙います。"
    "ただし、検索対策のためにキーワードを不自然に詰め込むことは逆効果なので絶対にしないでください。"
    "note で読まれる記事は、検索で答えを得られるだけでなく、"
    "書き手の実体験が具体的で、最後まで読ませる語りになっているものです。両方を満たしてください。"
    "そのうえで必ず守ること: "
    "冒頭2〜3行に、記事一覧やSNSで切り取られても内容と魅力が伝わる文を置く。"
    "検索した人が知りたい答えを、記事の前半で出し惜しみせずに書く。"
    "見出しは、検索する人が実際に打ち込む言葉に寄せつつ、note の記事として不自然にならない表現にする。"
    "「〜が大切です」「人それぞれです」のような、読んでも行動が変わらない一般論を書かない。"
    "根拠のない数値や出典を捏造しない。数字を出せない箇所は書かないか〔要確認〕と明記する。"
    "体験を語る部分では、抽象的な感想ではなく、そのとき何が起きて何をしたかを具体的に書く。"
)

# 検索意図ごとに記事の骨格を変える
SEARCH_INTENTS = {
    "知りたい（情報収集）": "背景や前提を、知識のない人にも分かるように順を追って説明する",
    "やり方を知りたい（手順）": "手順を番号付きで示し、各手順に自分がつまずいた点とその対処を添える",
    "体験談を読みたい": "時系列で出来事を追い、判断の理由と、そのとき何を感じたかを具体的に書く",
    "比べたい（比較検討）": "比較表を入れ、選ぶ基準と「こういう人にはこちらが向く」を明示する",
    "解決したい（トラブル）": "原因の切り分けを先に示し、原因ごとに対処を分けて書く",
}

# 本文に加えて出力させる note 向けのパーツ。("head" は本文の前、"tail" は本文の後ろ)
NOTE_SEO_SECTIONS = {
    "記事の紹介文（noteの設定用）": (
        "head",
        "## 記事の紹介文\n"
        "note の「記事の設定」に入れる紹介文。100字前後。"
        "検索結果とSNSシェアの両方で効くように、記事を読むと何が得られるかを書く",
    ),
    "冒頭の掴み（3案）": (
        "head",
        "## 冒頭の掴み（3案）\n"
        "記事一覧に表示される最初の2〜3行の案を3つ。"
        "それぞれ違う入り方（具体的な場面 / 問いかけ / 意外な事実）にする",
    ),
    "この記事の結論（前半に置く）": (
        "head",
        "## この記事の結論\n本文の前半に置く、3〜5行で結論だけを述べたブロック",
    ),
    "よくある質問（FAQ）": (
        "tail",
        "## よくある質問\n"
        "このテーマで続けて調べられる質問を3〜4つ選び、それぞれ2〜3文で答える",
    ),
}


def _system(seo: dict | None) -> str:
    """SEOモードのときだけ、システムプロンプトに SEO の層を足す。"""
    return SYSTEM + SEO_SYSTEM if seo else SYSTEM


def _seo_settings() -> dict | None:
    """検索も意識したいときの追加設定。オフのときは None を返す。"""
    if not st.toggle("検索からの流入も意識する", value=False, key="note_seo"):
        return None

    with st.container(border=True):
        main_keyword = st.text_input(
            "メインキーワード（検索窓に打ち込まれる言葉）",
            placeholder="例: 在宅ワーク 生活リズム 崩れる",
        )
        intent = st.selectbox("読む人が求めていること", list(SEARCH_INTENTS))
        sections = st.multiselect(
            "本文と一緒に出力するもの",
            list(NOTE_SEO_SECTIONS),
            default=["記事の紹介文（noteの設定用）", "冒頭の掴み（3案）"],
        )
        st.caption(
            "note は「素材メモ」に書いた実体験そのものが強みになります。"
            "検索対策より、そこを具体的に書くほうが効きます。"
        )
    return {"main_keyword": main_keyword, "intent": intent, "sections": sections}


def render() -> None:
    ui.page_header("🖊️", "note記事作成", "メモや体験から、note で読まれる語り口の記事を書きます。")
    if not ui.api_key_guard():
        return

    title = st.text_input("タイトル・書きたいこと", placeholder="例: 会社を辞めて在宅ワークに切り替えた話")
    material = st.text_area(
        "素材メモ（箇条書き・思いつきでOK）",
        height=200,
        placeholder="・辞めた直接のきっかけは通勤時間\n"
        "・最初の3ヶ月は生活リズムが崩れて失敗\n"
        "・朝の散歩を入れたら安定した\n"
        "・収入は一時的に下がった",
    )

    col1, col2 = st.columns(2)
    article_type = col1.selectbox("記事のタイプ", list(ARTICLE_TYPES))
    tone = col2.selectbox("文体", prompts.TONES, index=1)

    person = st.selectbox("一人称", PERSONS)
    length = ui.length_picker("note", default=3000, minimum=300, maximum=20000)

    audience = st.text_input("読んでほしい人（任意）", placeholder="例: 会社を辞めるか迷っている人")

    col5, col6 = st.columns(2)
    with_titles = col5.toggle("タイトル案も出す", value=True)
    with_tags = col6.toggle("ハッシュタグを提案する", value=True)

    paywall = st.toggle("有料エリアの区切りを提案する", value=False)
    extra = st.text_area(
        "追加の指示（任意）",
        height=80,
        placeholder="例: 説教くさくしない。数字は正確に。読者への問いかけで終わる。",
    )

    st.divider()
    seo = _seo_settings()

    st.divider()
    photos = photolib.uploader("note")

    st.divider()
    step1, step2 = st.columns(2)
    make_outline = step1.button("① 構成を考える", width="stretch")
    write = step2.button("② 記事を書く", type="primary", width="stretch")

    seo_rules: list[str] = []
    if seo:
        if seo["main_keyword"].strip():
            seo_rules += [
                f"メインキーワードは「{seo['main_keyword'].strip()}」。"
                "タイトル・冒頭2〜3行・見出しのいずれかに、読んで不自然でない形で入れる",
                "同じキーワードを本文で繰り返し過ぎない。語りとして不自然になるくらいなら入れない",
            ]
        seo_rules += [
            SEARCH_INTENTS[seo["intent"]],
            "検索した人が知りたい答えを、記事の前半で出し惜しみせずに書く",
        ]

    base = prompts.build(
        prompts.block("タイトル・テーマ", title),
        prompts.block("メインキーワード", seo["main_keyword"] if seo else ""),
        prompts.block("素材メモ", material),
        prompts.block("読んでほしい人", audience),
        prompts.block("追加の指示", extra),
        prompts.rules(
            ARTICLE_TYPES[article_type],
            f"文体は「{tone}」",
            *seo_rules,
            f"一人称は「{person}」で統一する" if person != "指定しない" else "一人称は素材メモに合わせる",
            *prompts.length_rules(
                length[0],
                length[1],
                length[2],
                unit="本文（タイトル案や紹介文などの付随パーツを除く）" if seo else "本文",
                sections=prompts.suggest_sections(length[0]),
            ),
            "素材メモにない出来事や数字を作らない。膨らませるのは描写と考察だけ",
        ),
    )

    if make_outline:
        if not title.strip() and not material.strip():
            st.warning("タイトルか素材メモのどちらかは入力してください。", icon="⚠️")
        else:
            prompt = prompts.build(
                "次の材料から note 記事の構成（書き出し・見出し・各パートで書くこと・締め）を考えてください。"
                "本文は書かず、構成だけを出してください。",
                "",
                base,
            )
            try:
                with st.spinner("構成を考えています…"):
                    st.session_state["note_outline"] = gemini.generate_text(
                        prompt, system_instruction=_system(seo)
                    )
            except gemini.GeminiError as exc:
                st.error(str(exc), icon="🚫")

    outline = st.text_area(
        "構成（書き換えてから②を押せます）",
        key="note_outline",
        height=220,
        placeholder="①を押すと構成が入ります。空のまま②を押しても書けます。",
    )

    prompt = None
    if write:
        if not title.strip() and not material.strip():
            st.warning("タイトルか素材メモのどちらかは入力してください。", icon="⚠️")
        else:
            title_part = (
                "## タイトル案（5つ）\n32字以内。メインキーワードをなるべく前半に置きつつ、"
                "note のタイムラインで見ても引きがある表現にする"
                if seo
                else "## タイトル案（5つ）"
            )
            tag_part = (
                "## ハッシュタグ案\nnote 内でよく使われる大きめのタグを2〜3個と、"
                "内容を具体的に示す小さめのタグを3〜5個、組み合わせて出す"
                if seo
                else "## ハッシュタグ案（5〜8個）"
            )
            seo_parts = (
                [NOTE_SEO_SECTIONS[name] for name in NOTE_SEO_SECTIONS if name in seo["sections"]]
                if seo
                else []
            )
            structure = [title_part] if with_titles else []
            structure += [body for place, body in seo_parts if place == "head"]
            structure += ["## 本文"]
            structure += [body for place, body in seo_parts if place == "tail"]
            if with_tags:
                structure += [tag_part]
            prompt = prompts.build(
                "次の材料から note の記事を書いてください。出力は以下の見出しの順に構成します。",
                "",
                "\n\n".join(structure),
                "",
                base,
                prompts.block("構成", outline),
                photolib.prompt_block(photos),
                prompts.rules(
                    *photolib.prompt_rules(photos),
                    "冒頭の3行で、読者が「これは自分の話だ」と感じる具体的な場面から入る",
                    "見出しは ## を使い、5〜10行ごとに空行を入れて読みやすくする",
                    "一般論で締めず、書き手自身の結論と、読者への問いかけで終える",
                    "有料エリアを設けるなら、本文中の適切な位置に「---（ここから有料エリア）---」を1か所入れ、"
                    "無料部分だけでも価値が伝わるようにする" if paywall else "有料エリアの区切りは入れない",
                    label="本文の書き方",
                ),
            )

    ui.render_output(
        TOOL_KEY,
        TOOL_LABEL,
        prompt=prompt,
        system=_system(seo),
        length=length,
        photos=photos,
        meta={
            "タイプ": article_type,
            "文体": tone,
            "分量": f"{length[0]:,}字",
            **({"写真": f"{len(photos)}枚"} if photos else {}),
            **({"検索": seo["main_keyword"] or "あり"} if seo else {}),
        },
    )
