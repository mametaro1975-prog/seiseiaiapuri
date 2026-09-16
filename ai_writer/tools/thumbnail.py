"""note・ブログ・SNS 向けのサムネイル画像を作る。"""

from __future__ import annotations

import streamlit as st

from ..core import config, gemini, history, prompts, ui

TOOL_KEY = "thumbnail"
TOOL_LABEL = "サムネイル"
STATE_IMAGES = "thumb_images"

SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたはサムネイル・アイキャッチ画像のアートディレクターです。"
    "媒体ごとの表示サイズと閲覧環境（スマホの小さな一覧、タイムラインでの流し見）を前提に、"
    "一瞬で内容が伝わる構図と文字量を設計します。"
)

# 媒体ごとの比率・推奨サイズ・デザインの勘所
PRESETS: dict[str, dict[str, str]] = {
    "note（記事の見出し画像）": {
        "ratio": "16:9",
        "size": "1280×670px",
        "notes": "note の記事一覧と記事上部に表示される。文字は少なめか無しでもよく、"
        "記事の空気感が伝わる落ち着いたビジュアルが好まれる。装飾は控えめに、余白を広く取る。",
    },
    "ブログのアイキャッチ（OGP）": {
        "ratio": "16:9",
        "size": "1200×630px",
        "notes": "SNS でシェアされたとき小さく表示される。記事タイトルの要点を、"
        "太く大きな文字で2〜8語程度に絞って入れる。背景と文字のコントラストを強くする。",
    },
    "X（旧Twitter）": {
        "ratio": "16:9",
        "size": "1200×675px",
        "notes": "タイムラインを流し見されるため、スマホで親指サイズでも読める文字量にする。"
        "情報は1つに絞り、要素を詰め込まない。",
    },
    "Instagram（正方形フィード）": {
        "ratio": "1:1",
        "size": "1080×1080px",
        "notes": "ビジュアルの美しさが最優先。文字は少なく、余白と配色の統一感を重視する。"
        "プロフィール上で並んだときに調和するトーンにする。",
    },
    "Instagram（縦長フィード）": {
        "ratio": "4:5",
        "size": "1080×1350px",
        "notes": "縦に大きく表示される。上下に余白を取り、中央に主題を置く。文字は少なめに。",
    },
    "ストーリーズ・リール・TikTok": {
        "ratio": "9:16",
        "size": "1080×1920px",
        "notes": "全画面の縦長。上下2割は UI に隠れるため、重要な要素は中央に置く。",
    },
    "YouTube サムネイル": {
        "ratio": "16:9",
        "size": "1280×720px",
        "notes": "一覧で強く目を引く必要がある。文字は極太で最大3〜6語、彩度とコントラストを高く、"
        "表情や感情がはっきり伝わる構図にする。",
    },
    "その他（比率を自分で指定）": {
        "ratio": "16:9",
        "size": "指定なし",
        "notes": "汎用のビジュアル。主題を中央に、余白を確保する。",
    },
}

RATIOS = ["16:9", "4:3", "3:2", "1:1", "4:5", "3:4", "2:3", "9:16", "21:9"]

STYLES = {
    "写真風・リアル": "実写写真のような自然光とディテール。人工的な加工感を出さない",
    "イラスト（フラット）": "均一な色面とシンプルな形の、フラットなベクターイラスト",
    "イラスト（手描き風）": "手描きの線と、少しかすれた質感のあるイラスト",
    "水彩・やわらかい": "水彩絵の具のにじみとやわらかい色合い",
    "ミニマル・余白重視": "要素を極限まで減らし、余白と1つの図形・オブジェクトで見せる",
    "ポップ・目立たせる": "彩度の高い配色と太い縁取りで、遠目にも目を引く",
    "高級感・落ち着き": "低彩度の配色と繊細な質感で、静かで上質な印象",
    "テック・未来的": "暗い背景に光のアクセント、グリッドや幾何学模様",
    "レトロ・ヴィンテージ": "褪せた色味と粒状感のある、昔の印刷物のような質感",
}

