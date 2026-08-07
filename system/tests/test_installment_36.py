# -*- coding: utf-8 -*-
"""36回割賦プロトタイプ向けのユニットテスト。"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from quote_system.batch_service import quote_output_root, run_individual
from quote_system.config import DATA_DIR, UPDATE_DIR, load_json
from quote_system.installment_36 import (
    filter_36_target_devices,
    is_installment_36_target,
    load_installment_36_targets,
    parse_installment_36_pdf,
)
from quote_system.pdf_renderer import _attention_notes
from quote_system.quote_service import build_quote


class Installment36PrototypeTest(unittest.TestCase):
    def test_targets_json_matches_seed_list(self):
        rules = load_installment_36_targets()
        self.assertTrue(
            is_installment_36_target(
                model="iPhone 16e(128GB)",
                model_key="iphone16e128gb",
                category="iPhone",
                targets=rules,
            )
        )
        self.assertTrue(
            is_installment_36_target(
                model="DIGNO BX3",
                model_key="dignobx3",
                category="Android",
                targets=rules,
            )
        )
        self.assertTrue(
            is_installment_36_target(
                model="DIGNOケータイ4",
                model_key="dignoke-tai4",
                category="ケータイ",
                targets=rules,
            )
        )
        self.assertFalse(
            is_installment_36_target(
                model="iPhone 17(256GB)",
                model_key="iphone17256gb",
                category="iPhone",
                targets=rules,
            )
        )
        # 除外指定は包含指定より優先される
        self.assertFalse(
            is_installment_36_target(
                model="DIGNO BX3 Plus",
                model_key="dignobx3plus",
                category="Android",
                targets=rules,
            )
        )
        self.assertFalse(
            is_installment_36_target(
                model="DIGNOケータイ4 for Biz",
                model_key="dignoケータイ4forbiz",
                category="ケータイ",
                targets=rules,
            )
        )

    def test_output_root_split(self):
        self.assertTrue(str(quote_output_root(48)).endswith("見積PDF"))
        self.assertTrue(str(quote_output_root(36)).endswith("見積PDF_36回"))

    def test_parse_and_filter_live_pdf_if_present(self):
        folder = UPDATE_DIR / "36回割賦"
        pdfs = list(folder.glob("*.pdf"))
        if not pdfs:
            self.skipTest("no 36 PDF in update folder")
        master = parse_installment_36_pdf(pdfs[0])
        self.assertGreaterEqual(master["device_count"], 1)
        selected = filter_36_target_devices(master)
        self.assertGreaterEqual(len(selected), 1)
        names = {d["model"] for d in selected}
        # seed list should capture at least one 16e/17e/bx/feature if on the PDF
        self.assertTrue(
            any("16e" in n or "17e" in n or "BX3" in n or "ケータイ" in n for n in names)
            or any(d.get("category") == "ケータイ" for d in selected)
        )

    def test_quote_build_single_36_period(self):
        device = {
            "category": "iPhone",
            "model": "iPhone 16e(128GB)",
            "model_key": "iphone16e128gb",
            "status": "販売中",
            "installment_months": 36,
            "payment_36_flat": 3308,
            "total": 119088,
            "payment_48": {
                "MNP": {"1_12": 3308, "13_24": 3308, "25_48": 3308},
                "新規": {"1_12": 3308, "13_24": 3308, "25_48": 3308},
                "番号移行": {"1_12": 3308, "13_24": 3308, "25_48": 3308},
                "機種変更・移動機物品販売": {
                    "1_12": 3308,
                    "13_24": 3308,
                    "25_48": 3308,
                },
            },
        }
        master = {"devices": [device]}
        plans = load_json(DATA_DIR / "plans.json")
        services = load_json(DATA_DIR / "services.json")
        quote = build_quote(
            {
                "quote_id": "T-36",
                "model": device["model"],
                "sales_type": "MNP",
                "plan_id": "biz_plus",
                "data_plan": "5GB",
                "installment_months": 36,
                "payment_36_flat": 3308,
                "services": {"ips": {"type": "subscription"}, "support_plan_id": "auto"},
                "universal_fee_tax_in": 4,
                "universal_fee_tax_ex": 4,
                "tax_rate": 0.10,
            },
            master,
            plans,
            services,
        )
        self.assertEqual(quote["installment_months"], 36)
        self.assertEqual(len(quote["periods"]), 1)
        self.assertEqual(quote["periods"][0]["key"], "1_36")
        self.assertEqual(quote["periods"][0]["device_payment"], 3308)
        self.assertIn("1～36", quote["periods"][0]["label"])
        # 48回払い前提の「新トクするサポート＋」注意事項は36回では出さない
        notes_36 = _attention_notes(quote, ips=True, support=True)
        self.assertFalse(any("新トクするサポート" in note for note in notes_36))
        notes_48 = _attention_notes(
            {**quote, "installment_months": 48}, ips=True, support=True
        )
        self.assertTrue(any("新トクするサポート" in note for note in notes_48))


if __name__ == "__main__":
    unittest.main()
