# AIライティングツール解体新書

> 自分で作った 3,000 行のコードを、あらためて頭から読み直す。
> `app.py` はたった 110 行で、覚えるべき考え方は 4 つしかない。

| 項目 | 数 |
|---|---|
| app.py の行数 | 110 |
| ツールの数 | 12 |
| core のファイル | 7 |
| core + tools の行数 | 3,076 |

---

## 01. まず全体像 — 4 つの層に分かれている

このアプリは **Streamlit**（Python だけで Web 画面が作れるライブラリ）で動いていて、中身はきれいに 4 層に分かれています。この分け方さえ掴めば、あとはどのファイルを開けばいいかが自動的に決まります。

| 層 | 役割 | 説明 |
|---|---|---|
| `app.py` | 受付 | どんなツールがあるかを一覧で持ち、サイドバーとページ切り替えを用意するだけ。処理は一切しない。 |
| `tools/` | 各ツールの画面 | 「ブログ記事作成」「文章要約」など 1 ツール 1 ファイル。入力欄を並べて、AI への指示文を組み立てるところまでが仕事。 |
| `core/` | 共通部品 | API 通信・プロンプトの部品・共通 UI・履歴・写真・コピー機能。全ツールがここを使い回す。 |
| `data/` | 保存場所 | `history.json` と `images/`。データベースは使わず、ただのファイル。 |

> **いちばん大事な原則**
>
> **tools は「何を聞くか」だけ、core は「どう作るか」だけ。**
> だから新しいツールを足しても core は 1 行も触らなくていいし、Gemini の使い方が変わっても直すのは core の 1 ファイルだけで済みます。

---

## 02. app.py の心臓は、たった 1 つの辞書

110 行のうち、意味があるのは実質この部分です。`TOOLS` という辞書が「グループ名 → そのグループのツール一覧」を持っていて、**画面もメニューも全部ここから自動生成されます**。

**`ai_writer/app.py`**

```python
# (モジュール, タイトル, アイコン, URLパス, ひとこと説明)
TOOLS = {
    "書く": [
        (blog,         "ブログ記事作成", "📝", "blog",  "構成案から本文まで一気に書く"),
        (note_article, "note記事作成",   "🖊️", "note",  "メモから note の語り口で書く"),
        (email_reply,  "メール返信作成", "📧", "email", "受信メールに合わせた返信文を作る"),
        (social,       "SNS投稿文",     "📱", "social","各SNSの作法に合わせた投稿案を出す"),
    ],
    "整える": [ ... ],
    "考える": [ ... ],
    "画像":   [ ... ],
}
```

この辞書を回して `st.Page` を作り、`st.navigation` に渡す。これで左のメニューが完成します。

**`ai_writer/app.py` — 末尾 17 行**

```python
PAGES: dict[str, st.Page] = {}
for group, items in TOOLS.items():
    for module, title, icon, url_path, _ in items:
        PAGES[url_path] = st.Page(module.render, title=title, icon=icon, url_path=url_path)

ui.sidebar_settings()
st.navigation(navigation, expanded=True).run()
```

`st.Page(module.render, ...)` の `module.render` に注目してください。**各ツールのファイルは `render()` という関数さえ持っていればいい**という約束になっていて、これがこのアプリ全体の設計を支えています。ツールを増やす作業が「ファイルを 1 つ作って、辞書に 1 行足す」だけで終わるのはこのおかげです。

---

## 03. Streamlit の「上から全部走り直す」を先に理解する

ここが最初にひっかかるところです。Streamlit は普通の Web アプリと違い、**ボタンを押すたび・スライダーを動かすたびに、スクリプトが上から下まで丸ごと再実行されます**。「変わったところだけ更新」ではありません。

つまり素直に書くと、文字数スライダーを少し動かしただけで AI がまた記事を書き始めてしまう。このアプリはそれを、`ui.render_output()` のたった一つの仕掛けで防いでいます。

**`ai_writer/tools/summarize.py` — 各ツール共通の型**

```python
run = st.button("要約する", type="primary", width="stretch")

prompt = None                # ← ふだんは None のまま
if run:                      # ← ボタンが押された回だけ中身が入る
    prompt = prompts.build( ... )

ui.render_output(TOOL_KEY, TOOL_LABEL, prompt=prompt, system=SYSTEM, ...)
```

