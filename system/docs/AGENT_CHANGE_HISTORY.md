# Agent change & decision history

**Audience:** coding agents / future AI sessions  
**Language:** English (product UI strings stay Japanese)  
**Purpose:** Full handoff of *why* things are the way they are ù not only architecture.

After reading root `AGENTS.md` and this fileùs parent `AI_CONTEXT.md`, use **this document** when:

- Resuming work after a long gap or a new chat
- Something ùused to workù or ùwas already fixedù
- Packaging text looks corrupted
- Defaults / parameter names feel inconsistent
- PDF layout rules are unclear

When you ship a user-visible behavior change, **append a dated entry** at the bottom of ùSession / decision logù (and bump the version table in `AI_CONTEXT.md` / `AGENTS.md` if `APP_VERSION` changes).

---

## Current ship target (as of 2026-08)

| Item | Value |
|------|--------|
| App version | **1.3.1** (`system/quote_system/config.py` ? `APP_VERSION`) |
| Display name | `????????` |
| Window title | `????????  ver.1.3.1` (two spaces after name is existing style ù match `desktop_app` / drag bar) |
| Dist folder / ZIP | `portable/????????ver{APP_VERSION}/` and `.zip` |
| Price master context | list PDF pattern `???????20260731??.pdf` under `???????/` |
| Japanese human spec filename | still `????????_v1.1.md` (content lags version numbers ù see ùDoc driftù) |

---

## Doc map (who reads what)

| File | Role |
|------|------|
| `AGENTS.md` | Short agent entry + hard product rules |
| `system/docs/AI_CONTEXT.md` | Architecture, paths, data flow, Cursor `.cursor` |
| **`system/docs/AGENT_CHANGE_HISTORY.md` (this file)** | Decision log, fine-tuning, pitfalls, parameter renames |
| `system/docs/????????_v1.1.md` | Japanese for human successors (partially stale on version digits) |
| `README.txt` | Field operators only ù **keep short**; no architecture dump |
| `system/docs/???????_v{APP_VERSION}_????.txt` | Optional field release note; ship with portable package |
| `.cursor/rules/quote-edit-handoff.mdc` | Always-on Cursor inject (points here) |

Field copy encoding: **UTF-8 with BOM** (`utf-8-sig`) for root `README.txt` and field release notes. Package step rewrites via `_write_utf8_bom` in `system/_arrange_portable.py`.

---

## Hard invariants (do not regress)

Copied for agents who only open this history file ù full wording in `AGENTS.md`:

1. Output root fixed: `output/??PDF/` (merge/overwrite; no dated batch folders).
2. `excluded_models.json` beats ùforce regenerate allù; excluded models hidden from individual-quote Combobox.
3. No **?????SB???? + 5GB** quotes (same money as 20GB).
4. Upfront IPS can produce `lump` and `monthly_as_running` (separate output folders).
5. Portrait A4 only; prefer **one page** even with worst-case attention notes.
6. Do not bulk-regenerate thousands of PDFs unless the human explicitly asks.
7. Prefer editing **source** under `system/quote_system/`, `desktop_app.py`, `system/data/`, tests, docs ù not `portable/` or `system/work/` as truth.

---

## Version timeline (product)

### 1.1 (baseline handoff era)

- Fixed output under `output/??PDF/`.
- Exclusions + individual-quote dropdown hide.
- Ouchi skips 5GB.
- Dual docs: AI English + Japanese developer spec; `.cursor` documented.
- Title bar must show `ver.{APP_VERSION}`.

### 1.2 (transitional packaging)

- Field options / notes refresh; packaging paths established.
- Superseded operationally by 1.3 UI defaults and masters; keep older release note files if present for history only.

### 1.3 (behavior defaults + field UX)

Shipped product decisions (still valid unless later note says otherwise):

| Topic | Decision | Where |
|-------|----------|--------|
| Default initial fee | **Special 3000**: ??????? + ???? 3,000?????????? 3300 ?? | `quote_service` / `batch_service` `special_3000` |
| Optional standard fee | Checkbox drives **`include_standard_initial_fee`** (not inverted ùspecialù flag) | `batch_service.quote_variants`, GUI |
| Legacy checkpoint | Old payloads may still say `include_special_initial_fee` ? map via `_checkpoint_include_standard_fee` | `batch_service.py` |
| IPS upfront batch | Default **off** (`upfront_var = False`) | `desktop_app.py` |
| Exclude UI wording | **????????** (not ùexclude modelsù English in UI) | `desktop_app.py` |
| Force-all wording | Explicit: on = rebuild all non-excluded active models; exclusions always win | `desktop_app.py` |
| Info button (i) | Opens `https://alphascript-kyoto.github.io/as-homepage/` | `INFO_HOME_URL` in `desktop_app.py` |
| AQ department | Per-dept contact fields supported; real values stay local-only | `company.json` (gitignored); `company.example.json` in git |
| Price list | Masters refreshed from **20260731** update PDF | `???????/` + parsed `device_master` / tests |
| SmartScreen note | Mentioned for field users in `README.txt` | field doc only |

