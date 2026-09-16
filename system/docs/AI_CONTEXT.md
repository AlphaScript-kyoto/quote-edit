# AI Context - Infinity Quote Batch App (ver.1.5)

**Purpose:** Machine-oriented specification for coding agents. Prefer this file + root `AGENTS.md` over guessing.

**Human Japanese handoff:** `system/docs/開発者向け仕様書_v1.4.md` (v1.3 / v1.1 are stubs)  
**Decision / change history (AI):** `system/docs/AGENT_CHANGE_HISTORY.md` — **read for prior tuning, defaults, PDF micro-layout, packaging encoding faults**  
**Field ops (Japanese, short):** `README.txt`  
**App version constant:** `quote_system.config.APP_VERSION` -> currently `"1.5"`  
**Cursor IDE rules:** `.cursor/rules/` (see section below)

---

## Product summary

Local Windows desktop app that reads SoftBank corporate device price-list PDFs and generates many quote PDFs under a fixed output tree. No cloud APIs.

Stack: Python 3, tkinter GUI, pdfplumber, reportlab. Optional PyInstaller portable EXE.

Display name: `見積もり一括作成` (`APP_DISPLAY_NAME`). Window title via `app_window_title()`: standard `見積もり一括作成  ver.{APP_VERSION}`; TM `見積もり一括作成（TM兼任事業部用）  ver.{APP_VERSION}`.

PDF layout is **portrait A4 only** (landscape experiment was rejected; do not reintroduce without an explicit request).

---

## Cursor project config (`.cursor/`)

### What it is

`.cursor/` is configuration for the **Cursor IDE** (AI-assisted editor used by developers). It is **not** part of the quote-generation runtime. Field operators should ignore it; `README.txt` tells them so.

Agents must treat project rules under `.cursor/rules/` as **active constraints** for this repository, in addition to `AGENTS.md` and this file.

### Layout

```
.cursor/
  rules/
    quote-edit-handoff.mdc   # alwaysApply: true - handoff + product invariants
```

### Rule file format (`.mdc`)

Each rule is Markdown with YAML frontmatter:

- `description`: short purpose (shown in Cursor rule UI)
- `alwaysApply: true`: inject into every agent turn in this workspace
- or `globs: ...`: apply only when matching files are in context

Current `quote-edit-handoff.mdc` purpose:

1. Force agents to read `AGENTS.md` + this `AI_CONTEXT.md` + `AGENT_CHANGE_HISTORY.md` before non-trivial changes
2. Point Japanese human successors to `開発者向け仕様書_v1.4.md`
3. Restate hard invariants (fixed output roots 48/36/24 + TM, include-list, no ouchi+5GB except iPad/AndroidTab or TM unlock, batch vs individual IRS, update check, one-page PDF, fee defaults, field UTF-8 BOM, no bulk regen unless asked)
4. Distinguish source from generated; require append-only entries in the change history

### Maintenance rules for agents

| Do | Do not |
|----|--------|
| Update rule text when invariants or doc paths change | Delete `.cursor` "to clean up" without human approval |
| Keep rules short; architecture here; decisions in `AGENT_CHANGE_HISTORY.md` | Dump long session history only into `.mdc` |
| Keep user-facing `README.txt` at one short note about `.cursor` | Teach field users how to edit Cursor rules |
| Append dated log after user-visible changes | Erase past decisions from the history file |

### Distribution note

Portable EXE packages under `portable/` may omit `.cursor`. That is expected. The **source repository** should keep `.cursor/rules` so future Cursor sessions inherit handoff context.

### Relationship to other docs

```
Field user      -> README.txt                 (mentions .cursor only as "ignore")
Human developer -> 開発者向け仕様書_v1.4.md + AGENT_CHANGE_HISTORY.md
AI / Cursor     -> AGENTS.md + this file + AGENT_CHANGE_HISTORY.md + .cursor/rules/*.mdc
```

---


### Locked quote relative path

`category / model / sales / [SB光] / [fee/IRS/plan/IPS…] / file.pdf`

Agents must **not** move the model folder (leaf vs after-category, etc.) without explicit user confirmation in the same turn.

## Repository map (source of truth)

```
quote-edit/
  アプリ起動.bat                    # launch GUI (dev)
  README.txt                  # field user guide (JP, keep simple)
  機種代金一覧表/                      # drop price PDFs here (UPDATE_DIR)
  output/見積PDF/               # 48-mode root (also _36回 / _24回 / TM variants)
  AGENTS.md                   # agent entry
  .cursor/rules/              # always-on Cursor agent guidance
  system/
    desktop_app.py
    quote_system/
    data/
    tests/
    docs/開発者向け仕様書_v1.4.md  # Japanese human handoff (current)
    docs/開発者向け仕様書_v1.3.md  # stub -> v1.4
    docs/開発者向け仕様書_v1.1.md  # stub -> v1.4
    docs/AI_CONTEXT.md
    docs/AGENT_CHANGE_HISTORY.md  # decisions, session log, pitfalls
    docs/リリースノート_v*_現場向け.txt  # optional field release notes (UTF-8 BOM)
```

