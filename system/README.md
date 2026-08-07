# ローカル見積作成システム（開発者向け入口）

| 項目 | 内容 |
|------|------|
| バージョン | **`quote_system.config.APP_VERSION` を正**（執筆時点 ver.1.3.3） |
| 現場向け操作 | ひとつ上の `README.txt` |
| **引き継ぎ仕様書（日本語・詳細）** | [`docs/開発者向け仕様書_v1.3.md`](docs/開発者向け仕様書_v1.3.md) |
| **AI向け仕様（英語）** | [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md)／[`AGENTS.md`](../AGENTS.md)／[`docs/AGENT_CHANGE_HISTORY.md`](docs/AGENT_CHANGE_HISTORY.md) |

後任の方はまず **`docs/開発者向け仕様書_v1.3.md`** を読んでください。  
Cursor / AI には **`AGENTS.md` + `AI_CONTEXT.md` + `AGENT_CHANGE_HISTORY.md`** を読ませてください。

## フォルダ構成（概要）

```
quote-edit/
  アプリ起動.bat / README.txt / 機種代金一覧表/ / output/
  AGENTS.md
  .cursor/rules/            … Cursor向けルール（実行には不要）
  system/
    desktop_app.py
    quote_system/
    data/                   … masters（company.json は Git外・ローカルのみ）
    docs/
    tests/
    build_portable_exe.bat
```

`.cursor` の説明は [`docs/開発者向け仕様書_v1.3.md`](docs/開発者向け仕様書_v1.3.md) と [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md) を参照。

## 現場向けアプリの流れ

1. `機種代金一覧表` に価格表PDFを置く  
2. 起動（開発：`アプリ起動.bat`／配布：`見積もり一括作成.exe`）  
3. `見積もり作成` → `output\見積PDF` へ上書き／追加  

## 管理者権限なしでの配布

`system\build_portable_exe.bat` → `portable\見積もり一括作成ver{APP_VERSION}`  
EXEの作業データは `%LOCALAPPDATA%\InfinityQuoteApp`。

## セットアップ（開発PC）

```powershell
cd system
python -m pip install -r requirements.txt
python -m unittest tests.test_system -v
```

## 現在の仕様ハイライト（1.3.x）

- 出力先固定：`output/見積PDF/`
- 初期費用デフォルト：免除＋3000円（標準手数料はオプション）
- 通常IPS：プラン別フォルダ（ゴールド24 等）／ファイル名は機種_容量のみ
- スーパー／ハイパー：プラン名フォルダなし（全販売区分）。サブスクは SB光直下、通常IPSは一括表記／ランニングコスト表記
- ランニングIPS：保証終了後は「－」；36か月は 25～36 / 37～48 分割
- スーパーライト：パケット50GBのみ
- PDF追加割引表示：弊社特別割引（内部名はスーパー／ハイパーライト割）
- 除外機種は再生成より優先；おうち割ありでは5GBを作らない
- PDF原則1ページ

詳細は仕様書本体と `AGENT_CHANGE_HISTORY.md` を参照。