> **読み解き**
>
> `render_output` は **prompt が入っていれば生成、None なら前回の結果を出すだけ**。前回の結果は `st.session_state["result::summary"]` に置いてあります。
> 「生成するかどうか」の判断を全ツールで 1 か所に集めたので、各ツールは `prompt = None` と書くだけで再生成を防げます。

---

## 04. ボタンを押してから文字が出るまで

「要約する」を押したとき、コードの中を何がどう流れるか。実際の順番です。

1. **入力を集める** — `tools/summarize.py → render()`
   原文・形式・文字数・読む人・残したい観点を画面から受け取る。
2. **指示文を組み立てる** — `core/prompts.py → build() / block() / rules()`
   空欄の項目は自動で捨てられ、埋まった項目だけが見出し付きのブロックになる。
3. **設定を読む** — `core/config.py → current()`
   サイドバーで選んだ APIキー・モデル・創造性を 1 つの `Settings` にまとめて渡す。
4. **Gemini に投げる** — `core/gemini.py → stream_text()`
   返事を待たず、届いた文字から順に `yield` で吐き出す。
5. **流しながら表示する** — `core/ui.py → st.write_stream()`
   タイプライターのように文字が出てくるのはここ。完成を待たないので体感が速い。
6. **履歴に残す** — `core/history.py → add()`
   `data/history.json` の先頭に追加。写真があれば画像も一緒に保存。
7. **コピー・保存ボタンを出す** — `core/ui.py → result_actions()`
   書式つきコピー、Markdown 保存、ZIP 保存、文字数チェック。

---

## 05. prompts.py — 指示文をレゴブロックにする

プロンプトを `f"..."` で毎回ベタ書きすると、条件が増えるたびに if 文だらけになります。このアプリは**部品を 3 つだけ**用意して、それを積むやり方をとっています。

**`ai_writer/core/prompts.py`**

```python
def block(label, value):
    """値があるときだけ見出しつきのブロックにする。"""
    if not value or not str(value).strip():
        return ""          # ← 空欄は自動で消える
    return f"# {label}\n{str(value).strip()}\n\n"

def build(*parts):
    """空でないブロックだけをつなげる。"""
    return "\n".join(p for p in parts if p and p.strip())

def rules(*lines, label="守ること"):
    """条件を箇条書きにまとめる。"""
```

おかげで各ツールは、**入力欄が埋まっているかを一切気にせず**ただ並べるだけで済みます。

```python
prompt = prompts.build(
    "次の文章を要約してください。",
    prompts.block("原文", source),
    prompts.block("要約を読む人", audience),   # 空なら消える
    prompts.block("必ず残す観点", keep),       # 空なら消える
    prompts.rules(
        FORMATS[fmt],
        "原文に書かれていないことは足さない",
        "数値・日付・固有名詞はそのまま残す",
    ),
)
```

### 文字数を守らせる工夫

「1,000 字で書いて」と頼んでも AI はぴったりには書けません。そこで `length_rules()` は**4 つの指示をセットで**渡します。

- 約 1,000 字（800〜1,200 字）に収める、**この範囲は必ず守る**
- 見出し・箇条書き・記号も**すべて含めて**数える
- 書き終えたら**数えて、外れていたら直してから**出力する
- 文字数を埋めるための繰り返しや前置きは書かない

さらに `suggest_sections()` が文字数から見出しの本数（700 字に 1 本、2〜8 本）を割り出して「1 セクション約○○字」まで指定します。範囲で狙わせて、最後に実測を表示する ——「ズレる前提で設計する」という考え方です。

---

## 06. gemini.py — API の面倒を全部引き受ける 291 行

core の中でいちばん厚いファイルですが、やっていることは 4 つです。

| 関数 | 役割 | ポイント |
|---|---|---|
| `stream_text()` | 文章を少しずつ生成 | 画像も一緒に渡せる（写真を見て書かせる） |
| `chat_stream()` | 会話履歴つきの生成 | AIチャット専用 |
| `generate_image()` | 画像生成 | Nano Banana 系。比率と解像度を指定 |
| `text_models()` | 使えるモデル一覧 | APIキーで実際に使えるものだけ出す |