**Parameter rename (important when reading old code/checkpoints):**

- `include_special_initial_fee` ? **`include_standard_initial_fee`**
- Semantics: default batch = special only; optional **add** standard 4500 path when flag true.
- Checkpoint helper still understands legacy key for resume.

### 1.3.1 (PDF layout polish + contacts + packaging text)

#### PDF layout (`pdf_renderer.py`)

| Topic | Decision |
|-------|----------|
| Line item No. column | `No.` first column on initial-fee and monthly tables; 1-based via `_with_row_numbers` |
| Title box | **Removed** ù no decorative frame around model/title |
| Subtitle under model | `{sales_type}????` (fallback `????`) |
| Monthly row order | Voice/plan/device lines ? **????IPS** (if shown monthly) ? **????** ? **??????????? last before total** ? monthly total |
| Subtotal row | Monthly **subtotal removed**; total only |
| Discount styling | Discount **names + amounts** in **red**; No. column stays normal color |
| Company TEL/FAX | One line in header contact block, e.g. `TEL ù / FAX ù` |
| IPS lump in monthly | Upfront IPS with `lump` stays in **initial** table, not monthly IPS row |
| IPS monthly display | Subscription always monthly row; upfront with `monthly_as_running` uses equivalent monthly |

#### Attention notes (`_attention_notes`)

| Condition | Note behavior |
|-----------|----------------|
| Subscription IPS | Fixed text: `????????????????????????1?????165?????????????` |
| Upfront + `monthly_as_running` | Explain running-cost display + actual lump amount |
| Support present | Infinity support note (separate from SoftBank billing) |
| Ouchi applied | Light set starts next month after circuit open |
| Always / common | Plan next-month apply, SMS/extra, tax note, Biz package, packet plan change rules, ??????????, personal?corp transfer fee, no smart login, iPhone accessory note |

Do **not** invent shorter marketing notes without human approval; field wording is intentional.

#### Company contacts (LOCAL ONLY)

- **Do not commit** real phones or postal addresses.
- Template: `system/data/company.example.json` (placeholders / empty phones).
- Runtime file: `system/data/company.json` (**gitignored**). Departments include TM / RT / CRM / AQ with optional per-department phone, fax, postal_address.
- Renderer: one-line TEL/FAX in header; empty FAX ? do not print a broken `FAX` stub.
- Tests that need contacts must use **synthetic** dicts (placeholders like `000-0000-ù`), never production numbers.

#### Portable packaging

| Topic | Decision |
|-------|----------|
| Bundle price PDF(s) | Copy all `*.pdf` from repo `???????/` into package same folder name |
| README + release note | UTF-8 **with BOM**, CRLF via `_write_utf8_bom` |
| Package name | `{APP_DISPLAY_NAME}ver{APP_VERSION}` (no space before ver) |
| Exclude `.cursor` | Optional in portable; required in source repo |

#### Text corruption incident (2026-08, release note ù?????ù)

**Symptom:** Field release note (and any copy from it) showed only `?` for Japanese, ASCII digits/phones intact. Same before and after unzip.

**Root cause:** Source file on disk was **already** lost ù Japanese replaced by literal ASCII `0x3F` (`?`). Not primarily ùZIP re-encodingù. Classic UTF-8-as-CP932 mojibake looks like garbage kana, not pure question marks.

**Fix:** Rewrite `system/docs/???????_v1.3.1_????.txt` with correct Japanese; save **UTF-8 BOM**; also BOM `README.txt`; arrange step forces `utf-8-sig` when copying; rebuild ZIP.

**Prevention for agents:**

1. Never ùfix encodingù by round-tripping through a code page that cannot represent Japanese without replacement.
2. After writing Japanese `.txt`, verify with Python: `path.read_bytes()[:3] == b"\xef\xbb\xbf"` optional BOM; `read_text(encoding="utf-8-sig")` must not be dominated by `?`.
3. If you see pure `?` lines, the content is **gone** ù restore from this doc / prior good `README` wording / chat, do not try to reverse `?`.
4. PyInstaller bat files stay **ASCII + CRLF, no UTF-8 BOM** (different from field Japanese `.txt`).

---

## Important code pivots (quick index)

| Concern | Primary files |
|---------|----------------|
| Version string | `quote_system/config.py` |
| Batch matrix / fees / IPS modes / checkpoints | `quote_system/batch_service.py` |
| Quote math / ouchi+5GB guard | `quote_system/quote_service.py` |
| PDF one-page layout | `quote_system/pdf_renderer.py` |
| GUI defaults & exclude & info | `system/desktop_app.py` |
| Department phones (local) | `system/data/company.json` (gitignored); example in `company.example.json` |
| Plans / services masters | `system/data/plans.json`, `services.json` |
| Tests | `system/tests/test_system.py` |
| Arrange portable | `system/_arrange_portable.py` |
| Build portable EXE | `system/build_portable_exe.bat` |

