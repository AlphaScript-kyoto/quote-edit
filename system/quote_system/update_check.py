"""Startup update notice for the standard (field) edition.

Reads a small latest.json from the internal share. Never blocks the UI long:
network failures / timeouts are silent. TM special edition does not use this.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR, EDITION_STANDARD, IS_TM_SPECIAL

# Field distribution folder (standard ZIP only; do not mix TM packages here).
STANDARD_SHARE_DIR = Path(
    (
        b"N:\\01."
        + bytes([0xe3, 0x83, 0x84, 0xe3, 0x83, 0xbc, 0xe3, 0x83, 0xab, 0xe3, 0x82, 0xba])
        + b"\\"
        + bytes(
            [
                0xe8, 0xa6, 0x8b, 0xe7, 0xa9, 0x8d, 0xe3, 0x82, 0x82, 0xe3, 0x82, 0x8a,
                0xe4, 0xbd, 0x9c, 0xe6, 0x88, 0x90, 0xe3, 0x83, 0x84, 0xe3, 0x83, 0xbc,
                0xe3, 0x83, 0xab,
            ]
        )
    ).decode("utf-8")
)
LATEST_JSON_NAME = "latest.json"
DEFAULT_TIMEOUT_SEC = 2.5
STATE_PATH = DATA_DIR / "update_check_state.json"


@dataclass(frozen=True)
class RemoteLatest:
    version: str
    zip_name: str
    edition: str
    notes: str
    share_dir: Path

    @property
    def zip_path(self) -> Path:
        return self.share_dir / self.zip_name


def version_tuple(version: str) -> tuple[int, ...]:
    """Numeric parts only: '1.4.10?' -> (1, 4, 10). Non-digits ignored for order."""
    parts = re.findall(r"\d+", str(version or ""))
    return tuple(int(p) for p in parts) if parts else (0,)


def is_remote_newer(remote_version: str, local_version: str = APP_VERSION) -> bool:
    """True when remote numeric version is strictly greater than local."""
    return version_tuple(remote_version) > version_tuple(local_version)


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(payload: dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def should_prompt_today(remote_version: str) -> bool:
    """Skip if the user already dismissed this remote version today."""
    state = _load_state()
    if str(state.get("dismissed_version") or "") != str(remote_version):
        return True
    return str(state.get("dismissed_on") or "") != date.today().isoformat()


def mark_dismissed(remote_version: str) -> None:
    _save_state(
        {
            "dismissed_version": str(remote_version),
            "dismissed_on": date.today().isoformat(),
        }
    )


def parse_latest_payload(
    payload: dict[str, Any],
    *,
    share_dir: Path = STANDARD_SHARE_DIR,
) -> RemoteLatest | None:
    version = str(payload.get("version") or "").strip()
    zip_name = str(payload.get("zip") or "").strip()
    if not version or not zip_name:
        return None
    edition = str(payload.get("edition") or EDITION_STANDARD).strip().lower()
    notes = str(payload.get("notes") or "").strip()
    return RemoteLatest(
        version=version,
        zip_name=zip_name,
        edition=edition or EDITION_STANDARD,
        notes=notes,
        share_dir=share_dir,
    )


def _read_latest_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError, UnicodeError):
        return None
    return payload if isinstance(payload, dict) else None


def fetch_remote_latest(
    *,
    share_dir: Path = STANDARD_SHARE_DIR,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> RemoteLatest | None:
    """Read latest.json with a hard timeout. Returns None on any failure."""
    if IS_TM_SPECIAL:
        return None

    path = share_dir / LATEST_JSON_NAME
    box: dict[str, Any] = {"result": None}

    def worker() -> None:
        box["result"] = _read_latest_json(path)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=max(0.5, float(timeout_sec)))
    if thread.is_alive():
        return None
    payload = box.get("result")
    if not isinstance(payload, dict):
        return None
    remote = parse_latest_payload(payload, share_dir=share_dir)
    if remote is None:
        return None
    # Standard app must ignore TM announcements if mixed by mistake.
    if remote.edition != EDITION_STANDARD:
        return None
    return remote


def check_for_update(
    *,
    local_version: str = APP_VERSION,
    share_dir: Path = STANDARD_SHARE_DIR,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> RemoteLatest | None:
    """Return remote info when a newer standard package is available and not snoozed."""
    remote = fetch_remote_latest(share_dir=share_dir, timeout_sec=timeout_sec)
    if remote is None:
        return None
    if not is_remote_newer(remote.version, local_version):
        return None
    if not should_prompt_today(remote.version):
        return None
    return remote


def open_update_location(remote: RemoteLatest) -> None:
    """Open Explorer on the ZIP if present, otherwise the share folder."""
    target = remote.zip_path if remote.zip_path.is_file() else remote.share_dir
    try:
        if target.is_file():
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            os.startfile(str(remote.share_dir))  # type: ignore[attr-defined]
    except OSError:
        try:
            os.startfile(str(remote.share_dir))  # type: ignore[attr-defined]
        except OSError:
            pass