### エラーを日本語に翻訳する

いちばん実用的なのが `_friendly()`。Google から返る英語のエラーを、**原因と次にやることが分かる日本語**に置き換えます。

**`ai_writer/core/gemini.py`**

```python
if "API key not valid" in message:
    return GeminiError("APIキーが正しくないようです。サイドバーで確認してください。" + detail)
if "RESOURCE_EXHAUSTED" in message or "429" in message:
    return GeminiError("APIの利用上限に達しました。しばらく待つか、軽いモデルに変えてください。" + detail)
if "NOT_FOUND" in message or "404" in message:
    return GeminiError(
        f"{where}は、このAPIキーでは使えません。サイドバーで下のモデルに変えてください。"
        + _available_listing()   # ← その場で使えるモデルを並べる
        + detail
    )
```

> **ここは実際のつまずきから生まれた**
>
> 「`gemini-2.5-pro` が使えない」と詰まったとき、**エラーを出すだけでなくその場で「使えるモデル一覧」を出す**ように直した名残です。`detail` で生の英語メッセージも必ず末尾に残しているので、想定外の原因も追えます。

加えて、`@st.cache_resource` で API クライアントを、`@st.cache_data(ttl=3600)` でモデル一覧を 1 時間キャッシュ。前述の「毎回上から再実行」でも、通信が走らないようにしてあります。

---

## 07. config.py — 設定を 1 つの箱にまとめる

APIキー・モデル・創造性・高速モード。この 4 つを `Settings` という**変更できない箱**（frozen dataclass）にまとめ、`config.current()` でいつでも取り出せるようにしています。

**`ai_writer/core/config.py`**

```python
def current() -> Settings:
    """いま有効な設定を返す。サイドバー未描画でも安全に呼べる。"""
    return Settings(
        api_key=st.session_state.get("api_key") or env_api_key(),
        model=st.session_state.get("model_id", MODELS[DEFAULT_MODEL_LABEL]),
        temperature=float(st.session_state.get("temperature", 0.7)),
        fast_mode=bool(st.session_state.get("fast_mode", False)),
    )
```

APIキーの探し方は **入力欄 → `.env` → 環境変数 → `secrets.toml`** の順。`.env` に書いておけば毎回貼らずに済み、書いていなければサイドバーの入力欄が出る、という二段構えです。`st.session_state` は「再実行しても消えない置き場所」で、Streamlit で状態を持つときの唯一の手段だと覚えておけば十分です。

---

## 08. ツールは全部おなじ形をしている

12 個のツールは、例外なくこの 5 ステップで書かれています。1 つ読めれば全部読めます。

```python
def render():
    ui.page_header("📄", "文章要約", "...")     # 1. 見出し
    if not ui.api_key_guard(): return          # 2. キーが無ければ案内して終了

    source = st.text_area("要約したい文章", ...)  # 3. 入力欄
    fmt    = st.selectbox("形式", list(FORMATS))

    prompt = None
    if st.button("要約する"):                    # 4. 押されたら指示文を組む
        prompt = prompts.build( ... )

    ui.render_output(TOOL_KEY, TOOL_LABEL, prompt=prompt, ...)  # 5. あとは丸投げ
```

各ファイルの冒頭にある `SYSTEM` が、そのツール専用の性格づけです。共通の `BASE_SYSTEM`（「日本語のプロのライター兼編集者」「前置きは書かない」「不確かなら〔要確認〕と書く」）に、ツール固有の一文を足す形になっています。

**`ai_writer/tools/summarize.py`**

```python
SYSTEM = (
    prompts.BASE_SYSTEM
    + "あなたは要約の専門家です。原文にある情報だけを使い、"
      "結論・根拠・数字を優先して残します。原文にない解釈や推測は加えません。"
)
```

ブログ記事だけはもう一段あって、SEO トグルを ON にすると `SEO_SYSTEM` が上乗せされます。中身は**キーワードの詰め込みを明確に禁止したうえで**、「検索意図への結論を冒頭で先に示す」「見出しの直下 2〜3 文でその問いに答える」「読んでも行動が変わらない一般論を書かない」「数値を捏造しない」といった、編集者が新人ライターに言うような指示になっています。

---

