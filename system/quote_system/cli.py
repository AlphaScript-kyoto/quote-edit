from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .config import (
    DATA_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    ensure_directories,
    load_json,
    save_json,
)
from .pdf_renderer import render_quote
from .price_pdf_parser import parse_price_pdf
from .quote_service import build_quote


def import_price(pdf_path: Path, output_path: Path) -> None:
    master = parse_price_pdf(pdf_path)
    save_json(output_path, master)
    print(
        f"価格表を取り込みました: {master['device_count']}機種 / "
        f"変更{master['changed_count']}件 / 取扱終了{master['discontinued_count']}件"
    )
    print(output_path)


def generate_quote(request_path: Path, output_path: Path | None) -> Path:
    request = load_json(request_path)
    device_master = load_json(DATA_DIR / "device_master.json")
    plan_master = load_json(DATA_DIR / "plans.json")
    service_master = load_json(DATA_DIR / "services.json")
    company = load_json(DATA_DIR / "company.json")
    quote = build_quote(request, device_master, plan_master, service_master)
    if output_path is None:
        safe_model = quote["model"].replace("/", "_").replace(" ", "_")
        output_path = OUTPUT_DIR / f"{quote['quote_id']}_{safe_model}.pdf"
    render_quote(quote, company, output_path)

    audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "request_file": str(request_path),
        "output_file": str(output_path),
        "quote": quote,
    }
    save_json(LOG_DIR / f"{quote['quote_id']}.json", audit)
    print(f"見積PDFを出力しました: {output_path}")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ローカル見積作成システム")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-price", help="機種価格表PDFを取り込む")
    import_parser.add_argument("--pdf", type=Path, required=True)
    import_parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "device_master.json",
    )

    generate_parser = subparsers.add_parser("generate", help="見積PDFを作成する")
    generate_parser.add_argument("--request", type=Path, required=True)
    generate_parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    ensure_directories()
    args = build_parser().parse_args()
    if args.command == "import-price":
        import_price(args.pdf, args.output)
    elif args.command == "generate":
        generate_quote(args.request, args.output)
