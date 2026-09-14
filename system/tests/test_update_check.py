"""Tests for standard-edition startup update check."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quote_system import update_check as uc


class UpdateCheckTest(unittest.TestCase):
    def test_version_tuple_strips_beta(self):
        self.assertEqual(uc.version_tuple("1.4.10?"), (1, 4, 10))
        self.assertEqual(uc.version_tuple("1.4.8"), (1, 4, 8))

    def test_is_remote_newer(self):
        self.assertTrue(uc.is_remote_newer("1.4.10?", "1.4.8"))
        self.assertFalse(uc.is_remote_newer("1.4.10?", "1.4.10"))
        self.assertFalse(uc.is_remote_newer("1.4.8", "1.4.10?"))
        self.assertFalse(uc.is_remote_newer("1.4.10?", "1.4.10?"))

    def test_parse_rejects_tm_edition_for_standard_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            share = Path(tmp)
            payload = {
                "version": "1.4.11?",
                "zip": "????????ver1.4.11?.zip",
                "edition": "tm_special",
            }
            (share / "latest.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            with patch.object(uc, "IS_TM_SPECIAL", False):
                self.assertIsNone(uc.fetch_remote_latest(share_dir=share, timeout_sec=1.0))

    def test_check_for_update_finds_newer_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            share = Path(tmp)
            state = Path(tmp) / "state.json"
            payload = {
                "version": "1.4.10?",
                "zip": "????????ver1.4.10?.zip",
                "edition": "standard",
                "notes": "test",
            }
            (share / "latest.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            with (
                patch.object(uc, "IS_TM_SPECIAL", False),
                patch.object(uc, "STATE_PATH", state),
            ):
                remote = uc.check_for_update(
                    local_version="1.4.8",
                    share_dir=share,
                    timeout_sec=1.0,
                )
                self.assertIsNotNone(remote)
                assert remote is not None
                self.assertEqual(remote.version, "1.4.10?")
                self.assertEqual(remote.zip_name, payload["zip"])

                uc.mark_dismissed(remote.version)
                again = uc.check_for_update(
                    local_version="1.4.8",
                    share_dir=share,
                    timeout_sec=1.0,
                )
                self.assertIsNone(again)

    def test_tm_special_skips_check(self):
        with patch.object(uc, "IS_TM_SPECIAL", True):
            self.assertIsNone(uc.fetch_remote_latest(timeout_sec=0.5))


if __name__ == "__main__":
    unittest.main()
