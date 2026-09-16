# AGENTS.md - Quote Edit / 見積もり一括作成

You are working in a **local SoftBank corporate quote PDF batch generator** (Windows).

## Read first

| Audience | Path | Language |
|----------|------|----------|
| **AI (this doc)** | `AGENTS.md` | English |
| **AI (full architecture)** | `system/docs/AI_CONTEXT.md` | English |
| **AI (change log / decisions)** | `system/docs/AGENT_CHANGE_HISTORY.md` | English |
| **Human developers (handoff)** | `system/docs/開発者向け仕様書_v1.4.md` | Japanese |
| **Field operators** | `README.txt` | Japanese (keep short) |
| **Cursor IDE rules** | `.cursor/rules/*.mdc` | English (project rules) |

Always load `system/docs/AI_CONTEXT.md` before non-trivial code changes.  
For prior fine-tuning, defaults, packing pitfalls, and “why is it like this?”, also load **`system/docs/AGENT_CHANGE_HISTORY.md`**.

## `.cursor` folder (required reading for agents)

`.cursor/` is **Cursor IDE project configuration**, not runtime app code and not for field users.

| Path | Role |
|------|------|
| `.cursor/rules/quote-edit-handoff.mdc` | Always-applied project rule (`alwaysApply: true`). Injects handoff invariants and points agents to `AGENTS.md` / `AI_CONTEXT.md` / Japanese spec. |

Rules for agents working in this repo:

1. Treat `.cursor/rules/*.mdc` as **binding project policy** alongside this file.
2. Do **not** delete or empty `.cursor` unless a human explicitly asks.
3. When adding rules, prefer small focused `.mdc` files with YAML frontmatter (`description`, `alwaysApply` or `globs`).
4. Keep field `README.txt` free of deep Cursor internals; one short "ignore this folder" line is enough for users.
5. Portable/EXE distribution may omit `.cursor`; that is fine. Source repo should keep it.

Full architecture notes on `.cursor` live in `system/docs/AI_CONTEXT.md` section **Cursor project config**.

## Current version

- **ver.1.5** - constant: `system/quote_system/config.py` -> `APP_VERSION`
- Window title: `app_window_title()` — standard `見積もり一括作成  ver.{APP_VERSION}`; TM `見積もり一括作成（TM兼任事業部用）  ver.{APP_VERSION}`

## Source of truth (edit these)

- Logic: `system/quote_system/*.py`
- GUI: `system/desktop_app.py`
- Masters: `system/data/plans.json`, `services.json`; **company contacts** via local `company.json` (gitignored) — template `company.example.json`
- Tests: `system/tests/test_system.py` (+ installment / update-check tests as needed)
- Cursor rules: `.cursor/rules/`

Treat as generated / do not hand-edit as source: `portable/`, `system/work/`, large vendor trees under portable.


## Locked output tree (do not change casually)

- Canonical relative path under each quote root: `{category}/{model}/{sales}/[SB光…]/[fee/IRS/plan/IPS…]/{file}.pdf`
- Model folder is **immediately under category** (not leaf-only).
- Model folder name uses compact `_filename_model` (no spaces/underscores).
- **Never** reshuffle this hierarchy without asking the user for explicit confirmation in that turn (even if they request a path change).

## Hard product rules (do not regress)

1. **Fixed output roots** (overwrite/merge; **no** per-run timestamp folders):
   - 48: `output/見積PDF/` (TM: `見積PDF_TM特例/`)
   - 36: `output/見積PDF_36回/` (TM: `見積PDF_TM特例_36回/`)
   - 24: `output/見積PDF_24回/` (TM: `見積PDF_TM特例_24回/`) — individual only
2. Included models (`included_models.json`) win over "regenerate all" and are the only models shown in the individual-quote dropdown (**48-mode**). Legacy `excluded_models.json` is used only when the include file is absent. **36-mode** uses `installment_36_targets.json` only.
3. Do **not** create ouchi-discount (SB光あり) quotes for **5GB** on phones (same effective offer as 20GB). Exception: **iPad / AndroidTab** allow 5GB+ouchi (no 20GB tier; packet set is 1/5/50GB only). **TM unrestricted individual** may also allow ouchi+5GB more broadly.
4. Upfront IPS may produce two display modes: `lump` and `monthly_as_running` (UI picks one).
5. Quote PDFs must remain **one page** under worst-case content (portrait A4).
6. Field docs stay simple; put architecture/history in `system/docs/`.
7. **Batch:** super/hyper = IRS+discount set only. **Individual (both editions):** may choose 安心サポートなし while keeping 弊社特別割引.
8. **24回割賦:** button under 作成タイプ opens individual window (not a batch radio); uses price-list `payment_24`.
9. iPad / データ通信 / AndroidTab: no MNP or 番号移行. Light / super_light / hyper_light: only `iPhone` and `Android`.
10. **Startup update check** (`update_check.py`): **standard edition only**. Reads share `latest.json`; silent on failure; never auto-replaces the app.
11. Skip devices marked `※MM販路取扱不可` (case-insensitive) in model/notes — not in picker, batch, or individual lists.
12. Include-picker / individual model lists follow **price PDF appearance order** (category sections by first appearance; no capacity re-sort).

## Typical workflows

- Run tests: `cd system && python -m unittest tests.test_system tests.test_installment_36 tests.test_update_check -v`
- Dev GUI: `アプリ起動.bat` or `python desktop_app.py` from `system/`
- Portable EXE: `system/build_portable_exe.bat` (ASCII/CRLF bats; **no UTF-8 BOM**)
- TM兼任事業部用 EXE: `system/build_portable_exe_tm.bat` (sets `QUOTE_APP_EDITION=tm_special`)

## Frozen vs source paths

| | Standard EXE | TM EXE |
|--|--------------|--------|
| User data | `%LOCALAPPDATA%\InfinityQuoteApp\` | `%LOCALAPPDATA%\InfinityQuoteAppTM\` |
| Price PDFs / `output/` | beside EXE | beside EXE |

See `AI_CONTEXT.md` path table.

## When bumping a release

1. Change `APP_VERSION`
2. Update Japanese developer spec (`開発者向け仕様書_v1.4.md`) if behavior changed
3. Sync `AI_CONTEXT.md` version table and this file
4. **Append** a dated entry to `system/docs/AGENT_CHANGE_HISTORY.md` (do not wipe history)
5. Keep title bar via `app_window_title()` and in-app version labels consistent
6. Field `README.txt` / `リリースノート_v{version}_現場向け.txt`: **UTF-8 with BOM** (see history doc)
7. Keep `.cursor/rules` pointers accurate if docs move
8. **Standard field release:** after placing the ZIP on `N:\01.ツールズ\見積もり作成ツール\`, update **`latest.json`** there (`version` + `zip` to match). Also sync `system/data/latest.example.json`. Do not point it at TM ZIPs.
