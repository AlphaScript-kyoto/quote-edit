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
| App version | See `APP_VERSION` in `system/quote_system/config.py` (currently **1.3.4**) |
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

### 2026-08-07 - Initial-fee folder only when branching
Default `special_3000` (PDF tax-in ¥3,300) omits fee folder. Folder only for `standard` (事務手数料あり), or for both modes when `include_standard_initial_fee` (special side uses `初期費用3300円`).

### 2026-08-06 - Support folder only when branching
Omit `安心サポートあり/なし` when that plan has a single support outcome (forced auto support for light plans; no support for biz+). Add folders when both variants are generated (`include_no_support`) or light plan explicitly has no support / non-auto plan has support.

### 2026-08-07 - Biz light plan + kishu rules
Add light (Bizパッケージ＋ライト, additional -500 yen; not 1GB). Forced support XS like super. **Not used for 機種変更**. On 機種変更 + IPS subscription, super/hyper share folder Bizパッケージ＋特別割引. PDF shows ライト割 as 弊社特別割引.

### 2026-08-07 - Kishu super/hyper PDFs under SB光
For 機種変更 + super/hyper standard path, omit plan folder (特別割引) and place PDF directly under SB光なし/あり. Biz+ keeps its folder. Branched IPS/fee still get intermediate folders.

### 2026-08-07 - Kishu upfront IPS display folders
機種変更 super/hyper: no plan folders; under SB光 use 一括表記 / ランニングコスト表記 then IPS plan (ゴールド24 etc.). Biz+ unchanged.

### 2026-08-07 - Release ver.1.3.3
Ship 1.3.3: branching fee/support folders; Biz light plan; kishu path layout (IPS一括表記 / IPSランニングコスト表記); display 機種変更 short name.

### 2026-08-07 - Super/hyper path merge for all sales types
Extend kishu-only flatten to **MNP / 新規 / 番号移行 / 機種変更** alike.
- `super_light` + `hyper_light`: no plan-name folder; subscription PDF under SB光; upfront under 一括表記 / ランニングコスト表記 then IPS plan token.
- Do **not** merge `light` (容量 overlap with both) — keeps `Bizパッケージ＋ライト`.
- `biz_plus` unchanged. Capacity uniqueness keeps zero path collisions across ~18k variants.

### 2026-08-07 - IRSあり parent + FAX seed merge
- Super/hyper under SB光: sibling folders **Bizパッケージ＋** and **IRSあり**; under IRSあり → `IPSサブスク` / `IPS一括表記` / `通常IPSランニングコスト表記` (+ plan token). IPSなし stays outside IRSあり.
- EXE `company.json`: on launch, fill empty `phone`/`fax`/`postal_address` (incl. department_contacts) from bundled company so field LOCALAPPDATA does not silently drop RT FAX while dev `system/data` still has it.
- PDF still hides FAX line when fax is empty string (TM etc.).

### 2026-08-07 - Portable company.json required + individual PDF QA
- `build_portable_exe.bat` refuses build without `system/data/company.json`; `_check_company_for_portable.py` requires RT/CRM/AQ phone+fax present (values not logged). Arrange step verifies bundled company exists.
- Expanded individual-quote tests: real PDF one page, RT header, super/hyper `IRSあり` paths, kishu light rejected.

### 2026-08-07 - Super/hyper parent folder rename IPSあり → IRSあり
User terminology: **IRS** = 安心保証サービス frame. Super/hyper PDFs live under `IRSあり` (not `IPSあり`). Subfolders for SoftBank repair billing stay `IPSサブスク` / `IPS一括表記` / `通常IPSランニングコスト表記`; no-repair stays `IPSなし` outside IRSあり.

### 2026-08-07 - Release ver.1.3.4 (super/hyper kishu-only)
Business rule: MNP / 新規 / 番号移行 customers do **not** join super or hyper light → do not generate those quotes.
- `is_sales_plan_allowed`: `super_light`/`hyper_light` only when sales = 機種変更・移動機物品販売.
- `light` still forbidden on 機種変更; still allowed on MNP/新番.
- Batch default variants: 78 → 57 (iPhone example); full-pattern 3556 → 2380.
- Bump `APP_VERSION` 1.3.4; field release note UTF-8 BOM.

### 2026-08-07 - 1.3.4 prototype: 36回割賦 mode (case R)
- UI radio: 通常48 / 36回割賦; open folder + output split (`見積PDF` vs `見積PDF_36回`).
- PDF dir: `機種代金一覧表/36回割賦/`; parse flat monthly (`payment_36_flat`), validate monthly*36=total.
- Target filter: `data/installment_36_targets.json` (categories e.g. ケータイ + model_key contains: 16e/17e/wish4/bx3). Field-editable.
- Quote periods: single column `分割支払 1～36回目` when installment_months=36.
- Confidential 36 PDF must stay local (not git).

### 2026-08-07 - 36-mode UX: exclusion disabled, dedicated individual buttons
- 36-installment mode ignores the exclusion feature entirely: main-window button disabled with status note, batch and individual paths no longer filter by excluded_models.json. Targets come only from installment_36_targets.json.
- Individual quote entry split into two explicit buttons: (48-normal) and (36-installment); window no longer follows the main-mode radio.

### 2026-08-07 - 36-mode: checkbox model picker + drop 48-only attention note
- Individual 36 window: model dropdown replaced with a checkbox list of all JSON-target models (select-all / clear buttons); generation loops selected models, per-model data-plan filtering, aggregated result dialog.
- PDF attention notes: the SHIN-TOKU SUPPORT+ paragraph (48-installment contract wording) is omitted when quote installment_months == 36 (test added).
- import_installment_36_master now caches by PDF sha256 into device_master_36.json so per-model run_individual calls do not re-parse the PDF.

### 2026-08-07 - 36-mode: edit-targets button
- Main window: when 36-installment mode is selected, a button next to the disabled exclusion status opens installment_36_targets.json in the default editor (seeds the file first if missing; notepad fallback). Hidden in 48 mode.

## Release checklist
1. APP_VERSION
2. Titles match
3. unittest
4. Field notes UTF-8 BOM
5. Append this file + sync AI_CONTEXT/AGENTS/Japanese spec
6. Never commit real company.json
7. Portable ZIP build only after local company.json has field FAXes
8. Never commit confidential 36 price PDFs

## Anti-patterns
Landscape PDF; CP932 round-trip for JP texts; committing phones; ouchi+5GB; inventing attention notes.

