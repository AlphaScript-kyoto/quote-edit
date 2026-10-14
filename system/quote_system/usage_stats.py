from __future__ import annotations

import csv
import ctypes
import getpass
import json
import os
import re
import socket
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import APP_EDITION, APP_VERSION, LOG_DIR


USAGE_SHARE_ROOT = Path(
    "N:\\01.\u30c4\u30fc\u30eb\u30ba\\"
    "\u898b\u7a4d\u3082\u308a\u4f5c\u6210\u30c4\u30fc\u30eb\\"
    "\u958b\u767a\u8005\u30c4\u30fc\u30eb\\"
    "\u4f5c\u6210\u30c7\u30fc\u30bf\u96c6\u8a08"
)
PENDING_DIR = LOG_DIR / "usage_pending"
LEGACY_CSV_HEADER = [
    "\u30a4\u30d9\u30f3\u30c8ID",
    "\u4f5c\u6210\u65e5\u6642",
    "Windows\u30e6\u30fc\u30b6\u30fc\u540d",
    "PC\u540d",
    "\u90e8\u7f72",
    "\u30a8\u30c7\u30a3\u30b7\u30e7\u30f3",
    "\u4f5c\u6210\u65b9\u5f0f",
    "\u5272\u8ce6\u56de\u6570",
    "\u4f5c\u6210PDF\u6570",
    "\u5bfe\u8c61\u6a5f\u7a2e\u6570",
    "\u7d50\u679c",
    "\u30a2\u30d7\u30ea\u30d0\u30fc\u30b8\u30e7\u30f3",
]
CSV_HEADER = [
    *LEGACY_CSV_HEADER[:3],
    "Windows\u8868\u793a\u540d",
    *LEGACY_CSV_HEADER[3:],
]
_sync_lock = threading.Lock()


def _windows_user_name() -> str:
    user = str(os.environ.get("USERNAME") or getpass.getuser() or "").strip()
    domain = str(os.environ.get("USERDOMAIN") or "").strip()
    if domain and user and domain.casefold() != socket.gethostname().casefold():
        return f"{domain}\\{user}"
    return user


def _windows_display_name(*, fallback: str = "") -> str:
    """Read the Windows account display name without requiring elevation."""
    if os.name != "nt":
        return fallback
    try:
        get_user_name_ex = ctypes.windll.secur32.GetUserNameExW
        size = ctypes.c_ulong(256)
        buffer = ctypes.create_unicode_buffer(size.value)
        if get_user_name_ex(3, buffer, ctypes.byref(size)):
            return buffer.value.strip() or fallback
        if size.value > len(buffer):
            buffer = ctypes.create_unicode_buffer(size.value)
            if get_user_name_ex(3, buffer, ctypes.byref(size)):
                return buffer.value.strip() or fallback
    except (AttributeError, OSError, ValueError):
        pass
    return fallback


def _computer_name() -> str:
    return str(os.environ.get("COMPUTERNAME") or socket.gethostname() or "unknown").strip()


def _safe_csv_value(value: Any) -> str:
    text = str(value if value is not None else "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    return cleaned or "unknown"


def _event_row(event: dict[str, Any]) -> list[str]:
    return [
        _safe_csv_value(event.get(key, ""))
        for key in (
            "event_id",
            "created_at",
            "windows_user",
            "windows_display_name",
            "computer_name",
            "department",
            "edition",
            "creation_type",
            "installment_months",
            "generated_files",
            "target_models",
            "result",
            "app_version",
        )
    ]


def _existing_event_ids(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.reader(handle)
        next(rows, None)
        return {row[0] for row in rows if row}


def _upgrade_legacy_csv(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] == CSV_HEADER:
        return
    if rows[0] != LEGACY_CSV_HEADER:
        raise ValueError(f"Unknown usage CSV schema: {csv_path}")
    temp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in rows[1:]:
            legacy = dict(zip(LEGACY_CSV_HEADER, row))
            writer.writerow([
                legacy.get(column, "") if column != "Windows\u8868\u793a\u540d" else ""
                for column in CSV_HEADER
            ])
    temp.replace(csv_path)


def _append_to_share(event: dict[str, Any], share_root: Path) -> None:
    month = str(event["created_at"])[:7]
    month_dir = share_root / month
    month_dir.mkdir(parents=True, exist_ok=True)
    csv_path = month_dir / f"{_safe_filename(str(event['computer_name']))}_{month}.csv"
    _upgrade_legacy_csv(csv_path)
    if str(event["event_id"]) in _existing_event_ids(csv_path):
        return
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if needs_header:
            writer.writerow(CSV_HEADER)
        writer.writerow(_event_row(event))


def sync_pending_usage(*, share_root: Path = USAGE_SHARE_ROOT) -> None:
    """Send pending usage events to the share, retaining files when it fails."""
    if not _sync_lock.acquire(blocking=False):
        return
    try:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        for pending in sorted(PENDING_DIR.glob("*.json")):
            try:
                event = json.loads(pending.read_text(encoding="utf-8"))
                _append_to_share(event, share_root)
                pending.unlink()
            except (OSError, ValueError, TypeError, KeyError, csv.Error):
                continue
    finally:
        _sync_lock.release()


def start_usage_sync() -> None:
    """Retry pending events in the background so the UI never waits on N:."""
    threading.Thread(target=sync_pending_usage, daemon=True).start()


def record_usage(
    *,
    creation_type: str,
    installment_months: int,
    generated_files: int,
    department: str,
    target_models: int = 0,
    result: str = "\u5b8c\u4e86",
) -> None:
    """Persist an event locally first, then start asynchronous share sync."""
    now = datetime.now()
    windows_user = _windows_user_name()
    event = {
        "event_id": uuid.uuid4().hex,
        "created_at": now.isoformat(timespec="seconds"),
        "windows_user": windows_user,
        "windows_display_name": _windows_display_name(fallback=windows_user),
        "computer_name": _computer_name(),
        "department": str(department or "").strip(),
        "edition": APP_EDITION,
        "creation_type": str(creation_type),
        "installment_months": int(installment_months),
        "generated_files": max(0, int(generated_files)),
        "target_models": max(0, int(target_models)),
        "result": str(result),
        "app_version": APP_VERSION,
    }
    try:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        pending = PENDING_DIR / f"{event['event_id']}.json"
        temp = pending.with_suffix(".tmp")
        temp.write_text(
            json.dumps(event, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(pending)
    except OSError:
        # Statistics must never prevent quote generation.
        return
    start_usage_sync()
