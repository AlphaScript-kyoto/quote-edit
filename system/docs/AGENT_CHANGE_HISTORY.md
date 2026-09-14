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
| App version | See `APP_VERSION` in `system/quote_system/config.py` (currently **1.4.14β**) |
| Display name | 見積もり一括作成 |
| Window title | `app_window_title()` — standard `見積もり一括作成  ver.{APP_VERSION}` (TM: `…（TM兼任事業部用）  ver.…`) |
| Editions | `standard` (field) / `tm_special` (TM兼任事業部・個別解除). Env `QUOTE_APP_EDITION` or bundled `app_edition.json` |
| Dist | `portable/見積もり一括作成ver{APP_VERSION}/` ；TM: `…_TM兼任事業部用ver{APP_VERSION}/` |
| Japanese spec | `system/docs/開発者向け仕様書_v1.4.md` (v1.3 / v1.1 stubs) |
| Company contacts | Local-only `system/data/company.json` (gitignored). Template: `company.example.json` |

---

## Doc map

| File | Role |
|------|------|
| `AGENTS.md` | Short agent entry |
| `system/docs/AI_CONTEXT.md` | Architecture |
| `AGENT_CHANGE_HISTORY.md` (this) | Decisions / session log |
| `開発者向け仕様書_v1.4.md` | Japanese human handoff (current) |
| `開発者向け仕様書_v1.3.md` / `v1.1.md` | Stubs → v1.4 |
| `README.txt` | Field operators (short) |
| `system/README.md` | Developer entry (JP) |

Field Japanese `.txt` for ships: UTF-8 with BOM (`utf-8-sig`). Arrange uses `_write_utf8_bom`.

---

## Hard invariants

1. Quote relative path LOCKED: category / model / sales / … / pdf (confirm with user before changing).
1. Fixed output roots (no per-run timestamp folders): 48 `見積PDF` / 36 `見積PDF_36回` / 24 `見積PDF_24回` (+ TM `*_TM特例*` variants).
2. Include-list (`included_models.json`) beats force-all for 48-mode; drives individual Combobox. 36 uses `installment_36_targets.json` only. Legacy exclude-list only if include missing.
3. No ouchi (おうち割 SB光あり) + 5GB on phones. Exception: iPad/AndroidTab (and TM unrestricted individual may allow more).
4. Upfront IPS: UI picks `lump` or `monthly_as_running`.
5. Portrait A4; prefer one-page PDFs.
6. No bulk regen of thousands of PDFs unless asked.
7. Real phones/addresses must not be in git.
8. Biz package super light: **50GB only** (standard; TM individual unlock may differ).
9. Batch: super/hyper = IRS+discount set only. Individual: may omit IRS while keeping 弊社特別割引.
10. Standard startup update check via share `latest.json`; update that file on every standard ship.

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

### 2026-08-07 - 36 targets: exclusion rules
- installment_36_targets.json now supports exclude_model_keys_exact / exclude_model_key_contains; exclusion wins over inclusion (categories/contains/exact).
- Seed excludes dignobx3plus and dignoke-tai4forbiz per user request (13 -> 11 target models on current PDF).

### 2026-08-07 - 36-mode: individual buttons follow mode
- Main window: the two individual-quote buttons are mode-gated. 36 mode disables the 48 button; 48 mode disables the 36 button. Prevents pressing the wrong-mode entry.

### 2026-08-07 - Individual window: create button moved to header
- Both individual windows (48 and 36): the PDF-create button now sits top-right next to the window title, and the status text moved under the header, so they are always visible regardless of window height (previously hidden below the fold on small screens).

### 2026-08-07 - PDF footer: tool version stamp
- Every quote PDF now draws a small gray footer at the bottom-right margin: APP_DISPLAY_NAME ver.APP_VERSION (canvas onPage draw at y=2.2mm, 5pt), outside the flowable area so one-page packing is unaffected. Applies to all quotes (48 and 36).

