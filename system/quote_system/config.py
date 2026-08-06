from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


# アプリ表示バージョン（ウィンドウタイトル等）。仕様書もこれに合わせて更新する。
APP_VERSION = "1.3.2"
APP_DISPLAY_NAME = "見積もり一括作成"

FROZEN = bool(getattr(sys, "frozen", False))
_USER_DATA_ROOT = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
) / "InfinityQuoteApp"

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


def ensure_directories() -> None:
    for directory in (DATA_DIR, INPUT_DIR, OUTPUT_DIR, LOG_DIR, UPDATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        bundled_data = RESOURCE_ROOT / "data"
        for filename in ("plans.json", "services.json", "company.json", "device_master.json"):
            source = bundled_data / filename
            target = DATA_DIR / filename
            if source.exists() and not target.exists():
                shutil.copy2(source, target)