Ignore generated trees when editing logic: `portable/`, `system/work/`.

---

## Path model (`config.py`)

| Symbol | Dev | Frozen EXE |
|--------|-----|------------|
| `APP_ROOT` | repo root | folder containing EXE |
| `SYSTEM_DIR` | `system/` | `APP_ROOT/system/` |
| `DATA_DIR` | `system/data/` | Standard: `%LOCALAPPDATA%/InfinityQuoteApp/data/` · TM: `.../InfinityQuoteAppTM/data/` |
| `OUTPUT_DIR` | `APP_ROOT/output` | same beside EXE |
| `UPDATE_DIR` | `APP_ROOT/機種代金一覧表` | same beside EXE |

Output dirnames (`QUOTE_OUTPUT_DIRNAME*` in `config.py`):

| Mode | Standard | TM |
|------|----------|-----|
| 48 (batch + individual) | `見積PDF` | `見積PDF_TM特例` |
| 36 | `見積PDF_36回` | `見積PDF_TM特例_36回` |
| 24 (individual only) | `見積PDF_24回` | `見積PDF_TM特例_24回` |

24-installment: button under 作成タイプ opens `_open_individual_window(24)` (not a batch radio). Uses main price PDF `payment_24` column.

### Startup update check (standard only)

Module: `quote_system/update_check.py`. On GUI start (standard edition): read `N:\01.ツールズ\見積もり作成ツール\latest.json` (~2.5s timeout). Failures are silent. If remote version is newer, show dialog; Yes opens Explorer on the ZIP (no auto-replace); No snoozes that version for the calendar day. TM edition skips entirely. Ignore remote when `edition ≠ standard`. Ship checklist: rewrite share `latest.json` + `system/data/latest.example.json` after placing the standard ZIP.

### Device × sales-type gates

| Category | Blocked sales |
|----------|---------------|
| `iPad`, `AndroidTab`, `データ通信` | `MNP`, `番号移行` |

Helper: `is_device_sales_type_allowed` (batch variants, `build_quote`, individual UI). Applies to **both** standard and TM editions.

Light-family plans (`light` / `super_light` / `hyper_light`): only categories `iPhone` and `Android` (`is_device_plan_allowed`).

### Device × data-plan gates

| Category | Allowed packets | Notes |
|----------|-----------------|-------|
| `ケータイ` | `1GB` only | No ouchi folder |
| `iPad`, `AndroidTab` | `1GB`, `5GB`, `50GB` | No 20GB / 無制限; **ouchi+5GB allowed** (`allows_ouchi_discount_with_5gb`) |
| Other (phone etc.) | ≥5GB (+1GB on 機種変更); 無制限 | ouchi+5GB blocked (same offer as 20GB) |

Helper: `is_device_data_plan_allowed`. Ouchi+5GB skip uses `allows_ouchi_discount_with_5gb` in batch / individual / `build_quote`.

### App editions

| Edition | Audience | Individual | Batch |
|---------|----------|------------|-------|
| `standard` | Field | Gated (current rules); individual may omit IRS on super/hyper while keeping 弊社特別割引 | Strict (super/hyper = IRS+discount set only) |
| `tm_special` | TM兼任事業部 | Unrestricted light-family sales/capacities + IRS radios; `special_3000` uses tax-ex **4500** | Same as standard |

Set `QUOTE_APP_EDITION` or bundle `app_edition.json`. Build: `system/build_portable_exe_tm.bat`. Do not mix TM into the standard field ZIP.

---

## Data-flow graph

```
price PDF
  -> price_pdf_parser.parse_price_pdf
  -> update device_master.json + app_state.json
  -> batch_service.quote_variants / run_batch / run_individual
  -> quote_service.build_quote
  -> pdf_renderer.render_quote
  -> output/<見積PDF|見積PDF_36回|見積PDF_24回|TM variants>/<tree>/<file>.pdf
```

Include-list: `included_models.json` is the allow-list for 48-mode batch **and** the individual-quote Combobox. If missing, `excluded_models.json` is inverted. If neither exists, all on-sale models. 36-mode ignores this and uses `installment_36_targets.json`.

---

## Agent change protocol

1. Read this file + **`AGENT_CHANGE_HISTORY.md`** + Japanese spec if changing product behavior. Obey `.cursor/rules`.
2. Keep field `README.txt` simple; put depth in `docs/` (architecture here; decisions in change history).
3. Bump `APP_VERSION` when releasing a user-visible milestone; sync titles, this file, `AGENTS.md`, and append change history. For **standard** field ZIP ships: also rewrite `N:\01.ツールズ\見積もり作成ツール\latest.json` (`version` / `zip`) and `system/data/latest.example.json`. Never mix TM packages into that file.
4. Field Japanese `.txt` for ships: **UTF-8 with BOM** (`utf-8-sig`). Arrange uses `_write_utf8_bom`. Bat files for build stay ASCII/CRLF **without** BOM.
5. Update tests for rule changes.
6. Do not regenerate thousands of PDFs unless the human asks.
7. After behavior changes, append a dated log line in `AGENT_CHANGE_HISTORY.md`.

