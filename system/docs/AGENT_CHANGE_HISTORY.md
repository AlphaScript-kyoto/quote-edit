# Agent change & decision history

**Audience:** coding agents / future AI sessions  
**Language:** English (product UI strings stay Japanese)  
**Purpose:** Full handoff of *why* things are the way they are.

After reading root `AGENTS.md` and `AI_CONTEXT.md`, use **this document** for prior fine-tuning and decisions.
Append a dated entry after user-visible changes.

---

## Current ship target

| Item | Value |
|------|--------|
| App version | See `APP_VERSION` in `system/quote_system/config.py` (currently **1.3.2**) |
| Display name | 見積もり一括作成 |
| Window title | `見積もり一括作成  ver.{APP_VERSION}` |
| Dist | `portable/見積もり一括作成ver{APP_VERSION}/` |
| Japanese spec | `system/docs/開発者向け仕様書_v1.3.md` |
| Company contacts | Local-only `system/data/company.json` (gitignored). Template: `company.example.json` |

---

## Doc map

| File | Role |
|------|------|
| `AGENTS.md` | Short agent entry |
| `system/docs/AI_CONTEXT.md` | Architecture |
| `AGENT_CHANGE_HISTORY.md` (this) | Decisions / session log |
| `開発者向け仕様書_v1.3.md` | Japanese human handoff |
| `README.txt` | Field operators (short) |

Field Japanese `.txt` for ships: UTF-8 with BOM (`utf-8-sig`). Arrange uses `_write_utf8_bom`.

---

## Hard invariants

1. Output root: `output/見積PDF/` only.
2. Exclusions beat force-all; hide models from individual Combobox.
3. No ouchi (おうち割 SB光あり) + 5GB.
4. Upfront IPS: `lump` and/or `monthly_as_running`.
5. Portrait A4; prefer one-page PDFs.
6. No bulk regen of thousands of PDFs unless asked.
7. Real phones/addresses must not be in git.
8. Biz package super light: **50GB only**.

---

## Version timeline (summary)

### 1.1
Fixed output root; exclusions; ouchi skips 5GB; dual AI/human docs; `.cursor`.

### 1.2
Field packaging refresh (mostly superseded by 1.3).

### 1.3
- Default fee: `special_3000`; optional `include_standard_initial_fee` (legacy key mapped).
- IPS upfront default off; exclude UI `除外する機種`; info (i) button.

### 1.3.1 + current polish
**PDF:** No. column; monthly order plan/IPS/support/universal/total; red discounts; no title box; `{sales_type}お見積もり`; TEL/FAX one line.
**PDF additional light discounts (display only):** super/hyper light names become **弊社特別割引** (internal `スーパーライト割` / `ハイパーライト割` stay in plans.json).
Biz package row remains `Bizパッケージ＋ 特別割引`.

**Upfront IPS folders:** under `IPS一括型` or `IPS一括型_月額換算` + plan folder `ゴールド24`, `プラチナ36水没`. Filename `model_data.pdf` only.

**Subscription filename:** no tier suffix; folder `IPSサブスク`.

**Running warranty columns:**
- 24 months: dash after month 24
- 36 months (plan B): split 25-36 / 37-48; dash after 36

**super_light:** only 50GB (`is_plan_data_plan_allowed`).

**Encoding incident:** pure ASCII `?` in Japanese files = destroyed content; rewrite + UTF-8 BOM.

**Privacy:** `company.json` gitignored; tests use synthetic contacts.

---

## Code pivots

| Concern | Files |
|---------|-------|
| Version | `config.py` |
| Paths / batch | `batch_service.py` |
| Math / plan rules | `quote_service.py` |
| PDF | `pdf_renderer.py` |
| GUI | `desktop_app.py` |
| Tests | `tests/test_system.py` |

---

## Session log

### 2026-08 - 1.3 / 1.3.1 packaging
Defaults, fee flag rename, PDF polish, BOM field texts, company.json out of git.

### 2026-08-06 - IPS folders + warranty + super_light 50GB
Folder JP names; running 24/36 rules; subscription filename without tier.

### 2026-08-06 - PDF additional discount label
Display **弊社特別割引** for super/hyper light rows (internal names unchanged).

### 2026-08-06 - Docs repair + history scrub
Rewrite this file (fix pure-`?` corruption). Japanese developer spec to v1.3. Git history rewrite removes phone/address blobs (approved).

### 2026-08-06 - Release ver.1.3.2
- Bump APP_VERSION to 1.3.2; field release note; portable ZIP packaging.
- Includes: IPS plan folders, warranty columns, super_light 50GB only, 弊社特別割引 PDF label, developer spec v1.3.

### 2026-08-06 - Display name for 機種変更
Folder path and PDF heading show **機種変更** (omit trailing 「・移動機物品販売」). Master key and price lookup unchanged. ver stays 1.3.2.

## Release checklist
1. APP_VERSION
2. Titles match
3. unittest
4. Field notes UTF-8 BOM
5. Append this file + sync AI_CONTEXT/AGENTS/Japanese spec
6. Never commit real company.json

## Anti-patterns
Landscape PDF; CP932 round-trip for JP texts; committing phones; ouchi+5GB; inventing attention notes.