### Default fee modes (mental model)

```
Batch default:
  fee_modes = ["special_3000"]
  if include_standard_initial_fee:
      fee_modes also includes "standard"

Individual quote:
  user-selected initial_fee_modes list ? {special_3000, standard}
```

### IPS display modes (mental model)

```
billing_type subscription  ? monthly row always; attention 165?/??
billing_type upfront:
  ips_display_mode=lump              ? lump in ????; not monthly IPS row
  ips_display_mode=monthly_as_running ? monthly equivalent row + attention about real lump
```

### Monthly table visual order (1.3.1)

1. Plan / voice / packet / discounts / device payment lines (as built in `plan_item_rows`)
2. ???????? (if `show_ips_monthly`)
3. ???????? (if support)
4. ???????????
5. ???? (highlighted; no intermediate ??)

---

## GUI defaults snapshot (1.3.x)

| Control | Default | Notes |
|---------|---------|--------|
| Force regenerate all | `True` | Still loses to exclusions |
| IPS ????????+?????? | `False` | User opts in |
| ?????????standard fee variants? | UI-specific; batch flag usually off | Prefer special 3000 by default |
| ?????? | Persisted JSON | Window title/lables use that Japanese phrase |
| Info (i) | Top-right | External browser to homepage |

---

## Known doc drift / cleanup TODOs for agents

1. **`????????_v1.1.md`** still labeled ver.1.1 in headers; product is 1.3.1. Prefer updating version tables or adding a ùpost-1.1 delta ? see AGENT_CHANGE_HISTORYù rather than rewriting whole file mid-incident.
2. Field release notes per version under `system/docs/???????_v*_????.txt` ù keep the **current** `APP_VERSION` file correct; older files are archival.
3. `portable/` ZIP is generated ù never treat it as source of truth for code or masters.
4. If Japanese human asks for ùREADME.md alwaysù, this product deliberately uses **`README.txt`** for operators (`AGENTS.md`). Do not replace field docs with a long English README.md.

---

## Session / decision log (append-only)

### 2026-08 ù 1.3 ? 1.3.1 product + packaging (summary of long sessions)

- Bumped product toward 1.3 defaults (special 3000, IPS upfront off, exclude UI rename, info URL, 20260731 price masters).
- Renamed fee include flag to `include_standard_initial_fee` with checkpoint compatibility for old key.
- 1.3.1 PDF: No. column; monthly order with universal last; red discounts; no title box; sales_type subheading; TEL/FAX one line; subscription IPS 165 yen note.
- Field README / portable packaging; UTF-8 BOM for Japanese field texts.
- Encoding incident: release note source destroyed to `?`; restored + `_write_utf8_bom`.
- Privacy: real company addresses/phones and personal contacts must not be pushed; `company.json` gitignored; tests use synthetic contacts.
- Documented in this file for agent handoff (this entry).

### When you change something next

Add a short subsection:

```markdown
### YYYY-MM-DD ù short title
- What the human asked
- What you changed (files)
- Explicit ùdo not regressù decision
- Tests run (or why not)
- APP_VERSION bump? yes/no
```

---

## Release checklist (agent)

1. `APP_VERSION` in `config.py`
2. Window title / UI labels show same version
3. Tests: `cd system && python -m unittest tests.test_system -v`
4. Update / rewrite `system/docs/???????_v{version}_????.txt` as **UTF-8 BOM** Japanese
5. Keep `README.txt` short; encoding **UTF-8 BOM**
6. Append this history file + sync `AI_CONTEXT.md` version table + `AGENTS.md` current version
7. Build: `system/build_portable_exe.bat` then confirm arrange wrote BOM texts
8. Spot-check unzipped release note: must not be `?` soup
9. Do not bulk-generate full quote forest unless asked

---

## Anti-patterns seen in this project

| Bad idea | Why |
|----------|-----|
| Reopening landscape PDF layout | Explicitly rejected; portrait A4 only |
| ùANSIù convert Japanese release notes | Replaces or mojibakes; use utf-8-sig |
| Treating `portable/*.zip` as editable source | Generated tree |
| Creating ouchi+5GB for ùcompletenessù | Business rule forbids |
| Hiding exclusions when force-all is on | Exclusions must win |
| Dumping architecture into `README.txt` | Field docs must stay simple |
| Inventing new attention-note prose | Use human-approved strings |
| Amending fees by only changing renderer totals | Numbers come from `quote_service` / masters |

End of living history ù **append; do not delete past decisions** unless the human retracts them (then mark withdrawn).