COLORS = [
    "おまかせ",
    "青系（信頼・落ち着き）",
    "暖色系（親しみ・活気）",
    "モノトーン（無彩色）",
    "パステル（やわらかい）",
    "ビビッド（鮮やか）",
    "アースカラー（自然・木や土）",
    "ダーク（黒背景・高コントラスト）",
]

PEOPLE = ["人物は入れない", "シルエットや後ろ姿", "イラストの人物", "実写風の人物"]


def _preset(name: str) -> dict[str, str]:
    return PRESETS[name]


def _design_prompt(platform, subject, main_text, sub_text, style, color, people, extra) -> str:
    preset = _preset(platform)
    return prompts.build(
        f"{platform} 用のサムネイル画像のデザイン案を3つ考えてください。",
        "",
        prompts.block("記事・投稿の内容", subject),
        prompts.block("入れたい文字", f"メイン: {main_text}\nサブ: {sub_text}" if main_text or sub_text else ""),
        prompts.block("媒体の特性", f"{preset['size']}（{preset['ratio']}）。{preset['notes']}"),
        prompts.block("追加の希望", extra),
        prompts.rules(
            f"テイストは「{style}」",
            f"配色は「{color}」",
            people,
            "案ごとに「## 案1: （ひとことコンセプト）」の見出しを付ける",
            "各案には「構図」「文字（実際に入れる文言）」「配色」「なぜ目を引くか」を書く",
            "最後に「## 画像生成用プロンプト」として、各案をそのまま画像生成 AI に渡せる"
            "日本語のプロンプトにまとめる",
        ),
    )


def _image_prompt(platform, subject, main_text, sub_text, style, color, people, extra) -> str:
    preset = _preset(platform)
    lines = [
        f"{platform}用のサムネイル画像を1枚デザインしてください。",
        f"サイズ感: {preset['size']}（アスペクト比 {preset['ratio']}）。",
        f"媒体の特性: {preset['notes']}",
        "",
        f"画像の主題: {subject}",
        f"テイスト: {STYLES[style]}",
        f"配色: {color}",
        f"人物: {people}",
    ]
    if main_text.strip():
        lines += [
            "",
            "画像内に次の日本語テキストを、誤字なく正確に大きく配置してください。",
            f'メインの文字: 「{main_text.strip()}」',
        ]
        if sub_text.strip():
            lines.append(f'サブの文字（メインより小さく）: 「{sub_text.strip()}」')
        lines += [
            "文字は読みやすいゴシック体で、背景と十分なコントラストを付けてください。",
            "指定した文字以外の文字・ロゴ・透かしは一切入れないでください。",
        ]
    else:
        lines += ["", "画像内に文字は一切入れず、ビジュアルだけで内容を伝えてください。"]

    if extra.strip():
        lines += ["", f"追加の希望: {extra.strip()}"]

    lines += [
        "",
        "端に重要な要素を置かず、縮小表示されても内容が分かる構図にしてください。",
    ]
    return "\n".join(lines)


def _render_saved_images() -> None:
    saved = st.session_state.get(STATE_IMAGES, [])
    if not saved:
        return
    st.subheader("生成された画像")
    for index, item in enumerate(saved, start=1):
        data = history.image_bytes(item["name"])
        if data is None:
            continue
        st.image(data, caption=f"案 {index}（{item['ratio']} / {item['platform']}）", width="stretch")
        st.download_button(
            f"⬇️ 案 {index} をダウンロード",
            data=data,
            file_name=item["name"],
            mime=item["mime"],
            key=f"thumbdl::{item['name']}",
            width="stretch",
        )
    if st.button("🗑️ 表示中の画像を消す", key="thumb_clear", width="stretch"):
        st.session_state[STATE_IMAGES] = []
        st.rerun()