### Portable field texts

- Source: root `README.txt`, `system/docs/リリースノート_v{APP_VERSION}_現場向け.txt`
- Package: `system/_arrange_portable.py` → package root; UTF-8 BOM + CRLF
- Pure `?` characters in Japanese files mean **content was destroyed** (not “open as Shift_JIS”); rewrite from history / human source

---

## Version history (docs)

| Ver | Notes |
|-----|-------|
| 1.5 | Formal release: official iPhone 18 PDF; remove temp overlay; PDF-order picker; skip MM-route; strip model-cell annotations; ignore 備考.
| 1.4.14β | Restore category/model/sales path; later 2026-09-16 removed temp overlay, PDF-order picker, skip MM-route. |
| 1.4.13β | Quote output: model folder only as deepest leaf before PDF. |
| 1.4.12β | Include-picker: temporary devices first; collapsible category sections. |
| 1.4.11β | Temporary iPhone 18 Pro / Pro Max overlay — removed after official price PDF. |
| 1.4.1 | 新トクするサポート＋査定不足時の支払を「最大44,000円(不課税)」に変更。48-mode model picker is include-list (`included_models.json`) instead of exclude-list. |
| 1.4.10β | 24回割賦 individual window; standard startup update check via N: `latest.json` (open ZIP; no auto-replace). |
| 1.4.9β | Standard individual: super/hyper may omit IRS while keeping 弊社特別割引 (all allowed sales types). Batch still IRS+discount set only. |
| 1.4.8β | iPad/AndroidTab packets 1/5/50GB only; allow ouchi+5GB for those (no 20GB tier). |
| 1.4.7β | Category gates: iPad/データ通信/AndroidTab no MNP・番号移行; light/super/hyper only for iPhone・Android. |
| 1.4.6β | Individual exception: super/hyper + IRSなし + discount (was MNP/新規 only until 1.4.9β). Separate **TM兼任事業部** package (`tm_special`) unlocks individual (sales×light family, capacities, IRS radios). Batch unchanged. |
| 1.4.5β | Super/hyper = IRS+discount set only; MNP/新規 create super/hyper only when checkbox ON (with IRS); default Biz-only for those sales types. |
| 1.4.4β | (superseded) MNP/新規 default IRSなし with discount kept — corrected in 1.4.5β. |
| 1.4.3β | PDF row 安心サポート; larger 機種代金総額; previous-Toku note kishu-only. |
| 1.4.2β | IRS folders only for super/hyper; optional IRSなし for MNP/新規 only (not 機種変更); optional light (no IRS); selectable normal-IPS display; Pixel 11 merged-row parse; include-list refresh from latest price PDF. |
| 1.4.0 | Packet-change attention note (5GB/20GB → 50GB不可) only on hyper_light with 5GB or 20GB. |
| 1.3.5 | Super/hyper restored for MNP/新規 (番号移行 still excluded); default no-IRS (安心サポートなし) + discount variants for MNP/新規 super/hyper (folders IRSあり/IRSなし); 36回割賦 prototype (case R): radio UI, targets JSON with exclusions + edit button, checkbox individual window, output `見積PDF_36回`; PDF version footer bottom-right; 36 quotes omit 新トクするサポート＋ note. |
| 1.3.4 | Super/hyper **only for 機種変更**; no super/hyper for MNP/新規/番号移行. Light remains non-kishu. IRSあり layout / company seed unchanged from 1.3.3. |
| 1.3.3 | Initial-fee / support folders only when branching; Biz light -500; super/hyper under IRSあり (サブスク/一括表記/通常ランニング); EXE company empty FAX merge; kishu no light; sales display 機種変更. |
| 1.3.2 | Upfront IPS plan folders (JP names); running warranty columns 24/36; super_light 50GB only; subscr. filename without tier; PDF extra light discount label `弊社特別割引`; developer spec v1.3; field package ZIP |
| 1.3.1 | PDF layout polish; company.json gitignored; UTF-8 BOM field texts; release-note encoding incident |
| 1.3 | Default `special_3000`; optional standard fee via `include_standard_initial_fee` (legacy `include_special_initial_fee` mapped in checkpoints); 「除外する機種」; IPS upfront default off; info (i) → alphascript homepage; masters 20260731; force-all wording |
| 1.2 | Field options/notes packaging refresh (mostly superseded by 1.3 defaults) |
| 1.1 | Fixed output root; exclusions (+ individual dropdown); ouchi skips 5GB; dual human/AI docs; `.cursor` documented |

**Detail & session log:** always prefer `system/docs/AGENT_CHANGE_HISTORY.md` over short row above.
