"""Fail portable build if company.json lacks department FAX/TEL for field PDFs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "company.json"
# 現場で「FAXが出ない」になりやすい部署。番号そのものはログに出さない。
_CRITICAL_DEPTS = ("RT事業部", "CRM事業部", "AQ事業部")


def main() -> int:
    if not DATA.exists():
        print(f"ERROR: missing {DATA}", file=sys.stderr)
        print("Copy company.example.json -> company.json and fill contacts.", file=sys.stderr)
        return 1
    try:
        company = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read company.json: {exc}", file=sys.stderr)
        return 1

    contacts = company.get("department_contacts")
    if not isinstance(contacts, dict) or not contacts:
        print("ERROR: company.json に department_contacts がありません。", file=sys.stderr)
        return 1

    problems: list[str] = []
    for dept in _CRITICAL_DEPTS:
        entry = contacts.get(dept)
        if not isinstance(entry, dict):
            problems.append(f"{dept}: エントリなし")
            continue
        phone = str(entry.get("phone") or "").strip()
        fax = str(entry.get("fax") or "").strip()
        if not phone:
            problems.append(f"{dept}: phone が空")
        if not fax:
            problems.append(f"{dept}: fax が空（PDFで FAX 行が消えます）")

    if problems:
        print("ERROR: 現場向け ZIP に同梱する company.json の連絡先が不足しています。", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        print(
            "※ TEL/FAX は Git にコミットせず、ビルド PC の system/data/company.json のみに置いてください。",
            file=sys.stderr,
        )
        return 1

    print("company.json OK: critical department phone/fax present (values not printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
