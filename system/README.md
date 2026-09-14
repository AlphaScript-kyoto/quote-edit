# ローカル見積作成システム（開発者向け入口）

| 項目 | 内容 |
|------|------|
| バージョン | **`quote_system.config.APP_VERSION` を正**（執筆時点 ver.1.4.10β） |
| 現場向け操作 | ひとつ上の `README.txt` |
| **引き継ぎ仕様書（日本語・詳細）** | [`docs/開発者向け仕様書_v1.4.md`](docs/開発者向け仕様書_v1.4.md) |
| **AI向け仕様（英語）** | [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md)／[`AGENTS.md`](../AGENTS.md)／[`docs/AGENT_CHANGE_HISTORY.md`](docs/AGENT_CHANGE_HISTORY.md) |

後任の方はまず **`docs/開発者向け仕様書_v1.4.md`** を読んでください。  
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
    build_portable_exe_tm.bat   … TM兼任事業部用
```

`.cursor` の説明は [`docs/開発者向け仕様書_v1.4.md`](docs/開発者向け仕様書_v1.4.md) と [`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md) を参照。

## 現場向けアプリの流れ

1. `機種代金一覧表` に価格表PDFを置く  
2. 起動（開発：`アプリ起動.bat`／配布：`見積もり一括作成.exe`）  
3. `見積もり作成` → 出力先は作成タイプに応じて上書き／追加（48回: `output\見積PDF`、36回: `output\見積PDF_36回`、24回個別: `output\見積PDF_24回`。TM兼任事業部用は `見積PDF_TM特例` / `_36回` / `_24回` の各ルート）  

## 管理者権限なしでの配布

`system\build_portable_exe.bat` → `portable\見積もり一括作成ver{APP_VERSION}`  
EXEの作業データは `%LOCALAPPDATA%\InfinityQuoteApp`。
現場 ZIP ビルド時は **`system/data/company.json` 必須**（TEL/FAX 入り）。Git にはコミットしない。

TM兼任事業部用（個別のみ制限解除）:  
`system\build_portable_exe_tm.bat` → `portable\見積もり一括作成_TM兼任事業部用ver{APP_VERSION}`  
出力は `output\見積PDF_TM特例`（36回: `_36回`、24回個別: `_24回`）、作業データは `%LOCALAPPDATA%\InfinityQuoteAppTM`。通常版ZIPとは別に配布する。

## セットアップ（開発PC）

```powershell
cd system
python -m pip install -r requirements.txt
python -m unittest tests.test_system tests.test_installment_36 tests.test_update_check -v
```

## 現在の仕様ハイライト（1.4.x）

- 出力先固定（タイムスタンプフォルダなし）：48回 `output/見積PDF/`（TM: `見積PDF_TM特例/`）、36回 `output/見積PDF_36回/`（TM: `見積PDF_TM特例_36回/`）、24回個別 `output/見積PDF_24回/`（TM: `見積PDF_TM特例_24回/`）
- 初期費用デフォルト：免除＋3000円（標準手数料はオプション）
- IRS（安心サポート）：一括ではスーパー／ハイパーはIRS必須。個別では「安心サポートなし」可（割引維持）
- 通常IPS：UIで「一括表記」または「ランニングコスト表記」を選択可能（選択した片方だけ生成）
- 24回割賦：作成タイプのボタンから個別ウィンドウを開く（出力 `見積PDF_24回`、価格表の24回列）
- フォルダ根本分岐：`IRSあり` / `IRSなし`。IRSなし直下はIPS分岐（＝Biz）。スーパー／ハイパーはIRSあり直下でプラン名フォルダなし（IRSなし時はプラン名付き）
- 価格表の新機種ブロック結合（例: Pixel 11）を分割して機種マスターへ反映。［作成する機種］を開くと最新PDFを再取込
- 通常IPS：プラン別フォルダ（ゴールド24 等）／ファイル名は機種_容量のみ
- ランニングIPS：保証終了後は「－」；36か月は 25～36 / 37～48 分割
- スーパーライト：パケット50GBのみ
- PDF追加割引表示：弊社特別割引（内部名はスーパー／ハイパーライト割）
- 作成対象機種（48回モード）：`data/included_models.json` があれば「全機種再生成」より優先。36回は `installment_36_targets.json`。おうち割ありでは5GBを作らない（iPad／AndroidTabは例外。同カテゴリの容量は1／5／50GBのみ）
- 起動時更新確認（通常版のみ）：N: 共有 `latest.json` を読み、新版があれば通知（失敗時は無音、自動替換なし）。TM版は実行しない
- 連絡先・FAX：`company.json`（開発は system/data、EXEは %LOCALAPPDATA%\\InfinityQuoteApp\\data）。実番号は Git に入れない
- PDF原則1ページ

詳細は仕様書本体と `AGENT_CHANGE_HISTORY.md` を参照。