### 2026-08-07 - Revert super/hyper to MNP/shinki + default no-IRS variants
Terminology fixed by user: IPS = repair warranty (shuuri hoshou), IRS = anshin support (PDF row: anshin hoshou service).
- is_sales_plan_allowed: super/hyper now allowed for kishu-henkou, MNP, shinki; still NOT for bangou-ikou (partial revert of the 1.3.4 kishu-only rule).
- quote_variants: for super/hyper on MNP/shinki only, a support=None (no-IRS) variant is generated BY DEFAULT (discount kept; _NO_IRS_DEFAULT_SALES_TYPES).
- Folder layout for merged super/hyper: IRS-ari / IRS-nashi frames by support presence; inner anshin-support ari/nashi folder removed (no duplication). IPS-nashi frame unchanged.
- Notes consistency verified: without IRS the anshin-support note and PDF row disappear; discount row (heisha tokubetsu waribiki) stays; IPS-related notes unaffected.
- Variant counts: standard 57 -> 85; full-pattern 3164 (was 2380). Tests updated + new PDF content test for MNP hyper no-IRS.

### 2026-08-07 - Release ver.1.3.5
QA (strict) before bump, all green:
- 36 unit tests OK.
- Exhaustive variant rule scan (iPhone default 85 variants): no super/hyper on 番号移行, no-IRS only on MNP/新規 super/hyper, no light-on-kishu, super=50GB only, no 1GB on light family, no ouchi+5GB.
- Output-path collision check: 0 collisions (default 85 / full 3164 / feature phone 48).
- Real PDF content checks: super MNP no-IRS (no 安心保証サービス row, no 安心サポート note, 弊社特別割引 kept, IPS note kept, IRSなし path, 1 page, footer), hyper 新規 IRS-yes, 番号移行 super rejected, 36-mode (single 1-36 column, no 新トク note, footer).
Bump: APP_VERSION 1.3.4 -> 1.3.5; AGENTS.md / AI_CONTEXT.md (version table row added) / system/README.md / field README.txt updated; field release note リリースノート_v1.3.5_現場向け.txt written UTF-8 BOM + CRLF.
Terminology (user-defined, use consistently): IPS = 修理保証サービス (repair warranty), IRS = 安心サポート (support; PDF row label 安心保証サービス).

### 2026-08-17 - Release ver.1.4.0
- Attention note for packet plan change restriction (5GB/20GB cannot move to 50GB; unlimited only) is shown only when plan_id=hyper_light and data_plan is 5GB or 20GB. Omitted for other plans/capacities. Tests added.
- Bump APP_VERSION 1.3.5 -> 1.4.0; docs / field README / release note UTF-8 BOM.

