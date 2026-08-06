# AI Context - Infinity Quote Batch App (ver.1.3.1)

**Purpose:** Machine-oriented specification for coding agents. Prefer this file + root `AGENTS.md` over guessing.

**Human Japanese handoff:** `system/docs/開発者向け仕様書_v1.3.md`  
**Decision / change history (AI):** `system/docs/AGENT_CHANGE_HISTORY.md` — **read for prior tuning, defaults, PDF micro-layout, packaging encoding faults**  
**Field ops (Japanese, short):** `README.txt`  
**App version constant:** `quote_system.config.APP_VERSION` -> currently `"1.3.1"`  
**Cursor IDE rules:** `.cursor/rules/` (see section below)

---

## Product summary

Local Windows desktop app that reads SoftBank corporate device price-list PDFs and generates many quote PDFs under a fixed output tree. No cloud APIs.

Stack: Python 3, tkinter GUI, pdfplumber, reportlab. Optional PyInstaller portable EXE.

Display name: `見積もり一括作成` (`APP_DISPLAY_NAME`). Window title bar must show `見積もり一括作成  ver.{APP_VERSION}` (drag handle area).

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
2. Point Japanese human successors to `開発者向け仕様書_v1.3.md`
3. Restate hard invariants (fixed output root, exclusions, no ouchi+5GB, one-page PDF, fee defaults, field UTF-8 BOM, no bulk regen unless asked)
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
Human developer -> 開発者向け仕様書_v1.3.md + AGENT_CHANGE_HISTORY.md
AI / Cursor     -> AGENTS.md + this file + AGENT_CHANGE_HISTORY.md + .cursor/rules/*.mdc
```

---

## Repository map (source of truth)

```
quote-edit/
  アプリ起動.bat                    # launch GUI (dev)
  README.txt                  # field user guide (JP, keep simple)
  機種代金一覧表/                      # drop price PDFs here (UPDATE_DIR)
  output/見積PDF/               # fixed output root (QUOTE_OUTPUT_ROOT)
  AGENTS.md                   # agent entry
  .cursor/rules/              # always-on Cursor agent guidance
  system/
    desktop_app.py
    quote_system/
    data/
    tests/
    docs/開発者向け仕様書_v1.3.md
    docs/開発者向け仕様書_v1.1.md  # stub pointer only
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
| `DATA_DIR` | `system/data/` | `%LOCALAPPDATA%/InfinityQuoteApp/data/` |
| `OUTPUT_DIR` | `APP_ROOT/output` | same beside EXE |
| `UPDATE_DIR` | `APP_ROOT/機種代金一覧表` | same beside EXE |

`QUOTE_OUTPUT_ROOT = OUTPUT_DIR / "見積PDF"`.

---

## Data-flow graph

```
price PDF
  -> price_pdf_parser.parse_price_pdf
  -> update device_master.json + app_state.json
  -> batch_service.quote_variants / run_batch / run_individual
  -> quote_service.build_quote
  -> pdf_renderer.render_quote
  -> output/見積PDF/<tree>/<file>.pdf
```

Exclusion: `excluded_models.json` skips batch targets **and** hides models from individual-quote Combobox.

---

## Agent change protocol

1. Read this file + **`AGENT_CHANGE_HISTORY.md`** + Japanese spec if changing product behavior. Obey `.cursor/rules`.
2. Keep field `README.txt` simple; put depth in `docs/` (architecture here; decisions in change history).
3. Bump `APP_VERSION` when releasing a user-visible milestone; sync titles, this file, `AGENTS.md`, and append change history.
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
| 1.3.1 | PDF layout polish; upfront IPS folders (JP names); running warranty columns; super_light 50GB only; subscr. filename without tier; PDF light discounts as 弊社特別割引; company.json gitignored; developer spec v1.3 |
| 1.3 | Default `special_3000`; optional standard fee via `include_standard_initial_fee` (legacy `include_special_initial_fee` mapped in checkpoints); 「除外する機種」; IPS upfront default off; info (i) → alphascript homepage; masters 20260731; force-all wording |
| 1.2 | Field options/notes packaging refresh (mostly superseded by 1.3 defaults) |
| 1.1 | Fixed output root; exclusions (+ individual dropdown); ouchi skips 5GB; dual human/AI docs; `.cursor` documented |

**Detail & session log:** always prefer `system/docs/AGENT_CHANGE_HISTORY.md` over short row above.
