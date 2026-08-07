"""36回割賦：対象リスト・PDF取込・マスター合成。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, UPDATE_DIR, load_json, save_json
from .price_pdf_parser import SALES_COLUMNS, normalize_model_name

TARGETS_PATH = DATA_DIR / "installment_36_targets.json"
DEVICE_MASTER_36_PATH = DATA_DIR / "device_master_36.json"
UPDATE_36_DIR = UPDATE_DIR / "36回割賦"

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 4,
    "snap_tolerance": 3,
    "join_tolerance": 3,
}


def update_36_dir() -> Path:
    path = UPDATE_36_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def latest_installment_36_pdf() -> Path | None:
    folder = update_36_dir()
    pdfs = list(folder.glob("*.pdf"))
    return max(pdfs, key=lambda path: path.stat().st_mtime) if pdfs else None


def load_installment_36_targets() -> dict[str, Any]:
    if not TARGETS_PATH.exists():
        return {
            "schema_version": 1,
            "match_categories": ["ケータイ"],
            "match_model_key_contains": [
                "iphone16e",
                "iphone17e",
                "aquoswish4",
                "dignobx3",
            ],
            "match_model_keys_exact": [],
            "exclude_model_keys_exact": [
                "dignobx3plus",
                "dignoケータイ4forbiz",
            ],
            "exclude_model_key_contains": [],
        }
    payload = load_json(TARGETS_PATH)
    if not isinstance(payload, dict):
        raise ValueError("installment_36_targets.json が不正です")
    return payload


def is_installment_36_target(
    *,
    model: str,
    model_key: str | None = None,
    category: str | None = None,
    targets: dict[str, Any] | None = None,
) -> bool:
    """JSON ルールで 36回作成対象か。除外指定が包含指定より優先される。"""
    rules = targets if targets is not None else load_installment_36_targets()
    key = (model_key or normalize_model_name(model)).strip()
    cat = str(category or "").strip()

    exclude_exact = {
        str(item).strip()
        for item in (rules.get("exclude_model_keys_exact") or [])
        if str(item).strip()
    }
    if key in exclude_exact:
        return False
    for part in rules.get("exclude_model_key_contains") or []:
        token = normalize_model_name(str(part))
        if token and token in key:
            return False

    exact = {
        str(item).strip()
        for item in (rules.get("match_model_keys_exact") or [])
        if str(item).strip()
    }
    if key in exact:
        return True

    for part in rules.get("match_model_key_contains") or []:
        token = normalize_model_name(str(part))
        if token and token in key:
            return True

    for allowed in rules.get("match_categories") or []:
        if cat and cat == str(allowed).strip():
            return True
    return False


def _num(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("\n", " ").strip()
    if not text or text in {"-", "－", "—", "–"}:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def parse_installment_36_pdf(pdf_path: Path) -> dict[str, Any]:
    """分割支払金一覧（36回均等）PDFを取り込む。"""
    import pdfplumber

    devices: list[dict[str, Any]] = []
    category = ""
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables(TABLE_SETTINGS)
            if not tables:
                raise ValueError(f"表を検出できませんでした: page={page_number}")
            table = max(tables, key=len)
            for row in table:
                if not row or len(row) < 7:
                    continue
                cat = str(row[1] or "").replace("\n", " ").strip()
                if cat and cat not in {"カテゴリ", "変更"}:
                    category = cat
                model = str(row[2] or "").replace("\n", " ").strip()
                if not model or model == "機種":
                    continue
                monthly = _num(row[6])
                total = _num(row[8] if len(row) > 8 else None)
                if monthly is None:
                    continue
                if total is not None and monthly * 36 != total:
                    raise ValueError(
                        f"36回検算不一致: {model} monthly={monthly} total={total}"
                    )
                devices.append(
                    {
                        "category": category,
                        "model": model,
                        "model_key": normalize_model_name(model),
                        "status": "販売中",
                        "payment_36_flat": monthly,
                        "installment_months": 36,
                        "total": total if total is not None else monthly * 36,
                        "source_page": page_number,
                    }
                )

    if not devices:
        raise ValueError(f"36回割賦の機種を読み取れませんでした: {pdf_path.name}")

    return {
        "schema_version": 1,
        "installment_months": 36,
        "source_pdf": pdf_path.name,
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": page_count,
        "device_count": len(devices),
        "devices": devices,
    }


def filter_36_target_devices(
    master_36: dict[str, Any],
    *,
    targets: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rules = targets if targets is not None else load_installment_36_targets()
    selected: list[dict[str, Any]] = []
    for raw in master_36.get("devices") or []:
        if not is_installment_36_target(
            model=str(raw.get("model") or ""),
            model_key=str(raw.get("model_key") or ""),
            category=str(raw.get("category") or ""),
            targets=rules,
        ):
            continue
        monthly = int(raw["payment_36_flat"])
        # quote_variants は payment_48 の None チェックを通すため均等値を埋め込む
        payment_48 = {
            sales: {"1_12": monthly, "13_24": monthly, "25_48": monthly}
            for sales in SALES_COLUMNS
        }
        selected.append(
            {
                **raw,
                "status": "販売中",
                "installment_months": 36,
                "payment_36_flat": monthly,
                "payment_48": payment_48,
                "payment_36": monthly,
                "payment_24": None,
                "eligible": raw.get("eligible")
                or {
                    "new_toku_support_plus": False,
                    "replacement_support": False,
                    "mobile_device_sale": False,
                },
            }
        )
    return selected


def import_installment_36_master(pdf_path: Path | None = None) -> dict[str, Any]:
    import hashlib

    path = pdf_path or latest_installment_36_pdf()
    if path is None or not path.exists():
        raise FileNotFoundError(
            "36回割賦の価格表PDFがありません。"
            f"「{UPDATE_36_DIR}」にPDFを入れてください。"
        )
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    # 同じPDFなら再解析せずキャッシュを返す（個別見積で機種ごとに呼ばれるため）
    if DEVICE_MASTER_36_PATH.exists():
        try:
            cached = load_json(DEVICE_MASTER_36_PATH)
        except Exception:
            cached = None
        if (
            isinstance(cached, dict)
            and cached.get("source_hash") == source_hash
            and cached.get("devices")
        ):
            return cached
    master = parse_installment_36_pdf(path)
    master["source_hash"] = source_hash
    save_json(DEVICE_MASTER_36_PATH, master)
    return master