## 09. 地味だけど効いている 3 ファイル

### history.py — データベースなしの履歴

JSON ファイル 1 つ。新しいものを先頭に `insert(0, ...)` して、300 件を超えたら古いものから捨てる。それだけです。

面白いのは画像の保存方法で、**ファイル名を画像の中身のハッシュ（SHA-1）にしています**。同じ写真を何度使ってもファイルは 1 つしか増えません。さらに `unused_images()` が「どの履歴からも参照されていない画像」を洗い出すので、履歴を消したあとのゴミ掃除ができます。

### photos.py — 写真を記事に差し込む

本文に `[[写真1]]` というマーカーを AI に書かせておき、表示のときに実際の画像へ差し替える方式です。HEIC（iPhone の写真）は自動で JPEG に変換し、**Gemini に送る用だけ長辺 1,600px に縮小**して、手元には元のサイズを残します。通信量を抑えつつ書き出しの画質は落とさない、という分担です。

### richcopy.py — note に貼ると書式が崩れる問題

note やメールの編集画面は Markdown を解釈しないので、`## 見出し` がそのまま文字として貼られてしまう。そこで Markdown を HTML に変換してからクリップボードに載せています。ここに、実際にぶつかった罠への対処が 2 つ入っています。

**`ai_writer/core/richcopy.py`**

```python
# 行頭の # が、後ろに空白なしで続くもの（= ハッシュタグ）
HASHTAG_LINE = re.compile(r"^(#{1,6})(?=[^\s#])", flags=re.MULTILINE)

def protect_hashtags(text):
    """「#無印良品」が巨大な見出しとして貼り付けられるのを防ぐ。"""
    return HASHTAG_LINE.sub(lambda m: "".join("\\" + c for c in m.group(1)), text)

# 「文章の次の行に --- 」を見出しとみなす記法を切る
converter.parser.blockprocessors.deregister("setextheader")
```

> **なぜこのコードがあるか**
>
> Markdown の見出しは `# ` のように **#** のあとに空白が入ります。空白のない `#無印良品` はハッシュタグなのに、変換器は見出しと解釈してしまう ——「コピペするとハッシュタグ以降の文字が大きくなる」現象の正体です。
> 2 つめの `deregister("setextheader")` は、区切り線のつもりで入れた `---` のせいで直前の 1 行が巨大な見出しに化けるのを防いでいます。
> 本文は AI の出力なので、変換前に必ず HTML エスケープしてタグを無効化してから処理しているのも大事な一手です。

---

## 10. 新しいツールを 1 つ足すには

ここまでの設計のご褒美がこれです。たとえば「プレスリリース作成」を足すなら:

1. `tools/press.py` を作り、`SYSTEM` と `render()` を書く（`summarize.py` を丸ごとコピーして中を書き換えるのが早い）
2. `app.py` の import に `press` を足す
3. `TOOLS["書く"]` に 1 行 `(press, "プレスリリース作成", "📣", "press", "...")` を足す

以上。メニュー・URL・ホーム画面のカード・履歴への保存・コピーボタン・文字数チェックは、**全部ついてきます**。core は 1 行も触りません。

---

## 11. このコードから持ち帰れる考え方

1. **入り口のファイルは薄く保つ。**
   app.py は「何があるか」を宣言するだけ。処理を書き始めた瞬間に読めなくなる。
2. **同じ形を 12 回くり返す。**
   全ツールが同型なので、1 つ読めば全部読めるし、1 つ直せば全部直せる。
3. **プロンプトも部品にする。**
   文字列を組み立てる関数を 3 つ用意しただけで、if 文の山が消えた。
4. **エラーは「次に何をすればいいか」まで書く。**
   使えないモデルを告げるだけでなく、使えるモデルをその場に並べる。
5. **AI の出力はズレる前提で設計する。**
   文字数は範囲で狙わせ、実測を必ず表示する。〔要確認〕を書かせる。

次に手を入れるなら、まず開くべきは `tools/` の中の 1 ファイルです。core は「動いているので触らない」場所として置いておけます。

---

対象コード: `ai_writer/`（app.py 110 行 / core 7 ファイル / tools 13 ファイル）
起動: `.venv/bin/streamlit run ai_writer/app.py` → `http://localhost:8501`
