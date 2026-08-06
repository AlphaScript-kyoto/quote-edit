"""Arrange PyInstaller output into the field-facing portable folder."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parent
if str(SYSTEM_DIR) not in sys.path:
    sys.path.insert(0, str(SYSTEM_DIR))

from quote_system.config import APP_DISPLAY_NAME, APP_VERSION

ROOT = SYSTEM_DIR.parent
DIST = ROOT / "portable"
BUILD_NAME = "QuoteBatchApp"
APP_NAME = APP_DISPLAY_NAME
# 配布フォルダ名例: 見積もり一括作成ver1.3.1
PACKAGE_DIR_NAME = f"{APP_NAME}ver{APP_VERSION}"
UPDATE_NAME = "機種代金一覧表"

BUILD_DIR = DIST / "build" / BUILD_NAME
STAGE = DIST / PACKAGE_DIR_NAME


def _write_utf8_bom(src: Path, dest: Path) -> None:
    """Copy text for field use as UTF-8 with BOM (Windows Notepad-safe)."""
    text = src.read_text(encoding="utf-8-sig")
    dest.write_text(text, encoding="utf-8-sig", newline="\r\n")


def main() -> int:
    if not BUILD_DIR.exists():
        print(f"Build output not found: {BUILD_DIR}", file=sys.stderr)
        return 1

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # PyInstaller with --contents-directory system produces:
    #   BUILD_DIR/QuoteBatchApp.exe
    #   BUILD_DIR/system/...
    exe_src = BUILD_DIR / f"{BUILD_NAME}.exe"
    if not exe_src.exists():
        print(f"EXE not found: {exe_src}", file=sys.stderr)
        return 1

    shutil.move(str(exe_src), str(STAGE / f"{APP_NAME}.exe"))
    system_src = BUILD_DIR / "system"
    if system_src.exists():
        shutil.move(str(system_src), str(STAGE / "system"))
    else:
        # Fallback: move remaining internals into system/
        system_dst = STAGE / "system"
        system_dst.mkdir(parents=True, exist_ok=True)
        for child in BUILD_DIR.iterdir():
            shutil.move(str(child), str(system_dst / child.name))

    (STAGE / UPDATE_NAME).mkdir(exist_ok=True)
    (STAGE / "output").mkdir(exist_ok=True)

    # 現場配布用：開発側 機種代金一覧表 にある価格表PDFを同梱する
    source_update = ROOT / UPDATE_NAME
    if source_update.is_dir():
        pdfs = sorted(source_update.glob("*.pdf"))
        for pdf in pdfs:
            shutil.copy2(pdf, STAGE / UPDATE_NAME / pdf.name)
        if pdfs:
            print(f"Bundled {len(pdfs)} price PDF(s) into {UPDATE_NAME}/")
        else:
            print(f"WARNING: no PDF found in {source_update}", file=sys.stderr)
    else:
        print(f"WARNING: {source_update} not found; price PDF not bundled", file=sys.stderr)

    readme = ROOT / "README.txt"
    if readme.exists():
        # UTF-8 BOM so Japanese Windows Notepad does not misread as CP932/ANSI.
        _write_utf8_bom(readme, STAGE / "README.txt")
    else:
        print("WARNING: README.txt not found at project root", file=sys.stderr)

    # 任意：現場向けリリースメモがあれば同梱
    release_note = SYSTEM_DIR / "docs" / f"リリースノート_v{APP_VERSION}_現場向け.txt"
    if release_note.exists():
        _write_utf8_bom(release_note, STAGE / release_note.name)

    shutil.rmtree(DIST / "build", ignore_errors=True)
    print(f"Portable app ready: {STAGE}")
    print("Contents: EXE / README.txt / 機種代金一覧表 / output / system")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
