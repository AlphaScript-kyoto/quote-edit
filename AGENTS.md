# AGENTS.md - Quote Edit / 見積もり一括作成

You are working in a **local SoftBank corporate quote PDF batch generator** (Windows).

## Read first

| Audience | Path | Language |
|----------|------|----------|
| **AI (this doc)** | `AGENTS.md` | English |
| **AI (full architecture)** | `system/docs/AI_CONTEXT.md` | English |
| **Human developers (handoff)** | `system/docs/開発者向け仕様書_v1.1.md` | Japanese |
| **Field operators** | `README.txt` | Japanese (keep short) |
| **Cursor IDE rules** | `.cursor/rules/*.mdc` | English (project rules) |

Always load `system/docs/AI_CONTEXT.md` before non-trivial code changes.

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

- **ver.1.1** - constant: `system/quote_system/config.py` -> `APP_VERSION`
- Window title (OS chrome / drag bar): `見積もり一括作成  ver.1.1`

## Source of truth (edit these)

- Logic: `system/quote_system/*.py`
- GUI: `system/desktop_app.py`
- Masters: `system/data/plans.json`, `services.json`, `company.json`
- Tests: `system/tests/test_system.py`
- Cursor rules: `.cursor/rules/`

Treat as generated / do not hand-edit as source: `portable/`, `system/work/`, large vendor trees under portable.

## Hard product rules (do not regress)

1. Output only under **`output/見積PDF/`** (overwrite/merge; no per-run timestamp folders).
2. Excluded models (`excluded_models.json`) win over "regenerate all" and are hidden from individual-quote model dropdown.
3. Do **not** create ouchi-discount (SB光あり) quotes for **5GB** (same effective offer as 20GB).
4. Upfront IPS may produce two display modes: `lump` and `monthly_as_running` (separate folders).
5. Quote PDFs must remain **one page** under worst-case content (portrait A4).
6. Field docs stay simple; put architecture/history in `system/docs/`.

## Typical workflows

- Run tests: `cd system && python -m unittest tests.test_system -v`
- Dev GUI: `アプリ起動.bat` or `python desktop_app.py` from `system/`
- Portable EXE: `system/build_portable_exe.bat` (ASCII/CRLF bats; **no UTF-8 BOM**)

## Frozen vs source paths

EXE user data lives in `%LOCALAPPDATA%\InfinityQuoteApp\`. Price PDFs and `output/` stay next to the EXE. See `AI_CONTEXT.md` path table.

## When bumping a release

1. Change `APP_VERSION`
2. Update Japanese developer spec filename/content if major
3. Sync `AI_CONTEXT.md` version table and this file
4. Keep title bar and in-app version labels consistent
5. Keep `.cursor/rules` pointers accurate if docs move
