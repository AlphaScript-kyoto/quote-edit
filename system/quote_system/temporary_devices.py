# -*- coding: utf-8 -*-
"""Temporary device overlays when official price PDF is not yet available.

Remove this module / set temporary_devices.json enabled=false once the
official SoftBank price list includes the same models.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import DATA_DIR, RESOURCE_ROOT, FROZEN, load_json

TEMPORARY_DEVICES_NAME = "temporary_devices.json"
TEMPORARY_DEVICES_PATH = DATA_DIR / TEMPORARY_DEVICES_NAME


def temporary_devices_source_path() -> Path:
    """Prefer user data copy; fall back to bundled resource (EXE / repo)."""
    if TEMPORARY_DEVICES_PATH.is_file():
        return TEMPORARY_DEVICES_PATH
    bundled = RESOURCE_ROOT / "data" / TEMPORARY_DEVICES_NAME
    if bundled.is_file():
        return bundled
    return TEMPORARY_DEVICES_PATH


def load_temporary_payload() -> dict[str, Any]:
    path = temporary_devices_source_path()
    if not path.is_file():
        return {"enabled": False, "devices": []}
    try:
        payload = load_json(path)
    except (OSError, ValueError, TypeError):
        return {"enabled": False, "devices": []}
    if not isinstance(payload, dict):
        return {"enabled": False, "devices": []}
    return payload


def temporary_devices_enabled() -> bool:
    payload = load_temporary_payload()
    return bool(payload.get("enabled")) and bool(payload.get("devices"))


def temporary_model_keys() -> set[str]:
    if not temporary_devices_enabled():
        return set()
    return {
        str(device.get("model_key") or "").strip()
        for device in load_temporary_payload().get("devices", [])
        if isinstance(device, dict) and str(device.get("model_key") or "").strip()
    }


def merge_temporary_devices(device_master: dict[str, Any] | None) -> dict[str, Any]:
    """Upsert temporary devices into a device master (in-memory). Official PDF
    entries with the same model_key are replaced while the overlay is enabled,
    so field quotes keep working until the temporary file is turned off.
    """
    master = deepcopy(device_master) if isinstance(device_master, dict) else {
        "schema_version": 1,
        "devices": [],
    }
    devices = list(master.get("devices") or [])
    if not temporary_devices_enabled():
        master["devices"] = devices
        return master

    payload = load_temporary_payload()
    by_key = {
        str(device.get("model_key") or ""): index
        for index, device in enumerate(devices)
        if isinstance(device, dict) and device.get("model_key")
    }
    for raw in payload.get("devices", []):
        if not isinstance(raw, dict):
            continue
        device = deepcopy(raw)
        key = str(device.get("model_key") or "").strip()
        if not key:
            continue
        device["model_key"] = key
        device.setdefault("status", "???")
        device.setdefault("category", "iPhone")
        device.setdefault("notes", "??????PDF????")
        device.setdefault("changed", True)
        device.setdefault("payment_36", None)
        device.setdefault("payment_24", None)
        device.setdefault(
            "eligible",
            {
                "new_toku_support_plus": True,
                "replacement_support": True,
                "mobile_device_sale": True,
            },
        )
        if key in by_key:
            devices[by_key[key]] = device
        else:
            by_key[key] = len(devices)
            devices.append(device)

    master["devices"] = devices
    master["temporary_devices"] = True
    return master
