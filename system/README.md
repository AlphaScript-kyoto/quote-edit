# ローカル見積作成システム（開発者向け入口）

| 項目 | 内容 |
|------|------|
| バージョン | **ver.1.2**（`quote_system.config.APP_VERSION`） |
| 現場向け操作 | ひとつ上の `README.txt` |
| **引き継ぎ仕様書（日本語・詳細）** | [`docs/開発者向け仕様書_v1.1.md`](docs/開発者向け仕様書_v1.1.md) |
| **AI向け仕様（英語）** | [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md) ／ リポジトリ直下 [`AGENTS.md`](../AGENTS.md) |

後任の方はまず **`docs/開発者向け仕様書_v1.1.md`** を読んでください。  
Cursor / その他 AI に作業させるときは **`AGENTS.md` + `AI_CONTEXT.md`** を読ませてください（英語の方が構造化ルールを安定して拾いやすいため、人向けと分けています）。

## フォルダ構成（概要）

```
quote-edit/
  アプリ起動.bat / README.txt / 機種代金一覧表/ / output/
  AGENTS.md
  .cursor/rules/            … Cursor（開発用AI）向けルール。アプリ実行には不要
  system/
    desktop_app.py          … GUI（タイトルバーに ver.x.x 表示）
    quote_system/           … 計算・一括・PDF
    data/                   … JSONマスタ・状態
    docs/                   … 仕様書（.cursorの詳細説明あり）
    tests/
    build_portable_exe.bat
```

`.cursor` の意味・保守方針は [`docs/開発者向け仕様書_v1.1.md`](docs/開発者向け仕様書_v1.1.md) の「`.cursor` フォルダとは」および [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md) の **Cursor project config** を参照。

## 現場向けアプリの流れ

1. `機種代金一覧表` に価格表PDFを置く  
2. 起動（開発：`アプリ起動.bat`／配布：`見積もり一括作成.exe`）  
3. `見積もり作成` → `output\見積PDF` へ上書き／追加  

## 管理者権限なしでの配布

`system\build_portable_exe.bat` → `portable\見積もり一括作成ver{APP_VERSION}`（現在は ver1.2）  
EXEの作業データ（除外機種など）は `%LOCALAPPDATA%\InfinityQuoteApp`。

## セットアップ（開発PC）

```powershell
cd system
python -m pip install -r requirements.txt
python -m unittest tests.test_system -v
```

## CLI（開発用）

```powershell
cd system
python app.py import-price --pdf "input\分割支払金一覧.pdf"
python app.py generate --request "data\test_quote.json"
```

## 現在の仕様ハイライト（ver.1.1）

- 出力先固定：`output/見積PDF/`
- フォルダ：料金プラン → 事務手数料あり／初期費用3000円 → IPSサブスク／一括型／一括型_月額換算／なし → 安心サポート
- 除外機種：`data/excluded_models.json`（全機種再生成より優先）
- おうち割ありでは5GBを作らない
- PDFは原則1ページ

詳細・相関図・保守手順は仕様書本体を参照。
