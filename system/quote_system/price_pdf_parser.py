from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber


SALES_COLUMNS = {
    "MNP": 7,
    "新規": 10,
    "番号移行": 13,
    "機種変更・移動機物品販売": 16,
}

# マスター／PDF 列の正式名はそのまま。出力フォルダ・見積PDFの見出しだけ短くする。
_SALES_TYPE_DISPLAY = {
    "機種変更・移動機物品販売": "機種変更",
}


def sales_type_display_name(sales_type: str) -> str:
    """販売区分の表示名（フォルダ名・PDF表題用）。データ照合キーは変更しない。"""
    key = str(sales_type or "").strip()
    return _SALES_TYPE_DISPLAY.get(key, key)


def normalize_model_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[\s()（）・_-]+", "", normalized)


def _numbers_from_cells(row: list[Any], start: int, count: int = 3) -> list[int | None]:
    text = " ".join(str(row[index] or "") for index in range(start, min(start + count, len(row))))
    tokens = re.findall(r"-|\d[\d,]*", text)
    values: list[int | None] = []
    for token in tokens[:count]:
        values.append(None if token == "-" else int(token.replace(",", "")))
    while len(values) < count:
        values.append(None)
    return values


def _single_number(value: Any) -> int | None:
    match = re.search(r"\d[\d,]*", str(value or ""))
    return int(match.group(0).replace(",", "")) if match else None


def _is_changed(value: Any) -> bool:
    return "変更" in str(value or "")


def _validate_total(payments: list[int | None], total: int | None) -> bool | None:
    if total is None or any(value is None for value in payments):
        return None
    calculated = payments[0] * 12 + payments[1] * 12 + payments[2] * 24
    return calculated == total


def parse_price_pdf(pdf_path: Path) -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    current_category = ""

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables(
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 4,
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
            )
            if not tables:
                raise ValueError(f"表を検出できませんでした: page={page_number}")

            table = max(tables, key=len)
            for row in table:
                if len(row) < 23:
                    continue
                category = str(row[1] or "").replace("\n", " ").strip()
                if category and category != "カテゴリ":
                    current_category = category

                model = str(row[2] or "").replace("\n", " ").strip()
                if not model or model == "機種":
                    continue

                route_payments = {
                    sales_type: _numbers_from_cells(row, start)
                    for sales_type, start in SALES_COLUMNS.items()
                }
                route_text = " ".join(str(row[index] or "") for index in range(7, 19))
                route_dash_count = route_text.count("-")
                has_any_48_payment = any(
                    any(value is not None for value in payments)
                    for payments in route_payments.values()
                )
                payment_36 = _single_number(row[19])
                payment_24 = _single_number(row[20])
                # 4つの販売区分に「-」が連続する行は取扱終了。
                # 48回欄が空欄で36回・24回のみ設定された端末とは区別します。
                status = (
                    "取扱終了"
                    if not has_any_48_payment and route_dash_count >= 4
                    else "販売中"
                )
                total = _single_number(row[22])
                validations = {
                    sales_type: _validate_total(payments, total)
                    for sales_type, payments in route_payments.items()
                }

                devices.append(
                    {
                        "category": current_category,
                        "model": model,
                        "model_key": normalize_model_name(model),
                        "changed": _is_changed(row[0]),
                        "status": status,
                        "notes": str(row[3] or "").replace("\n", " ").strip(),
                        "eligible": {
                            "new_toku_support_plus": "●" in str(row[4] or ""),
                            "replacement_support": "●" in str(row[5] or ""),
                            "mobile_device_sale": "●" in str(row[6] or ""),
                        },
                        "payment_48": {
                            sales_type: {
                                "1_12": payments[0],
                                "13_24": payments[1],
                                "25_48": payments[2],
                            }
                            for sales_type, payments in route_payments.items()
                        },
                        "payment_36": payment_36,
                        "payment_24": payment_24,
                        "total": total,
                        "validation": validations,
                        "source_page": page_number,
                    }
                )

    invalid = [
        {"model": device["model"], "sales_type": sales_type}
        for device in devices
        for sales_type, result in device["validation"].items()
        if result is False
    ]
    if invalid:
        raise ValueError(f"支払総額との検算不一致があります: {invalid[:10]}")

    return {
        "schema_version": 1,
        "source_pdf": pdf_path.name,
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": page_count,
        "device_count": len(devices),
        "changed_count": sum(1 for device in devices if device["changed"]),
        "discontinued_count": sum(1 for device in devices if device["status"] == "取扱終了"),
        "devices": devices,
    }


def find_device(master: dict[str, Any], model_name: str) -> dict[str, Any]:
    key = normalize_model_name(model_name)
    matches = [device for device in master["devices"] if device["model_key"] == key]
    if not matches:
        raise KeyError(f"機種マスターにありません: {model_name}")
    if len(matches) > 1:
        raise KeyError(f"機種名が重複しています: {model_name}")
    return matches[0]
