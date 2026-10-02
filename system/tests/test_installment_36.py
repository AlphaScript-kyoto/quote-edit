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
from quote_system.pdf_renderer import _attention_notes, _device_payment_label
from quote_system.price_pdf_parser import SALES_COLUMNS
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
                model="iPhone 16 Pro(128GB)",
                model_key="iphone16pro128gb",
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
        self.assertTrue(str(quote_output_root(24)).endswith("見積PDF_24回"))

    def test_quote_build_single_24_period(self):
        device = {
            "category": "iPhone",
            "model": "iPhone 15(256GB)",
            "model_key": "iphone15256gb",
            "status": "販売中",
            "payment_24": 5694,
            "total": 136656,
            "payment_48": {
                "MNP": {"1_12": None, "13_24": None, "25_48": None},
                "新規": {"1_12": None, "13_24": None, "25_48": None},
                "番号移行": {"1_12": None, "13_24": None, "25_48": None},
                "機種変更・移動機物品販売": {
                    "1_12": None,
                    "13_24": None,
                    "25_48": None,
                },
            },
            "eligible": {
                "new_toku_support_plus": False,
                "replacement_support": False,
                "mobile_device_sale": True,
            },
        }
        master = {"devices": [device]}
        plans = load_json(DATA_DIR / "plans.json")
        services = load_json(DATA_DIR / "services.json")
        quote = build_quote(
            {
                "quote_id": "T-24",
                "quote_date": "2026-09-14",
                "customer_name": "御中",
                "model": device["model"],
                "sales_type": "機種変更・移動機物品販売",
                "plan_id": "biz_plus",
                "data_plan": "5GB",
                "initial_fee_mode": "special_3000",
                "installment_months": 24,
                "payment_24": 5694,
                "services": {
                    "ips": {"type": "subscription"},
                    "support_plan_id": "auto",
                },
                "universal_fee_tax_in": 4,
                "universal_fee_tax_ex": 4,
                "ouchi_discount_applied": False,
                "tax_rate": 0.10,
            },
            master,
            plans,
            services,
        )
        self.assertEqual(quote["installment_months"], 24)
        self.assertEqual(len(quote["periods"]), 1)
        self.assertEqual(quote["periods"][0]["key"], "1_24")
        self.assertEqual(quote["periods"][0]["device_payment"], 5694)
        self.assertIn("1～24", quote["periods"][0]["label"])
        self.assertEqual(_device_payment_label(quote), "機種代金（24分割）")
        notes_24 = _attention_notes(quote, ips=True, support=True)
        self.assertFalse(any("新トクするサポート" in note for note in notes_24))

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
        self.assertEqual(_device_payment_label(quote), "機種代金（36分割）")
        self.assertEqual(
            _device_payment_label({**quote, "installment_months": 48}),
            "機種代金（48分割）",
        )
        # 48回払い前提の「新トクするサポート＋」注意事項は36回では出さない
        notes_36 = _attention_notes(quote, ips=True, support=True)
        self.assertFalse(any("新トクするサポート" in note for note in notes_36))
        notes_48 = _attention_notes(
            {**quote, "installment_months": 48}, ips=True, support=True
        )
        self.assertTrue(any("新トクするサポート" in note for note in notes_48))

    def test_36_super_hyper_follow_48_rules(self):
        """36回でもスーパー／ハイパーは48回と同じルールで作成できる。"""
        from quote_system.batch_service import quote_variants

        master_36 = {
            "devices": [
                {"category": "iPhone", "model": "iPhone 16e(128GB)",
                 "model_key": "iphone16e128gb", "payment_36_flat": 3308,
                 "total": 3308 * 36},
                {"category": "ケータイ", "model": "DIGNOケータイ4",
                 "model_key": "dignoke-tai4", "payment_36_flat": 1500,
                 "total": 1500 * 36},
            ]
        }
        devices = {d["model"]: d for d in filter_36_target_devices(master_36)}
        plans = load_json(DATA_DIR / "plans.json")
        services = load_json(DATA_DIR / "services.json")

        iphone_variants = list(
            quote_variants(devices["iPhone 16e(128GB)"], plans, include_mnp_shinki_irs=True)
        )
        by_plan_sales = {(v["plan_id"], v["sales_type"]) for v in iphone_variants}
        for plan_id in ("super_light", "hyper_light"):
            for sales in ("機種変更・移動機物品販売", "MNP", "新規"):
                self.assertIn((plan_id, sales), by_plan_sales)
            self.assertNotIn((plan_id, "番号移行"), by_plan_sales)
        feature_variants = list(
            quote_variants(devices["DIGNOケータイ4"], plans, include_mnp_shinki_irs=True)
        )
        self.assertFalse(
            any(v["plan_id"] in {"super_light", "hyper_light"} for v in feature_variants)
        )

        master = {"devices": list(devices.values())}
        for plan_id, sales, capacity in (
            ("super_light", "機種変更・移動機物品販売", "50GB"),
            ("super_light", "MNP", "5GB"),
            ("hyper_light", "新規", "無制限"),
        ):
            with self.subTest(plan_id=plan_id, sales=sales, capacity=capacity):
                quote = build_quote(
                    {
                        "quote_id": "T-36-SL",
                        "model": "iPhone 16e(128GB)",
                        "sales_type": sales,
                        "plan_id": plan_id,
                        "data_plan": capacity,
                        "installment_months": 36,
                        "services": {
                            "ips": {"type": "subscription"},
                            "support_plan_id": "auto",
                        },
                        "universal_fee_tax_in": 4,
                        "universal_fee_tax_ex": 4,
                        "tax_rate": 0.10,
                    },
                    master,
                    plans,
                    services,
                )
                self.assertEqual(quote["installment_months"], 36)
                self.assertEqual(quote["periods"][0]["key"], "1_36")
                self.assertIsNotNone(quote["services"]["support"])

    def test_36_model_selection_from_pdf_checkboxes(self):
        """36回はPDFの全機種から選ぶ。未保存時は旧対象ルールで初期選択。"""
        from quote_system import installment_36 as i36

        master_36 = {
            "devices": [
                {"category": "iPhone", "model": "iPhone 17 Pro(256GB)",
                 "model_key": "iphone17pro256gb", "payment_36_flat": 5000, "total": 180000},
                {"category": "iPhone", "model": "iPhone 16e(128GB)",
                 "model_key": "iphone16e128gb", "payment_36_flat": 3308, "total": 119088},
                {"category": "Android", "model": "Restricted ※MM販路取扱不可",
                 "model_key": "restricted", "payment_36_flat": 1000, "total": 36000},
                {"category": "iPhone", "model": "iPhone 16e(128GB)",
                 "model_key": "iphone16e128gb", "payment_36_flat": 3308, "total": 119088},
            ]
        }
        empty_48 = {"devices": []}
        all_devices = i36.all_36_devices(master_36, empty_48)
        self.assertEqual(
            [d["model_key"] for d in all_devices], ["iphone17pro256gb", "iphone16e128gb"]
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "included_models_36.json"
            with (
                patch.object(i36, "INCLUDED_36_PATH", path),
                patch.object(i36, "TARGETS_PATH", Path(tmp) / "no_targets.json"),
                patch.object(i36, "DEVICE_MASTER_48_PATH", Path(tmp) / "no_master.json"),
            ):
                # 未保存: 旧ルール既定値（16e は対象、17 Pro は対象外）
                self.assertEqual(i36.load_included_36_keys(master_36), {"iphone16e128gb"})
                i36.save_included_36_keys(["iphone17pro256gb", "unknown"])
                self.assertEqual(i36.load_included_36_keys(master_36), {"iphone17pro256gb"})
                self.assertEqual(
                    [d["model"] for d in i36.selected_36_devices(master_36)],
                    ["iPhone 17 Pro(256GB)"],
                )
                i36.save_included_36_keys([])
                self.assertEqual(i36.selected_36_devices(master_36), [])

    def test_36_only_devices_from_48_price_list_are_added(self):
        """通常価格表で36回欄だけに金額がある機種（データ通信）を36回の一覧に足す。"""
        from quote_system import installment_36 as i36

        empty_48_payments = {
            sales: {"1_12": None, "13_24": None, "25_48": None} for sales in SALES_COLUMNS
        }
        master_48 = {
            "devices": [
                {"category": "データ通信", "model": "Pocket WiFi 5G A503SH",
                 "model_key": "pocketwifi5ga503sh", "status": "販売中",
                 "payment_48": empty_48_payments, "payment_36": 1320, "total": 47520},
                # 48回もある機種は足さない（36回PDF側で扱う）
                {"category": "iPhone", "model": "iPhone 17(256GB)",
                 "model_key": "iphone17256gb", "status": "販売中",
                 "payment_48": {s: {"1_12": 3000, "13_24": 3000, "25_48": 3000}
                                for s in SALES_COLUMNS},
                 "payment_36": 4000, "total": 144000},
                # 検算が合わない行は足さない
                {"category": "データ通信", "model": "Broken", "model_key": "broken",
                 "status": "販売中", "payment_48": empty_48_payments,
                 "payment_36": 100, "total": 999},
            ]
        }
        master_36 = {
            "devices": [
                {"category": "iPhone", "model": "iPhone 16e(128GB)",
                 "model_key": "iphone16e128gb", "payment_36_flat": 3308, "total": 119088},
            ]
        }
        devices = i36.all_36_devices(master_36, master_48)
        self.assertEqual(
            [d["model_key"] for d in devices], ["iphone16e128gb", "pocketwifi5ga503sh"]
        )
        wifi = devices[1]
        self.assertEqual(wifi["category"], "データ通信")
        self.assertEqual(wifi["payment_36_flat"], 1320)
        self.assertEqual(wifi["installment_months"], 36)

        plans = load_json(DATA_DIR / "plans.json")
        services = load_json(DATA_DIR / "services.json")
        quote = build_quote(
            {
                "quote_id": "T-36-DATA",
                "model": wifi["model"],
                "sales_type": "新規",
                "plan_id": "biz_plus",
                "data_plan": "20GB",
                "installment_months": 36,
                "services": {"ips": {"type": "subscription"}, "support_plan_id": "auto"},
                "universal_fee_tax_in": 4,
                "universal_fee_tax_ex": 4,
                "tax_rate": 0.10,
            },
            {"devices": devices},
            plans,
            services,
        )
        self.assertEqual(quote["periods"][0]["key"], "1_36")
        self.assertEqual(quote["periods"][0]["device_payment"], 1320)

        from quote_system.batch_service import quote_variants

        variants = list(quote_variants(wifi, plans, include_mnp_shinki_irs=True))
        self.assertTrue(variants)
        self.assertEqual({v["plan_id"] for v in variants}, {"biz_plus"})
        self.assertFalse({"MNP", "番号移行"} & {v["sales_type"] for v in variants})

    def test_run_individual_36_data_device_pdf_if_present(self):
        """実データ: データ通信の機種で36回の個別PDFが1ページで出る。"""
        folder = UPDATE_DIR / "36回割賦"
        if not list(folder.glob("*.pdf")):
            self.skipTest("no 36 PDF in update folder")
        import pdfplumber

        from quote_system.installment_36 import all_36_devices, import_installment_36_master

        devices = all_36_devices(import_installment_36_master())
        data_device = next((d for d in devices if d.get("category") == "データ通信"), None)
        if data_device is None:
            self.skipTest("no data-communication device in price lists")
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            included = Path(tmp) / "included_models_36.json"
            included.write_text(
                '{"model_keys": ["%s"]}' % data_device["model_key"], encoding="utf-8"
            )
            with (
                patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT_36", out),
                patch("quote_system.installment_36.INCLUDED_36_PATH", included),
            ):
                result = run_individual(
                    model=data_device["model"],
                    sales_type="新規",
                    plan_id="biz_plus",
                    data_plans=["20GB"],
                    ouchi_options=[False],
                    include_ips_subscription=True,
                    support_plan_id="auto",
                    installment_months=36,
                    unrestricted_individual=False,
                )
            pdfs = sorted(out.rglob("*.pdf"))
            self.assertEqual(result.generated_files, 1)
            self.assertEqual(pdfs[0].parts[len(out.parts)], "データ通信")
            with pdfplumber.open(pdfs[0]) as doc:
                self.assertEqual(len(doc.pages), 1)
                text = doc.pages[0].extract_text() or ""
            self.assertIn("36", text)

    def test_run_individual_36_super_hyper_pdfs(self):
        """36回の個別作成でスーパー／ハイパーのPDFが実際に1ページで出る。"""
        folder = UPDATE_DIR / "36回割賦"
        if not list(folder.glob("*.pdf")):
            self.skipTest("no 36 PDF in update folder")
        import pdfplumber

        from quote_system.installment_36 import import_installment_36_master

        targets = filter_36_target_devices(import_installment_36_master())
        iphone = next((d for d in targets if d.get("category") == "iPhone"), None)
        if iphone is None:
            self.skipTest("no iPhone in 36 targets")
        cases = (
            ("機種変更・移動機物品販売", "super_light", ["50GB"]),
            ("MNP", "super_light", ["5GB", "20GB", "50GB", "無制限"]),
            ("新規", "hyper_light", ["5GB", "20GB", "無制限"]),
        )
        for sales, plan_id, capacities in cases:
            with self.subTest(sales=sales, plan_id=plan_id), TemporaryDirectory() as tmp:
                out = Path(tmp) / "out"
                included = Path(tmp) / "included_models_36.json"
                included.write_text(
                    '{"model_keys": ["%s"]}' % iphone["model_key"], encoding="utf-8"
                )
                with (
                    patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT_36", out),
                    patch("quote_system.installment_36.INCLUDED_36_PATH", included),
                ):
                    result = run_individual(
                        model=iphone["model"],
                        sales_type=sales,
                        plan_id=plan_id,
                        data_plans=capacities,
                        ouchi_options=[False],
                        include_ips_subscription=True,
                        support_plan_id="auto",
                        installment_months=36,
                        unrestricted_individual=False,
                    )
                pdfs = sorted(out.rglob("*.pdf"))
                self.assertEqual(result.generated_files, len(capacities))
                self.assertEqual(len(pdfs), len(capacities))
                with pdfplumber.open(pdfs[0]) as doc:
                    self.assertEqual(len(doc.pages), 1)
                    text = doc.pages[0].extract_text() or ""
                self.assertIn("36", text)
                self.assertIn("弊社特別割引", text)


if __name__ == "__main__":
    unittest.main()