def render() -> None:
    ui.page_header(
        "🖼️",
        "サムネイル作成",
        "note・ブログ・SNS など、媒体に合わせた比率とデザインでサムネイルを作ります。",
    )
    if not ui.api_key_guard():
        return

    platform = st.selectbox("どこで使うサムネイルか", list(PRESETS))
    preset = _preset(platform)

    if platform == "その他（比率を自分で指定）":
        ratio = st.selectbox("アスペクト比", RATIOS)
    else:
        ratio = preset["ratio"]
        st.caption(f"推奨サイズ {preset['size']}（{ratio}）　—　{preset['notes']}")

    subject = st.text_area(
        "記事・投稿の内容",
        height=120,
        placeholder="例: 会社を辞めて在宅ワークに切り替えた体験談。朝の散歩で生活リズムが整った話。",
    )

    col1, col2 = st.columns(2)
    main_text = col1.text_input("サムネに入れるメインの文字", placeholder="例: 在宅ワーク、最初の3ヶ月")
    sub_text = col2.text_input("サブの文字（任意）", placeholder="例: 失敗から学んだこと")
    st.caption("空欄にすると、文字なしのビジュアルだけの画像を作ります。")

    col3, col4 = st.columns(2)
    style = col3.selectbox("テイスト", list(STYLES))
    color = col4.selectbox("配色", COLORS)

    col5, col6 = st.columns(2)
    people = col5.selectbox("人物", PEOPLE)
    quality = col6.radio("画質", ["1K（速い）", "2K（きれい）"], index=1, horizontal=True)

    extra = st.text_area(
        "追加の希望（任意）",
        height=80,
        placeholder="例: 朝の光が入る部屋。ノートパソコンとコーヒー。人の顔は写さない。",
    )

    with st.expander("画像生成モデルの設定"):
        live = gemini.image_models(config.current().api_key)
        options = live or list(gemini.IMAGE_MODELS.values())
        preferred = [m for m in gemini.IMAGE_MODELS.values() if m in options]
        image_model = st.selectbox(
            "モデル",
            options,
            index=options.index(preferred[0]) if preferred else 0,
            help="一覧は APIキーで実際に使えるモデルから作られます。",
        )
        count = st.slider("生成する枚数", 1, 3, 1, help="枚数の分だけ API を呼びます。")
        st.caption(
            "日本語の文字入れは Nano Banana Pro のほうが安定します。"
            "それでも文字が崩れることがあるので、生成後は必ず目で確認してください。"
        )

    st.divider()
    step1, step2 = st.columns(2)
    plan = step1.button("① デザイン案を考える", width="stretch")
    make = step2.button("② 画像を生成する", type="primary", width="stretch")

    if make:
        if not subject.strip() and not main_text.strip():
            st.warning("記事の内容か、入れる文字のどちらかは入力してください。", icon="⚠️")
        else:
            image_prompt = _image_prompt(
                platform, subject, main_text, sub_text, style, color, people, extra
            )
            saved: list[dict] = []
            progress = st.progress(0.0, text="画像を生成しています…")
            try:
                for index in range(count):
                    images, _ = gemini.generate_image(
                        image_prompt,
                        model=image_model,
                        aspect_ratio=ratio,
                        image_size=quality[:2],
                    )
                    for data, mime in images:
                        saved.append(
                            {
                                "name": history.save_image(data, mime),
                                "mime": mime,
                                "ratio": ratio,
                                "platform": platform,
                            }
                        )
                    progress.progress((index + 1) / count, text=f"{index + 1} / {count} 枚")
            except gemini.GeminiError as exc:
                st.error(str(exc), icon="🚫")
            finally:
                progress.empty()

            if saved:
                st.session_state[STATE_IMAGES] = saved
                history.add(
                    TOOL_LABEL,
                    image_prompt,
                    {
                        "媒体": platform,
                        "比率": ratio,
                        "テイスト": style,
                        "images": [item["name"] for item in saved],
                    },
                )

    _render_saved_images()

    prompt = None
    if plan:
        if not subject.strip() and not main_text.strip():
            st.warning("記事の内容か、入れる文字のどちらかは入力してください。", icon="⚠️")
        else:
            prompt = _design_prompt(
                platform, subject, main_text, sub_text, style, color, people, extra
            )

    ui.render_output(
        f"{TOOL_KEY}_plan",
        f"{TOOL_LABEL}（デザイン案）",
        prompt=prompt,
        system=SYSTEM,
        meta={"媒体": platform, "比率": ratio, "テイスト": style},
    )
