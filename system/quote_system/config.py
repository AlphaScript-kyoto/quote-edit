from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


# アプリ表示バージョン（ウィンドウタイトル等）。仕様書もこれに合わせて更新する。
APP_VERSION = "1.4.13β"
APP_DISPLAY_NAME = "見積もり一括作成"

# パッケージ版: standard（現場向け） / tm_special（TM兼任事業部用・個別制限解除）
EDITION_STANDARD = "standard"
EDITION_TM_SPECIAL = "tm_special"
_VALID_EDITIONS = frozenset({EDITION_STANDARD, EDITION_TM_SPECIAL})


def _resolve_app_edition() -> str:
    """Edition comes from env or bundled marker — not from LOCALAPPDATA user data."""
    env = str(os.environ.get("QUOTE_APP_EDITION") or "").strip().lower()
    if env in _VALID_EDITIONS:
        return env
    candidates: list[Path] = []
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "data" / "app_edition.json")
        exe_parent = Path(sys.executable).resolve().parent
        candidates.append(exe_parent / "system" / "data" / "app_edition.json")
    else:
        candidates.append(Path(__file__).resolve().parents[1] / "data" / "app_edition.json")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        edition = str(payload.get("edition") or "").strip().lower()
        if edition in _VALID_EDITIONS:
            return edition
    return EDITION_STANDARD


APP_EDITION = _resolve_app_edition()
IS_TM_SPECIAL = APP_EDITION == EDITION_TM_SPECIAL

FROZEN = bool(getattr(sys, "frozen", False))
_USER_DATA_ROOT = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
) / ("InfinityQuoteAppTM" if IS_TM_SPECIAL else "InfinityQuoteApp")

if FROZEN:
    APP_ROOT = Path(sys.executable).resolve().parent
    SYSTEM_DIR = APP_ROOT / "system"
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SYSTEM_DIR))
    DATA_DIR = _USER_DATA_ROOT / "data"
    LOG_DIR = _USER_DATA_ROOT / "logs"
    INPUT_DIR = _USER_DATA_ROOT / "input"
else:
    SYSTEM_DIR = Path(__file__).resolve().parents[1]
    APP_ROOT = SYSTEM_DIR.parent
    RESOURCE_ROOT = SYSTEM_DIR
    DATA_DIR = SYSTEM_DIR / "data"
    LOG_DIR = SYSTEM_DIR / "logs"
    INPUT_DIR = SYSTEM_DIR / "input"

OUTPUT_DIR = APP_ROOT / "output"
UPDATE_DIR = APP_ROOT / "機種代金一覧表"

# TM特例パッケージは出力も分離（通常版の見積PDFと混線しない）
QUOTE_OUTPUT_DIRNAME = "見積PDF_TM特例" if IS_TM_SPECIAL else "見積PDF"
QUOTE_OUTPUT_DIRNAME_36 = "見積PDF_TM特例_36回" if IS_TM_SPECIAL else "見積PDF_36回"
QUOTE_OUTPUT_DIRNAME_24 = "見積PDF_TM特例_24回" if IS_TM_SPECIAL else "見積PDF_24回"


def app_window_title() -> str:
    if IS_TM_SPECIAL:
        return f"{APP_DISPLAY_NAME}（TM兼任事業部用）  ver.{APP_VERSION}"
    return f"{APP_DISPLAY_NAME}  ver.{APP_VERSION}"


def package_dir_name() -> str:
    if IS_TM_SPECIAL:
        return f"{APP_DISPLAY_NAME}_TM兼任事業部用ver{APP_VERSION}"
    return f"{APP_DISPLAY_NAME}ver{APP_VERSION}"

# 旧コード互換
PROJECT_ROOT = APP_ROOT


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def merge_missing_company_fields(
    local: dict[str, Any],
    bundled: dict[str, Any],
) -> bool:
    """ローカル company の空の TEL/FAX/住所を同梱マスタで埋める。変更があれば True。

    EXE 初回コピー後に FAX が空のまま残ると、開発環境（system/data）と
    現場（%LOCALAPPDATA%）で見積表記が食い違うため、空欄のみ同梱側で補完する。
    既に値が入っている項目は上書きしない。
    """
    changed = False
    for key in ("phone", "fax", "postal_address"):
        bundled_value = str(bundled.get(key) or "").strip()
        local_value = str(local.get(key) or "").strip()
        if bundled_value and not local_value:
            local[key] = bundled[key]
            changed = True

    bundled_contacts = bundled.get("department_contacts")
    if not isinstance(bundled_contacts, dict):
        return changed
    local_contacts = local.get("department_contacts")
    if not isinstance(local_contacts, dict):
        local_contacts = {}
        local["department_contacts"] = local_contacts
        changed = True

    for dept, bundled_entry in bundled_contacts.items():
        if not isinstance(bundled_entry, dict):
            continue
        local_entry = local_contacts.get(dept)
        if not isinstance(local_entry, dict):
            local_entry = {}
            local_contacts[dept] = local_entry
            changed = True
        for field in ("phone", "fax", "postal_address", "address"):
            bundled_value = str(bundled_entry.get(field) or "").strip()
            local_value = str(local_entry.get(field) or "").strip()
            if bundled_value and not local_value:
                local_entry[field] = bundled_entry[field]
                changed = True
    return changed


def ensure_directories() -> None:
    for directory in (DATA_DIR, INPUT_DIR, OUTPUT_DIR, LOG_DIR, UPDATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        bundled_data = RESOURCE_ROOT / "data"
        for filename in (
            "plans.json",
            "services.json",
            "company.json",
            "device_master.json",
            "temporary_devices.json",
            "installment_36_targets.json",
        ):
            source = bundled_data / filename
            target = DATA_DIR / filename
            if source.exists() and not target.exists():
                shutil.copy2(source, target)
            # company: 現場に残った空の FAX 等を同梱マスタで補完（開発と表記差が出る対策）
            if filename == "company.json" and source.exists() and target.exists():
                try:
                    local = load_json(target)
                    bundled = load_json(source)
                    if isinstance(local, dict) and isinstance(bundled, dict):
                        if merge_missing_company_fields(local, bundled):
                            save_json(target, local)
                except (OSError, json.JSONDecodeError, TypeError):
                    pass
    (UPDATE_DIR / "36回割賦").mkdir(parents=True, exist_ok=True)

