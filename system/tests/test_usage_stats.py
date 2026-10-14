import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from quote_system import usage_stats


class UsageStatsTest(unittest.TestCase):
    def test_record_and_sync_to_monthly_computer_csv(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pending = root / "pending"
            share = root / "share"
            with (
                patch.object(usage_stats, "PENDING_DIR", pending),
                patch.object(usage_stats, "start_usage_sync"),
                patch.object(usage_stats, "_windows_user_name", return_value="DOMAIN\\user"),
                patch.object(
                    usage_stats,
                    "_windows_display_name",
                    return_value="\u4f50\u85e4 \u4eae\u592a",
                ),
                patch.object(usage_stats, "_computer_name", return_value="PC-001"),
            ):
                usage_stats.record_usage(
                    creation_type="\u500b\u5225",
                    installment_months=36,
                    generated_files=12,
                    department="RT\u4e8b\u696d\u90e8",
                    target_models=2,
                )
                self.assertEqual(len(list(pending.glob("*.json"))), 1)
                usage_stats.sync_pending_usage(share_root=share)

            csv_files = list(share.rglob("*.csv"))
            self.assertEqual(len(csv_files), 1)
            self.assertTrue(csv_files[0].read_bytes().startswith(b"\xef\xbb\xbf"))
            with csv_files[0].open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Windows\u30e6\u30fc\u30b6\u30fc\u540d"], "DOMAIN\\user")
            self.assertEqual(rows[0]["Windows\u8868\u793a\u540d"], "\u4f50\u85e4 \u4eae\u592a")
            self.assertEqual(rows[0]["\u4f5c\u6210PDF\u6570"], "12")
            self.assertEqual(rows[0]["\u5272\u8ce6\u56de\u6570"], "36")
            self.assertFalse(list(pending.glob("*.json")))

            duplicate = {
                "event_id": rows[0]["\u30a4\u30d9\u30f3\u30c8ID"],
                "created_at": rows[0]["\u4f5c\u6210\u65e5\u6642"],
                "computer_name": "PC-001",
            }
            pending.mkdir(exist_ok=True)
            (pending / "duplicate.json").write_text(
                json.dumps(duplicate),
                encoding="utf-8",
            )
            with patch.object(usage_stats, "PENDING_DIR", pending):
                usage_stats.sync_pending_usage(share_root=share)
            with csv_files[0].open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)

    def test_legacy_csv_is_upgraded_with_display_name_column(self):
        with TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "legacy.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(usage_stats.LEGACY_CSV_HEADER)
                writer.writerow([
                    "old-event",
                    "2026-10-14T13:49:00",
                    "DOMAIN\\old-user",
                    "PC-001",
                    "RT",
                    "standard",
                    "\u4e00\u62ec",
                    "48",
                    "10",
                    "1",
                    "\u5b8c\u4e86",
                    "1.7.4",
                ])
            usage_stats._upgrade_legacy_csv(csv_path)
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["Windows\u8868\u793a\u540d"], "")
            self.assertEqual(rows[0]["Windows\u30e6\u30fc\u30b6\u30fc\u540d"], "DOMAIN\\old-user")

    def test_failed_share_keeps_pending_event_for_retry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pending = root / "pending"
            pending.mkdir()
            event = {
                "event_id": "event-1",
                "created_at": "2026-10-14T13:49:00",
                "computer_name": "PC-001",
            }
            (pending / "event-1.json").write_text(
                json.dumps(event),
                encoding="utf-8",
            )
            blocked_share = root / "not-a-directory"
            blocked_share.write_text("blocked", encoding="utf-8")
            with patch.object(usage_stats, "PENDING_DIR", pending):
                usage_stats.sync_pending_usage(share_root=blocked_share)
            self.assertTrue((pending / "event-1.json").exists())


if __name__ == "__main__":
    unittest.main()