### 2026-08-17 - Portable package bundles 36-installment price PDF
- _arrange_portable.py now copies 機種代金一覧表/36回割賦/*.pdf into the portable folder (in addition to root price PDFs). Confidential 36 PDF stays gitignored; only local/ZIP distribution.

### 2026-08-18 - Portable package always bundles usage-guide PDF
- _arrange_portable.py copies the newest repo-root PDF matching *使い方*.pdf (filename may include a version) next to the EXE. Missing guide fails the package step so later versions cannot ship without it. PDF stays gitignored; ZIP only.

### 2026-08-18 - 36-installment PDF row label
- Monthly breakdown device row was hardcoded as 機種代金（48分割） even for 36-month quotes. Now uses quote installment_months (36 -> 機種代金（36分割）). Test added.

### 2026-08-20 - Release ver.1.4.1
- Shin-toku support+ note: unpaid-assessment penalty is now 最大44,000円(不課税); removed 20,000円 residual-cap wording. Still omitted on 36-month quotes.
- 48-mode model picker is an include-list (作成する機種 / included_models.json). Legacy excluded_models.json is inverted only when include file is absent. New PDF models are not generated until checked. 36-mode still uses installment_36_targets.json.
- Bump APP_VERSION 1.4.0 -> 1.4.1.

### 2026-08-20 - IRS default + selectable normal IPS display
- Batch default for IRS is now `あり` only. `IRSなし` variants are generated only when `include_no_support=True` (UI checkbox).
- Removed automatic `IRSなし` generation for MNP/新規 on super/hyper plans; this is now explicit opt-in.
- Added batch-level normal IPS display selection: generate either `lump` or `monthly_as_running` based on UI selection.
- Checkpoint payload now stores `include_upfront_lump` / `include_upfront_running` so resume preserves display-mode choice.
- Updated tests for the new default variant counts and checkpoint call signature.

### 2026-08-20 - Pixel 11 parse + IRS-first folders
- Price PDF table extraction sometimes merges a whole “新機種” block (e.g. all Google Pixel 11 SKUs) into one cell. `_expand_merged_device_rows` now splits by model newlines so each SKU becomes its own device.
- Opening ［作成する機種］ now re-imports the selected/latest price PDF into `device_master.json` so newly listed models appear immediately (unchecked until include-listed).
- Super/hyper quotes always include IRS (安心サポート). `build_quote` rejects super/hyper with support_plan_id=None. Batch `include_no_support` only adds IRSなし for `light`.
- No `Bizパッケージ＋` folder: IRSなし + IPS branches is enough to identify Biz. Light still uses its plan folder (capacity overlap with hyper).
- IPS branch folder names are unified: `IPSサブスク` / `IPS一括表記` / `通常IPSランニングコスト表記`.

### 2026-08-20 - Beta ver.1.4.2β
- APP_VERSION -> 1.4.2β (beta portable ZIP).
- IRS-first folders; no Bizパッケージ＋ folder under IRSなし; selectable normal IPS display; Pixel 11 merged-row parse; ［作成する機種］ refreshes from latest price PDF.
- Field release note リリースノート_v1.4.2β_現場向け.txt (UTF-8 BOM).

### 2026-08-20 - IRS on super/hyper only; light optional
- Light never gets IRS (`services.json` auto_mapping excludes light; `build_quote` forces support=None for light).
- Super/hyper default IRSあり + discount. Checkbox `include_no_support` adds super/hyper IRSなし **with discount kept**.
- New checkbox `include_light_plan` (default OFF): batch creates Bizパッケージ＋ライト only when checked.
- Variant counts (iPhone 17 256GB): default 50; with light 71; full flags without light 1988; with light 2576.
- Overwrite beta portable ZIP after rebuild.

### 2026-08-24 - IRS folders only for super/hyper; no kishu IRSなし
- Batch `include_no_support` adds IRSなし only for super/hyper on **MNP/新規** (機種変更・番号移行 excluded).
- Folder `IRSあり`/`IRSなし` only for super/hyper. Biz/light no longer use IRS folder (チェックOFFでは IRSなし フォルダが出ない).
- Checkbox label clarifies 追加 + MNP/新規のみ + 機種変更対象外.
- PDF 機種代金総額 confirmed present (月額表の下); no code change.
- Variant counts with no_support: 64 (was 71); full flags 1792 / with light 2380.

### 2026-08-25 - Beta ver.1.4.3β (PDF label + device total size)
- PDF monthly row label: `安心保証サービス` -> `安心サポート` (attention note unchanged: 携帯電話機安心サポート).
- `機種代金総額` paragraph font 7.6pt -> 10.2pt (+2.6).
- APP_VERSION -> 1.4.3β; field release note; overwrite beta ZIP.

### 2026-08-28 - Previous Toku-suru support note: kishu only
- PDF attention note「前回ご購入時トクするサポート…」is shown only when `sales_type` is 機種変更（機種変更・移動機物品販売）. MNP/新規/番号移行 omit it.

### 2026-09-04 - MNP/新規 default IRSなし; checkbox adds IRSあり
- Super/hyper: 機種変更 remains IRSあり fixed. MNP/新規 default IRSなし (discount kept); checkbox `include_mnp_shinki_irs` adds IRSあり.
- 番号移行 unchanged (no super/hyper → no IRS).
- UI checkbox: 「新規／MNPのスーパー／ハイパーにIRSあり版も追加…」.
- Attention note「携帯電話機安心サポートについて…」already gated by `support=True`; test asserts absent when IRSなし.
- Legacy kwarg/checkpoint key `include_no_support` mapped to new flag.

### 2026-09-04 - Beta ver.1.4.4β
- APP_VERSION -> 1.4.4β; field release note; portable ZIP to local + N: shared folder.

### 2026-09-04 - Super/hyper = IRS+discount set; ver.1.4.5β
- Field clarification: IRS and super/hyper additional discount are a set. No IRSなし super/hyper (would keep discount) — do not generate.
- MNP/新規: checkbox OFF → Biz only (no super/hyper). Checkbox ON → super/hyper with IRSあり (+ discount).
- 機種変更 unchanged (super/hyper with IRS). 番号移行 unchanged.
- `build_quote` raises if super/hyper requested with support_plan_id=None.
- APP_VERSION -> 1.4.5β; overwrite portable ZIP.

### 2026-09-04 - Individual exception for IRSなし super/hyper; ver.1.4.6β
- Batch unchanged: super/hyper only as IRS+discount set; never generate IRSなし in batch.
- Individual (`run_individual` / `allow_super_hyper_without_irs=True`): may choose 安心サポートなし while keeping 弊社特別割引.
- UI hint under individual support combobox; folder still `IRSなし` + plan name for path uniqueness.
- APP_VERSION -> 1.4.6β.

### 2026-09-07 - TM individual plan dropdown order
- TM特例個別の料金プラン並び: Bizパッケージ＋ → ライト → スーパーライト → ハイパーライト.

### 2026-09-07 - TM special initial fee 4,500
- TM特例個別のみ: 「事務手数料免除＋初期費用」標準を税抜4,500円（税込4,950円）。通常版の3,000／3,300は維持。
- `run_individual` unrestricted + `special_3000` sets `special_initial_fee_tax_ex=4500`.

### 2026-09-09 - Block MNP/番号移行 for iPad・データ通信・AndroidTab
- Both editions: `is_device_sales_type_allowed` — categories `iPad` / `AndroidTab` / `データ通信` cannot use MNP or 番号移行.
- Enforced in `quote_variants` (batch), `build_quote`, `run_individual`, and individual UI sales dropdown.

### 2026-09-09 - Light family plans only for iPhone / Android
- Both editions: `is_device_plan_allowed` — `light` / `super_light` / `hyper_light` only for categories `iPhone` and `Android`.
- iPad / AndroidTab / データ通信 / ケータイ / キッズフォン etc. get Bizパッケージ＋ only (no light-family batch or individual).

### 2026-09-09 - Beta ver.1.4.7β
- APP_VERSION -> 1.4.7β; field release note; standard portable ZIP to local + N: share.
- TM special ZIP rebuilt to portable only (same APP_VERSION, separate package name).

### 2026-09-09 - Omit SB光 folder for ケータイ
- Category `ケータイ` (1GB only, no ouchi branch): `_quote_relative_path` skips `SB光なし`/`SB光あり` folder level.
- Rebuild ver.1.4.7β ZIPs (no version bump): standard → portable + N:; TM → portable only.

### 2026-09-09 - iPad/AndroidTab packets + ouchi×5GB; ver.1.4.8β
- iPad / AndroidTab: allowed data plans only `1GB` / `5GB` / `50GB` (`is_device_data_plan_allowed`). No 20GB or 無制限.
- Exception to phone rule: ouchi (SB光あり) + 5GB **allowed** for those categories (`allows_ouchi_discount_with_5gb`) because there is no 20GB tier to collapse into.
- Phones / other categories: still skip ouchi+5GB. TM special individual unrestricted still allows ouchi+5GB broadly.
- APP_VERSION -> 1.4.8β; both portable ZIPs; standard also to N: share.

### 2026-09-09 - Standard individual IRSなし for all sales; ver.1.4.9β
- Batch unchanged: super/hyper only as IRS+discount set.
- Individual (`run_individual`): always `allow_super_hyper_without_irs=True` — includes 機種変更 (previously MNP/新規 only on standard).
- Standard individual UI: 「安心サポートなし」 always in combobox; hint says individual-only, discount kept.
- APP_VERSION -> 1.4.9β; both portable ZIPs; standard to N: share.

### 2026-09-14 - 24回割賦 individual window; ver.1.4.10β
- UI: button under 作成タイプ (below 36 radio) opens individual window (`_open_individual_window(24)`). Not a third batch radio.
- Uses main price PDF `payment_24` column (flat monthly); single PDF period `分割支払 1～24回目`.
- Output: `output/見積PDF_24回` (TM: `見積PDF_TM特例_24回`).
- Parser: devices with only 24/36 (no 48) stay `販売中` (commented intent restored).
- 新トクするサポート＋ note omitted for 24 like 36.
- APP_VERSION -> 1.4.10β; both portable ZIPs; standard to N: share.

### 2026-09-14 - Standard update notice via N: latest.json (no version bump)
- Standard edition only: on startup, background-read `N:\01.ツールズ\見積もり作成ツール\latest.json` (≈2.5s timeout; silent if unreachable).
- Compare numeric version tuples (`1.4.10β` → 1.4.10). Newer → dialog; Yes opens Explorer on ZIP; No snoozes that version for today.
- TM special skips entirely. Ignores latest.json if `edition` ≠ `standard`.
- Template: `system/data/latest.example.json`. Ship overwrite of ver.1.4.10β standard ZIP (+ place latest.json on N:).

### 2026-09-14 - Remember latest.json on every standard ship
- Human request: on every version bump / standard ZIP distribute, always rewrite share `latest.json` (and the example template). Agents must not forget this step.

### 2026-09-14 - Docs sync: agent rules + Japanese spec v1.4
- Audited AGENTS / handoff / AI_CONTEXT / AGENT_CHANGE_HISTORY vs code (1.4.10β).
- Fixed contradictions: multi output roots (48/36/24 + TM), include-list (not exclude-first), update check, app_window_title, TM paths/4500 fee.
- Added `開発者向け仕様書_v1.4.md`; v1.3/v1.1 are stubs.
- Refreshed `system/README.md`.


### 2026-09-14 - Temporary iPhone 18 Pro / Pro Max (ver.1.4.11β)
- Field emergency: official price PDF not yet published; add `data/temporary_devices.json` + `temporary_devices.py` merge overlay (48-only).
- Naming follows existing iPhone style (`iPhone 18 Pro(256GB)`, `iPhone 18 Pro Max(...)`). Capacities 256/512/1TB/2TB (user typo 215GB interpreted as 512GB).
- Installments mapped as 1_12=13_24 (months 1-24) + 25_48. Pro Max 256GB kishu 25-48 adjusted 5500->5550 so periods match stated total 295,920.
- Overlay not persisted into device_master.json; always force-included for batch/individual while enabled. Standard + TM both use same data.
- APP_VERSION -> 1.4.11β; both portable ZIPs; standard to N: + latest.json.


### 2026-09-14 - Include picker UX (ver.1.4.12β)
- Temporary overlay models appear at the top under `臨時追加（価格表PDF未反映）`.
- Other models grouped by category with collapsible headers; open/close all; per-category select/clear.
- Individual 48-mode model list also sorts temporary devices first.
- APP_VERSION -> 1.4.12β; both portable ZIPs; standard to N: + latest.json.


### 2026-09-14 - Restore output path without model folder (no version bump)
- Field request: quote PDF tree is category / sales-type / SB光 / … ; model is distinguished by PDF filename only (no per-model folder).
- Overwrite portable ZIPs at current APP_VERSION; standard to N: + latest.json.


### 2026-09-14 - Model folder only as deepest leaf (no version bump)
- Quote path: category / sales / SB光 / … / model / filename.pdf (model folder is the last folder before the PDF).
- Overwrite portable ZIPs at current APP_VERSION; standard to N: + latest.json.


### 2026-09-14 - Quote path leaf model folder (ver.1.4.13β)
- Quote path: category / sales / SB光 / fee/IRS/plan/IPS… / **model** / filename.pdf (model folder is only the deepest folder before the PDF). Model folder uses compact name without spaces/underscores (same as PDF basename model token).
- APP_VERSION -> 1.4.13β; both portable ZIPs; standard to N: + latest.json.


### 2026-09-14 - Restore category/model path + temp 24-split (ver.1.4.14β)
- **LOCKED** output tree: `category / model / sales / SB光… / … / file.pdf` (model folder directly under category; compact name without underscores).
- Agents must confirm with the user before any future path-layout change.
- Temporary iPhone 18 Pro/Max: `payment_24 = total // 24` (pure split of 機種代金総額).
- APP_VERSION -> 1.4.14β; both portable ZIPs; standard to N: + latest.json.

## Release checklist
1. APP_VERSION
2. Titles match
3. unittest
4. Field notes UTF-8 BOM
5. Append this file + sync AI_CONTEXT/AGENTS/Japanese spec
6. Never commit real company.json
7. Portable ZIP build only after local company.json has field FAXes
8. Never commit confidential 36 price PDFs
9. TM edition ZIP is separate from standard field ZIP
10. **Standard release:** update `N:\01.ツールズ\見積もり作成ツール\latest.json` (`version` + `zip`) and `system/data/latest.example.json` whenever the field ZIP changes (including same-version overwrite ships)

## Anti-patterns
Landscape PDF; CP932 round-trip for JP texts; committing phones; ouchi+5GB on phones (iPad/AndroidTab exception exists); inventing attention notes; pointing agents at stale `開発者向け仕様書_v1.3.md` body instead of v1.4.

