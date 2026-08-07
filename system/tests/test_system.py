import unittest
from pathlib import Path
from copy import deepcopy

from quote_system.batch_service import (
    _ips_filename_token,
    _quote_filename,
    _quote_relative_path,
    changed_model_keys,
    quote_variants,
)
from quote_system.config import DATA_DIR, load_json
from quote_system.pdf_renderer import _display_periods
from quote_system.price_pdf_parser import find_device
from quote_system.quote_service import build_quote


class QuoteSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device_master = load_json(DATA_DIR / "device_master.json")
        cls.plan_master = load_json(DATA_DIR / "plans.json")
        cls.service_master = load_json(DATA_DIR / "services.json")
        cls.request = load_json(DATA_DIR / "test_quote.json")

    def test_iphone_17_256gb_prices(self):
        device = find_device(self.device_master, "iPhone 17 256GB")
        self.assertEqual(device["payment_48"]["MNP"], {
            "1_12": 1,
            "13_24": 1,
            "25_48": 7529,
        })
        self.assertEqual(device["payment_48"]["新規"]["1_12"], 1375)
        self.assertEqual(device["payment_48"]["番号移行"]["1_12"], 875)
        self.assertEqual(
            device["payment_48"]["機種変更・移動機物品販売"]["1_12"],
            3700,
        )
        self.assertEqual(device["total"], 180720)
        self.assertTrue(all(device["validation"].values()))

    def test_quote_totals(self):
        quote = build_quote(
            self.request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["components"]["communication_tax_ex"], 1980)
        self.assertEqual(quote["components"]["communication_tax_in"], 2178)
        self.assertEqual(quote["components"]["biz_package_discount_tax_ex"], -4300)
        self.assertEqual(quote["components"]["additional_discount_tax_ex"], -1500)
        self.assertEqual(quote["components"]["additional_discount_name"], "ハイパーライト割")
        from quote_system.pdf_renderer import _pdf_additional_discount_label
        self.assertEqual(
            _pdf_additional_discount_label(quote["components"]["additional_discount_name"]),
            "弊社特別割引",
        )
        self.assertEqual(_pdf_additional_discount_label("スーパーライト割"), "弊社特別割引")
        self.assertEqual(_pdf_additional_discount_label("特別割引"), "弊社特別割引")
        self.assertEqual(quote["services"]["ips"]["name"], "IPSラージプラン")
        self.assertEqual(quote["services"]["ips"]["monthly_charge_tax_in"], 1540)
        self.assertEqual(quote["services"]["support"]["name"], "携帯電話安心サポートS")
        self.assertEqual(
            [period["monthly_total_tax_in"] for period in quote["periods"]],
            [5351, 5351, 12879],
        )
        self.assertEqual(
            [period["monthly_total_display_tax_ex"] for period in quote["periods"]],
            [4865, 4865, 12393],
        )

    def test_upfront_ips_monthly_equivalent(self):
        request = {**self.request, "plan_id": "biz_plus", "initial_fee_mode": "standard"}
        request["services"] = {
            "ips": {"type": "upfront", "plan_id": "ips_gold_24_water"},
            "support_plan_id": None,
        }
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["initial_total_tax_in"], 45320)
        self.assertEqual(quote["services"]["ips"]["monthly_equivalent_tax_in"], 1683)
        self.assertEqual(quote["periods"][0]["monthly_total_tax_in"], 3833)
        self.assertEqual(quote["periods"][0]["monthly_equivalent_total_tax_in"], 5516)

    def test_upfront_ips_keeps_plan_support_mapping(self):
        request = deepcopy(self.request)
        request["services"] = {
            "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
            "support_plan_id": "auto",
        }
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["services"]["ips"]["plan_id"], "ips_gold_24")
        self.assertEqual(quote["services"]["support"]["plan_id"], "support_s")

    def test_revised_initial_fee(self):
        request = {**self.request, "initial_fee_mode": "standard"}
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["initial_fee_tax_in"], 4950)
        self.assertEqual(self.plan_master["common"]["initial_fee_effective_from"], "2026-01-21")
        special = build_quote(
            {**self.request, "initial_fee_mode": "special_3000"},
            self.device_master,
            self.plan_master,
            self.service_master,
        )
        self.assertEqual(special["initial_fee_tax_in"], 0)
        self.assertEqual(special["special_initial_fee_tax_ex"], 3000)

    def test_ips_can_be_removed_without_losing_discounts(self):
        request = deepcopy(self.request)
        request["services"] = {"ips": {"type": "none"}, "support_plan_id": "auto"}
        quote = build_quote(request, self.device_master, self.plan_master, self.service_master)
        self.assertIsNone(quote["services"]["ips"])
        self.assertEqual(quote["components"]["biz_package_discount_tax_ex"], -4300)
        self.assertEqual(quote["components"]["additional_discount_tax_ex"], -1500)
        self.assertEqual(quote["periods"][0]["monthly_total_display_tax_ex"], 3465)

    def test_iphone_category_is_available_for_notes(self):
        quote = build_quote(
            self.request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["device_category"], "iPhone")

    def test_rt_department_address_uses_hirai_4f_only(self):
        from quote_system.pdf_renderer import _resolve_department_header

        # Synthetic company — no production addresses/phones in the repo.
        company = {
            "name": "Test Co",
            "department": "TM事業本部",
            "registration_number": "G0000000",
            "postal_address": "本社ビル",
            "phone": "000-0000-0000",
            "fax": "",
            "department_contacts": {
                "TM事業本部": {"phone": "000-0000-0000", "fax": ""},
                "RT事業部": {
                    "phone": "000-0000-1111",
                    "fax": "000-0000-2222",
                    "postal_address": "本社ビル4F",
                },
            },
        }
        _, _, default_address = _resolve_department_header(
            {**company, "department": "TM事業本部"}
        )
        self.assertIn("本社ビル", default_address)
        self.assertNotIn("4F", default_address)
        _, _, rt_address = _resolve_department_header(
            {**company, "department": "RT事業部"}
        )
        self.assertIn("本社ビル4F", rt_address)

    def test_merge_missing_company_fields_fills_empty_fax_only(self):
        from quote_system.config import merge_missing_company_fields

        local = {
            "phone": "111",
            "fax": "",
            "department_contacts": {
                "TM事業本部": {"phone": "111", "fax": ""},
                "RT事業部": {"phone": "222", "fax": ""},
            },
        }
        bundled = {
            "phone": "999",
            "fax": "bundled-top-fax",
            "department_contacts": {
                "TM事業本部": {"phone": "should-not-use", "fax": ""},
                "RT事業部": {"phone": "should-not-use", "fax": "000-0000-9002"},
            },
        }
        self.assertTrue(merge_missing_company_fields(local, bundled))
        self.assertEqual(local["fax"], "bundled-top-fax")
        self.assertEqual(local["phone"], "111")  # 既存は維持
        self.assertEqual(local["department_contacts"]["RT事業部"]["fax"], "000-0000-9002")
        self.assertEqual(local["department_contacts"]["RT事業部"]["phone"], "222")
        # 既に FAX がある場合は上書きしない
        local["department_contacts"]["RT事業部"]["fax"] = "keep-me"
        self.assertFalse(merge_missing_company_fields(local, bundled))
        self.assertEqual(local["department_contacts"]["RT事業部"]["fax"], "keep-me")

    def test_department_contacts_resolve_per_department(self):
        from quote_system.pdf_renderer import _resolve_department_header

        company = {
            "name": "Test Co",
            "department": "TM事業本部",
            "registration_number": "G0000000",
            "postal_address": "本社ビル",
            "phone": "000-0000-0000",
            "fax": "",
            "departments": ["TM事業本部", "RT事業部", "CRM事業部", "AQ事業部"],
            "department_contacts": {
                "TM事業本部": {"phone": "000-0000-0001", "fax": ""},
                "RT事業部": {
                    "phone": "000-0000-0002",
                    "fax": "000-0000-9002",
                    "postal_address": "本社ビル4F",
                },
                "CRM事業部": {"phone": "000-0000-0003", "fax": "000-0000-9003"},
                "AQ事業部": {
                    "phone": "000-0000-0004",
                    "fax": "000-0000-9004",
                    "postal_address": "別拠点ビル",
                },
            },
        }
        expected = {
            "TM事業本部": ("000-0000-0001", "", "本社ビル"),
            "RT事業部": ("000-0000-0002", "000-0000-9002", "本社ビル4F"),
            "CRM事業部": ("000-0000-0003", "000-0000-9003", "本社ビル"),
            "AQ事業部": ("000-0000-0004", "000-0000-9004", "別拠点ビル"),
        }
        for department, (phone, fax, address_token) in expected.items():
            with self.subTest(department=department):
                got_phone, got_fax, got_address = _resolve_department_header(
                    {**company, "department": department}
                )
                self.assertEqual(got_phone, phone)
                self.assertEqual(got_fax, fax)
                self.assertIn(address_token, got_address)
                if department in ("TM事業本部", "CRM事業部"):
                    self.assertNotIn("4F", got_address)
                if department == "AQ事業部":
                    self.assertNotIn("本社ビル", got_address)

    def test_pdf_header_shows_selected_department_contact(self):
        import pdfplumber
        from tempfile import TemporaryDirectory
        from quote_system.pdf_renderer import render_quote

        quote = build_quote(
            self.request, self.device_master, self.plan_master, self.service_master
        )
        company = {
            "name": "Test Co",
            "department": "TM事業本部",
            "registration_number": "G1901279",
            "postal_address": "本社ビル",
            "phone": "000-0000-0000",
            "fax": "",
            "logo_file": "assets/company_logo.png",
            "department_contacts": {
                "TM事業本部": {"phone": "000-0000-0001", "fax": ""},
                "RT事業部": {
                    "phone": "000-0000-0002",
                    "fax": "000-0000-9002",
                    "postal_address": "本社ビル4F",
                },
                "CRM事業部": {
                    "phone": "000-0000-0003",
                    "fax": "000-0000-9003",
                },
                "AQ事業部": {
                    "phone": "000-0000-0004",
                    "fax": "000-0000-9004",
                    "postal_address": "別拠点ビル",
                },
            },
        }
        cases = {
            "TM事業本部": {
                "department": "TM事業本部",
                "phone": "000-0000-0001",
                "fax": None,
                "address": "本社ビル",
                "not_address": "4F",
            },
            "RT事業部": {
                "department": "RT事業部",
                "phone": "000-0000-0002",
                "fax": "000-0000-9002",
                "address": "本社ビル4F",
                "not_address": None,
            },
            "CRM事業部": {
                "department": "CRM事業部",
                "phone": "000-0000-0003",
                "fax": "000-0000-9003",
                "address": "本社ビル",
                "not_address": "4F",
            },
            "AQ事業部": {
                "department": "AQ事業部",
                "phone": "000-0000-0004",
                "fax": "000-0000-9004",
                "address": "別拠点ビル",
                "not_address": "本社ビル",
            },
        }

        with TemporaryDirectory() as tmp:
            for department, expect in cases.items():
                with self.subTest(department=department):
                    output = Path(tmp) / f"{department}.pdf"
                    render_quote(
                        quote,
                        {**company, "department": department},
                        output,
                    )
                    with pdfplumber.open(output) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                    self.assertIn(expect["department"], text)
                    self.assertIn(f"TEL：{expect['phone']}", text)
                    self.assertIn(expect["address"], text)
                    if expect["fax"]:
                        self.assertRegex(
                            text,
                            rf"TEL：{expect['phone']}\s+FAX：{expect['fax']}",
                        )
                    else:
                        self.assertIn(f"TEL：{expect['phone']}", text)
                        self.assertNotIn("FAX：", text)
                    if expect["not_address"]:
                        self.assertNotIn(expect["not_address"], text)
                    self.assertIn("届出番号：G1901279", text)
                    self.assertIn("MNPお見積り", text)

    def test_support_auto_mapping(self):
        super_light = {**self.request, "plan_id": "super_light", "data_plan": "50GB"}
        quote = build_quote(
            super_light, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["services"]["support"]["plan_id"], "support_xs")
        self.assertEqual(quote["services"]["support"]["monthly_fee_tax_ex"], 980)
        self.assertEqual(quote["services"]["support"]["monthly_fee_tax_in"], 1078)

        light = {**self.request, "plan_id": "light", "data_plan": "20GB"}
        light_quote = build_quote(
            light, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(light_quote["services"]["support"]["plan_id"], "support_xs")

        biz_plus = {**self.request, "plan_id": "biz_plus"}
        quote = build_quote(
            biz_plus, self.device_master, self.plan_master, self.service_master
        )
        self.assertIsNone(quote["services"]["support"])

    def test_standard_batch_variants(self):
        device = find_device(self.device_master, "iPhone 17 256GB")
        variants = list(quote_variants(device, self.plan_master))
        self.assertEqual(len(variants), 78)
        self.assertEqual({item["sales_type"] for item in variants}, {
            "MNP", "新規", "番号移行", "機種変更・移動機物品販売"
        })
        # ライト系割引プランでは1GBを作らない（Bizは機種変更のみ1GB可）
        self.assertFalse(any(
            item["data_plan"] == "1GB"
            and item["plan_id"] in {"light", "super_light", "hyper_light"}
            for item in variants
        ))
        ones = [item for item in variants if item["data_plan"] == "1GB"]
        self.assertTrue(ones)
        self.assertTrue(all(
            item["plan_id"] == "biz_plus"
            and item["sales_type"] == "機種変更・移動機物品販売"
            for item in ones
        ))
        # 機種変更では Biz＋ とハイパーに 5GB がある
        kishu_five = {
            item["plan_id"]
            for item in variants
            if item["sales_type"] == "機種変更・移動機物品販売"
            and item["data_plan"] == "5GB"
        }
        self.assertEqual(kishu_five, {"biz_plus", "hyper_light"})
        # スーパーライトは50GBのみ
        self.assertTrue(
            all(
                item["data_plan"] == "50GB"
                for item in variants
                if item["plan_id"] == "super_light"
            )
        )
        # ライトは1GB以外・機種変更では使わない
        self.assertTrue(
            all(
                item["data_plan"] != "1GB"
                for item in variants
                if item["plan_id"] == "light"
            )
        )
        self.assertFalse(any(
            item["plan_id"] == "light" and item["sales_type"] == "機種変更・移動機物品販売"
            for item in variants
        ))
        self.assertEqual({item["ouchi_discount_applied"] for item in variants}, {False, True})
        self.assertFalse(any(
            item["data_plan"] == "5GB" and item["ouchi_discount_applied"]
            for item in variants
        ))
        self.assertTrue(all(item["ips"]["type"] == "subscription" for item in variants))
        self.assertTrue(all(item["initial_fee_mode"] == "special_3000" for item in variants))

        with_no_ips = list(quote_variants(device, self.plan_master, include_no_ips=True))
        self.assertEqual(len(with_no_ips), 156)
        self.assertEqual({item["ips"]["type"] for item in with_no_ips}, {"subscription", "none"})

        with_standard_fee = list(quote_variants(
            device, self.plan_master, include_standard_initial_fee=True
        ))
        self.assertEqual(len(with_standard_fee), 156)
        self.assertEqual(
            {item["initial_fee_mode"] for item in with_standard_fee},
            {"special_3000", "standard"},
        )

    def test_feature_phone_data_plan_rule(self):
        device = find_device(self.device_master, "DIGNOケータイ4")
        variants = list(quote_variants(device, self.plan_master))
        self.assertEqual({item["data_plan"] for item in variants}, {"1GB"})
        self.assertEqual({item["plan_id"] for item in variants}, {"biz_plus"})
        self.assertEqual({item["ouchi_discount_applied"] for item in variants}, {False})

        # ライト系プランは1GBを対象としない（ケータイでもハイパーを作らない）
        with self.assertRaisesRegex(ValueError, "1GB|50GBのみ"):
            build_quote(
                {
                    **self.request,
                    "model": device["model"],
                    "plan_id": "hyper_light",
                    "data_plan": "1GB",
                    "sales_type": "MNP",
                },
                self.device_master,
                self.plan_master,
                self.service_master,
            )

        request = deepcopy(self.request)
        request.update({"model": device["model"], "plan_id": "biz_plus", "data_plan": "1GB"})
        quote = build_quote(request, self.device_master, self.plan_master, self.service_master)
        self.assertEqual(quote["data_plan"], "1GB")

        request["data_plan"] = "5GB"
        with self.assertRaisesRegex(ValueError, "1GBのみ"):
            build_quote(request, self.device_master, self.plan_master, self.service_master)

    def test_non_feature_phone_cannot_use_1gb(self):
        request = deepcopy(self.request)
        request.update({"plan_id": "biz_plus", "data_plan": "1GB"})
        with self.assertRaisesRegex(ValueError, "5GB以上"):
            build_quote(request, self.device_master, self.plan_master, self.service_master)

    def test_ouchi_discount_schedule(self):
        request = deepcopy(self.request)
        request["data_plan"] = "20GB"
        request["ouchi_discount_applied"] = True
        quote = build_quote(request, self.device_master, self.plan_master, self.service_master)
        self.assertEqual(quote["components"]["ouchi_discount_tax_ex"], -1000)
        self.assertTrue(quote["ouchi_discount_applied"])

        request["data_plan"] = "50GB"
        request["plan_id"] = "super_light"
        quote = build_quote(request, self.device_master, self.plan_master, self.service_master)
        self.assertEqual(quote["components"]["ouchi_discount_tax_ex"], -1000)

        request["data_plan"] = "5GB"
        with self.assertRaisesRegex(ValueError, "スーパーライトはパケット50GBのみ"):
            build_quote(request, self.device_master, self.plan_master, self.service_master)

    def test_ouchi_discount_rejects_5gb(self):
        request = deepcopy(self.request)
        request["data_plan"] = "5GB"
        request["ouchi_discount_applied"] = True
        with self.assertRaisesRegex(ValueError, "5GB見積は作成しません"):
            build_quote(request, self.device_master, self.plan_master, self.service_master)

    def test_equal_initial_payment_periods_are_merged_for_pdf(self):
        from quote_system.pdf_renderer import (
            _display_periods_for_quote,
            _ips_monthly_for_period,
            _ips_monthly_tax_in,
        )

        quote = build_quote(
            self.request, self.device_master, self.plan_master, self.service_master
        )
        displayed = _display_periods(quote["periods"])
        self.assertEqual([period["label"] for period in displayed], [
            "分割支払 1～24回目", "分割支払 25～48回目",
        ])

        changed = deepcopy(quote["periods"])
        changed[1]["device_payment"] += 1
        self.assertEqual(len(_display_periods(changed)), 3)

        # 24か月通常IPSのランニング表記: 25回目以降は修理保証0
        gold24_request = deepcopy(self.request)
        gold24_request.update({
            "ips_display_mode": "monthly_as_running",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
                "support_plan_id": None,
            },
        })
        gold24 = build_quote(
            gold24_request, self.device_master, self.plan_master, self.service_master
        )
        gold_periods = _display_periods_for_quote(gold24)
        self.assertEqual([p["label"] for p in gold_periods], [
            "分割支払 1～24回目", "分割支払 25～48回目",
        ])
        monthly = _ips_monthly_tax_in(gold24["services"]["ips"])
        amounts = [
            _ips_monthly_for_period(
                p,
                ips=gold24["services"]["ips"],
                ips_display_mode="monthly_as_running",
                ips_tax_in_monthly=monthly,
            )
            for p in gold_periods
        ]
        self.assertEqual(amounts[0], monthly)
        self.assertEqual(amounts[1], 0)

        # 36か月通常IPS: 25～48を 25～36 / 37～48 に分割し、37以降は0
        plat36_request = deepcopy(self.request)
        plat36_request.update({
            "ips_display_mode": "monthly_as_running",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_platinum_36"},
                "support_plan_id": None,
            },
        })
        plat36 = build_quote(
            plat36_request, self.device_master, self.plan_master, self.service_master
        )
        plat_periods = _display_periods_for_quote(plat36)
        self.assertEqual([p["label"] for p in plat_periods], [
            "分割支払 1～24回目",
            "分割支払 25～36回目",
            "分割支払 37～48回目",
        ])
        monthly36 = _ips_monthly_tax_in(plat36["services"]["ips"])
        amounts36 = [
            _ips_monthly_for_period(
                p,
                ips=plat36["services"]["ips"],
                ips_display_mode="monthly_as_running",
                ips_tax_in_monthly=monthly36,
            )
            for p in plat_periods
        ]
        self.assertEqual(amounts36, [monthly36, monthly36, 0])

    def test_output_folder_hierarchy(self):
        device = find_device(self.device_master, self.request["model"])
        request = deepcopy(self.request)
        request["initial_fee_mode"] = "special_3000"
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        variant = {
            "sales_type": self.request["sales_type"],
            "plan_id": self.request["plan_id"],
            "data_plan": self.request["data_plan"],
            "initial_fee_mode": "special_3000",
            "ips_display_mode": "lump",
        }
        relative = _quote_relative_path(
            device, variant, quote, "subscription", "SB光なし"
        )
        # スーパー／ハイパー: Biz＋と並ぶ IPSあり / IPSサブスク
        self.assertEqual(relative.parts, (
            "iPhone", "iPhone_17(256GB)", "MNP", "SB光なし",
            "IPSあり", "IPSサブスク",
            "iPhone17(256GB)_5GB.pdf",
        ))
        self.assertNotIn("ハイパーライト", str(relative))
        self.assertNotIn("スーパーライト", str(relative))
        self.assertNotIn("安心サポート", str(relative))
        self.assertNotIn("初期費用", str(relative))
        self.assertNotIn("事務手数料", str(relative))

        upfront_request = deepcopy(self.request)
        upfront_request.update({
            "data_plan": "50GB",
            "plan_id": "super_light",
            "initial_fee_mode": "special_3000",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_platinum_36_water"},
                "support_plan_id": "auto",
            },
        })
        upfront_quote = build_quote(
            upfront_request, self.device_master, self.plan_master, self.service_master
        )
        upfront_variant = {
            "sales_type": upfront_request["sales_type"],
            "plan_id": upfront_request["plan_id"],
            "data_plan": upfront_request["data_plan"],
            "initial_fee_mode": "special_3000",
            "ips_display_mode": "lump",
        }
        upfront_relative = _quote_relative_path(
            device, upfront_variant, upfront_quote, "ips_platinum_36_water", "SB光なし"
        )
        self.assertEqual(upfront_relative.parts[4], "IPSあり")
        self.assertEqual(upfront_relative.parts[5], "IPS一括表記")
        # 通常IPSはゴ/プ等をフォルダで分け、ファイル名は機種_容量のみ
        self.assertEqual(upfront_relative.parts[6], "プラチナ36水没")
        self.assertEqual(upfront_relative.name, "iPhone17(256GB)_50GB.pdf")
        self.assertNotIn("スーパーライト", str(upfront_relative))
        self.assertNotIn("IPS一括型", str(upfront_relative))
        self.assertNotIn("安心サポート", str(upfront_relative))
        self.assertNotIn("初期費用", str(upfront_relative))

        running_variant = {**upfront_variant, "ips_display_mode": "monthly_as_running"}
        running_quote = build_quote(
            {**upfront_request, "ips_display_mode": "monthly_as_running"},
            self.device_master, self.plan_master, self.service_master,
        )
        running_relative = _quote_relative_path(
            device, running_variant, running_quote, "ips_platinum_36_water", "SB光なし"
        )
        self.assertEqual(running_relative.parts[4], "IPSあり")
        self.assertEqual(running_relative.parts[5], "通常IPSランニングコスト表記")
        self.assertEqual(running_relative.parts[6], "プラチナ36水没")
        self.assertEqual(
            running_quote["initial_total_tax_ex"],
            running_quote["initial_fee_tax_ex"] + running_quote["special_initial_fee_tax_ex"],
        )

        gold24_request = deepcopy(self.request)
        gold24_request.update({
            "data_plan": "50GB",
            "plan_id": "super_light",
            "initial_fee_mode": "special_3000",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
                "support_plan_id": None,
            },
        })
        gold24_quote = build_quote(
            gold24_request, self.device_master, self.plan_master, self.service_master
        )
        gold24_relative = _quote_relative_path(
            device,
            {
                "sales_type": gold24_request["sales_type"],
                "plan_id": gold24_request["plan_id"],
                "data_plan": gold24_request["data_plan"],
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            gold24_quote,
            "ips_gold_24",
            "SB光なし",
        )
        self.assertEqual(gold24_relative.parts[4], "IPSあり")
        self.assertEqual(gold24_relative.parts[5], "IPS一括表記")
        self.assertEqual(gold24_relative.parts[6], "ゴールド24")
        # 強制加入プランでサポートなしを選んだときだけサポートフォルダを付ける
        self.assertEqual(gold24_relative.parts[7], "安心サポートなし")
        self.assertEqual(gold24_relative.name, "iPhone17(256GB)_50GB.pdf")

        none_request = deepcopy(self.request)
        none_request["services"] = {"ips": {"type": "none"}, "support_plan_id": None}
        none_quote = build_quote(
            none_request, self.device_master, self.plan_master, self.service_master
        )
        none_relative = _quote_relative_path(
            device, variant, none_quote, "none", "SB光なし"
        )
        self.assertEqual(none_relative.parts[4], "IPSなし")
        self.assertEqual(none_relative.parts[5], "安心サポートなし")
        self.assertEqual(
            _quote_filename(device, variant, none_quote),
            "iPhone17(256GB)_5GB.pdf",
        )
        self.assertNotIn("IPSあり", str(none_relative))

        # サポートなしバリアントも作る場合はあり側にもフォルダを付ける
        branched = _quote_relative_path(
            device, variant, quote, "subscription", "SB光なし",
            include_no_support=True,
        )
        self.assertEqual(branched.parts[-2], "安心サポートあり")
        self.assertEqual(branched.name, "iPhone17(256GB)_5GB.pdf")
        self.assertIn("IPSあり", branched.parts)
        self.assertIn("IPSサブスク", branched.parts)

        # 事務手数料あり版との同時生成時は標準側にも初期費用フォルダを付ける
        fee_branched = _quote_relative_path(
            device, variant, quote, "subscription", "SB光なし",
            include_standard_initial_fee=True,
        )
        self.assertEqual(fee_branched.parts[4], "初期費用3300円")
        self.assertEqual(fee_branched.parts[5], "IPSあり")
        self.assertEqual(fee_branched.parts[6], "IPSサブスク")
        standard_request = deepcopy(self.request)
        standard_request["initial_fee_mode"] = "standard"
        standard_request["initial_fee_tax_in"] = int(
            self.plan_master["common"]["initial_fee_tax_in"]
        )
        standard_request["initial_fee_tax_ex"] = int(
            self.plan_master["common"]["initial_fee_tax_ex"]
        )
        standard_quote = build_quote(
            standard_request, self.device_master, self.plan_master, self.service_master
        )
        standard_relative = _quote_relative_path(
            device,
            {**variant, "initial_fee_mode": "standard"},
            standard_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(standard_relative.parts[4], "事務手数料あり")
        self.assertIn("IPSあり", standard_relative.parts)
        self.assertNotIn("初期費用3300円", str(standard_relative))

        # 自動サポートのない Bizパッケージ＋ は「なし」固定なのでフォルダ省略
        biz_request = deepcopy(self.request)
        biz_request["plan_id"] = "biz_plus"
        biz_request["services"] = {"ips": {"type": "subscription"}, "support_plan_id": "auto"}
        biz_quote = build_quote(
            biz_request, self.device_master, self.plan_master, self.service_master
        )
        self.assertIsNone(biz_quote["services"]["support"])
        biz_relative = _quote_relative_path(
            device,
            {**variant, "plan_id": "biz_plus"},
            biz_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(biz_relative.parts[4], "Bizパッケージ＋")
        self.assertNotIn("安心サポート", str(biz_relative))
        self.assertEqual(biz_relative.parts[5], "IPSサブスク")
        biz_with_support_request = deepcopy(biz_request)
        biz_with_support_request["services"] = {
            "ips": {"type": "subscription"},
            "support_plan_id": "support_s",
        }
        biz_with_support = build_quote(
            biz_with_support_request,
            self.device_master,
            self.plan_master,
            self.service_master,
        )
        biz_with_support_relative = _quote_relative_path(
            device,
            {**variant, "plan_id": "biz_plus"},
            biz_with_support,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(biz_with_support_relative.parts[-2], "安心サポートあり")

        kishu_request = deepcopy(self.request)
        kishu_request["sales_type"] = "機種変更・移動機物品販売"
        kishu_quote = build_quote(
            kishu_request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(kishu_quote["sales_type"], "機種変更・移動機物品販売")
        kishu_relative = _quote_relative_path(
            device,
            {**variant, "sales_type": kishu_request["sales_type"]},
            kishu_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(kishu_relative.parts[2], "機種変更")
        self.assertNotIn("移動機物品販売", str(kishu_relative))

        # 機種変更×スーパー／ハイパー（標準）も同じ統合レイアウト
        kishu_super = deepcopy(self.request)
        kishu_super.update({
            "sales_type": "機種変更・移動機物品販売",
            "plan_id": "super_light",
            "data_plan": "50GB",
        })
        kishu_super_quote = build_quote(
            kishu_super, self.device_master, self.plan_master, self.service_master
        )
        kishu_super_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_super["sales_type"],
                "plan_id": "super_light",
                "data_plan": "50GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            kishu_super_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(
            kishu_super_path.parts,
            (
                "iPhone",
                "iPhone_17(256GB)",
                "機種変更",
                "SB光なし",
                "IPSあり",
                "IPSサブスク",
                "iPhone17(256GB)_50GB.pdf",
            ),
        )
        self.assertNotIn("特別割引", str(kishu_super_path))
        self.assertNotIn("Bizパッケージ", str(kishu_super_path))
        kishu_hyper = deepcopy(self.request)
        kishu_hyper.update({
            "sales_type": "機種変更・移動機物品販売",
            "plan_id": "hyper_light",
            "data_plan": "5GB",
        })
        kishu_hyper_quote = build_quote(
            kishu_hyper, self.device_master, self.plan_master, self.service_master
        )
        kishu_hyper_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_hyper["sales_type"],
                "plan_id": "hyper_light",
                "data_plan": "5GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            kishu_hyper_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(kishu_hyper_path.parts[-1], "iPhone17(256GB)_5GB.pdf")
        self.assertEqual(kishu_hyper_path.parts[3], "SB光なし")
        self.assertEqual(kishu_hyper_path.parts[4], "IPSあり")
        self.assertEqual(kishu_hyper_path.parts[5], "IPSサブスク")
        self.assertEqual(len(kishu_hyper_path.parts), 7)
        # Bizパッケージ＋ は従来どおりプランフォルダを作る
        kishu_biz = deepcopy(self.request)
        kishu_biz.update({
            "sales_type": "機種変更・移動機物品販売",
            "plan_id": "biz_plus",
            "data_plan": "5GB",
        })
        kishu_biz_quote = build_quote(
            kishu_biz, self.device_master, self.plan_master, self.service_master
        )
        kishu_biz_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_biz["sales_type"],
                "plan_id": "biz_plus",
                "data_plan": "5GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            kishu_biz_quote,
            "subscription",
            "SB光なし",
        )
        self.assertEqual(kishu_biz_path.parts[4], "Bizパッケージ＋")
        # 機種変更で IPS なしなど分岐があるときは IPS フォルダを付ける
        kishu_no_ips = deepcopy(kishu_hyper)
        kishu_no_ips["services"] = {"ips": {"type": "none"}, "support_plan_id": "auto"}
        kishu_no_ips_quote = build_quote(
            kishu_no_ips, self.device_master, self.plan_master, self.service_master
        )
        kishu_no_ips_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_no_ips["sales_type"],
                "plan_id": "hyper_light",
                "data_plan": "5GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            kishu_no_ips_quote,
            "none",
            "SB光なし",
        )
        self.assertIn("IPSなし", kishu_no_ips_path.parts)

        # 機種変更＋通常IPSも同様（一括表記／ランニングコスト表記）
        kishu_upfront = deepcopy(self.request)
        kishu_upfront.update({
            "sales_type": "機種変更・移動機物品販売",
            "plan_id": "super_light",
            "data_plan": "50GB",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_platinum_36_water"},
                "support_plan_id": "auto",
            },
        })
        kishu_upfront_quote = build_quote(
            kishu_upfront, self.device_master, self.plan_master, self.service_master
        )
        kishu_lump_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_upfront["sales_type"],
                "plan_id": "super_light",
                "data_plan": "50GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "lump",
            },
            kishu_upfront_quote,
            "ips_platinum_36_water",
            "SB光なし",
        )
        self.assertEqual(
            kishu_lump_path.parts,
            (
                "iPhone",
                "iPhone_17(256GB)",
                "機種変更",
                "SB光なし",
                "IPSあり",
                "IPS一括表記",
                "プラチナ36水没",
                "iPhone17(256GB)_50GB.pdf",
            ),
        )
        self.assertNotIn("スーパーライト", str(kishu_lump_path))
        self.assertNotIn("ハイパーライト", str(kishu_lump_path))
        kishu_hyper_upfront = deepcopy(kishu_upfront)
        kishu_hyper_upfront.update({
            "plan_id": "hyper_light",
            "data_plan": "5GB",
            "ips_display_mode": "monthly_as_running",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
                "support_plan_id": "auto",
            },
        })
        kishu_hyper_upfront_quote = build_quote(
            kishu_hyper_upfront, self.device_master, self.plan_master, self.service_master
        )
        kishu_running_path = _quote_relative_path(
            device,
            {
                "sales_type": kishu_hyper_upfront["sales_type"],
                "plan_id": "hyper_light",
                "data_plan": "5GB",
                "initial_fee_mode": "special_3000",
                "ips_display_mode": "monthly_as_running",
            },
            kishu_hyper_upfront_quote,
            "ips_gold_24",
            "SB光なし",
        )
        self.assertEqual(kishu_running_path.parts[4], "IPSあり")
        self.assertEqual(kishu_running_path.parts[5], "通常IPSランニングコスト表記")
        self.assertEqual(kishu_running_path.parts[6], "ゴールド24")
        self.assertNotIn("ハイパーライト", str(kishu_running_path))
        self.assertNotIn("IPS一括型", str(kishu_running_path))

        # 機種変更ではライト不可
        kishu_light = deepcopy(self.request)
        kishu_light.update({
            "sales_type": "機種変更・移動機物品販売",
            "plan_id": "light",
            "data_plan": "20GB",
        })
        with self.assertRaisesRegex(ValueError, "機種変更では"):
            build_quote(
                kishu_light, self.device_master, self.plan_master, self.service_master
            )
        # MNPではライト可（割引 -500）
        mnp_light = deepcopy(self.request)
        mnp_light.update({"plan_id": "light", "data_plan": "20GB"})
        light_quote = build_quote(
            mnp_light, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(light_quote["components"]["additional_discount_tax_ex"], -500)
        self.assertEqual(light_quote["components"]["additional_discount_name"], "ライト割")
        self.assertEqual(light_quote["services"]["support"]["plan_id"], "support_xs")

    def test_kishu_henko_pdf_heading_short(self):
        import pdfplumber
        from tempfile import TemporaryDirectory
        from quote_system.pdf_renderer import render_quote

        request = deepcopy(self.request)
        request["sales_type"] = "機種変更・移動機物品販売"
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        company = {
            "name": "Test Co",
            "department": "TM事業本部",
            "registration_number": "G1901279",
            "postal_address": "本社",
            "phone": "000-0000-0000",
            "fax": "",
            "logo_file": "assets/company_logo.png",
        }
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "kishu.pdf"
            render_quote(quote, company, output)
            with pdfplumber.open(output) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("機種変更お見積り", text)
        self.assertNotIn("移動機物品販売", text)

    def test_special_initial_fee_mode(self):
        request = deepcopy(self.request)
        request["initial_fee_mode"] = "special_3000"
        request["services"] = {
            "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
            "support_plan_id": None,
        }
        request["plan_id"] = "biz_plus"
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(quote["initial_fee_tax_ex"], 0)
        self.assertEqual(quote["special_initial_fee_tax_ex"], 3000)
        # IPS一括（税抜）+ 初期費用3000
        ips_tax_ex = round(quote["services"]["ips"]["upfront_total_tax_in"] / 1.1)
        self.assertEqual(quote["initial_total_tax_ex"], 3000 + ips_tax_ex)

    def test_full_pattern_variant_count_for_selected_models(self):
        device = find_device(self.device_master, "iPhone 17 256GB")
        variants = list(quote_variants(
            device, self.plan_master,
            include_upfront_ips=True, include_no_ips=True, include_no_support=True,
            include_standard_initial_fee=True,
        ))
        # 初期費用 special_3000 + standard。一括型は lump / monthly_as_running の2版
        self.assertEqual(len(variants), 3556)
        self.assertEqual(
            {item["initial_fee_mode"] for item in variants},
            {"standard", "special_3000"},
        )
        self.assertFalse(any(
            item["data_plan"] == "5GB" and item["ouchi_discount_applied"]
            for item in variants
        ))

        feature = find_device(self.device_master, "DIGNOケータイ4")
        feature_variants = list(quote_variants(
            feature, self.plan_master,
            include_upfront_ips=True, include_no_ips=True, include_no_support=True,
            include_standard_initial_fee=True,
        ))
        self.assertEqual(len(feature_variants), 48)

    def test_quote_output_root_constant(self):
        from quote_system.batch_service import QUOTE_OUTPUT_ROOT
        from quote_system.config import OUTPUT_DIR
        self.assertEqual(QUOTE_OUTPUT_ROOT, OUTPUT_DIR / "見積PDF")

    def test_excluded_model_keys_roundtrip(self):
        from quote_system.batch_service import (
            EXCLUDED_MODELS_PATH,
            load_excluded_model_keys,
            save_excluded_model_keys,
        )
        previous = load_excluded_model_keys()
        existed = EXCLUDED_MODELS_PATH.exists()
        try:
            save_excluded_model_keys(["demo_key_a", "demo_key_b"])
            self.assertEqual(load_excluded_model_keys(), {"demo_key_a", "demo_key_b"})
        finally:
            if existed:
                save_excluded_model_keys(previous)
            elif EXCLUDED_MODELS_PATH.exists():
                EXCLUDED_MODELS_PATH.unlink()

    def test_running_mode_omits_ips_from_initial_total(self):
        request = deepcopy(self.request)
        request["initial_fee_mode"] = "special_3000"
        request["ips_display_mode"] = "monthly_as_running"
        request["services"] = {
            "ips": {"type": "upfront", "plan_id": "ips_gold_24"},
            "support_plan_id": None,
        }
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        self.assertEqual(
            quote["initial_total_tax_in"],
            quote["special_initial_fee_tax_in"],
        )
        self.assertEqual(quote["ips_display_mode"], "monthly_as_running")

    def test_worst_case_quote_pdf_fits_one_page(self):
        import pdfplumber
        from tempfile import TemporaryDirectory
        from quote_system.pdf_renderer import render_quote

        request = deepcopy(self.request)
        request.update({
            "model": "13インチiPad Pro（M5）Wi-Fi+Cellular(256GB)",
            "plan_id": "hyper_light",
            "data_plan": "無制限",
            "ouchi_discount_applied": True,
            "initial_fee_mode": "special_3000",
            "ips_display_mode": "monthly_as_running",
            "services": {
                "ips": {"type": "upfront", "plan_id": "ips_platinum_36_water"},
                "support_plan_id": "auto",
            },
        })
        quote = build_quote(
            request, self.device_master, self.plan_master, self.service_master
        )
        company = load_json(DATA_DIR / "company.json")
        company = {**company, "department": "TM事業本部"}
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "worst.pdf"
            render_quote(quote, company, output)
            with pdfplumber.open(output) as pdf:
                self.assertEqual(len(pdf.pages), 1)
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            self.assertNotIn("携帯電話料金小計", text)
            self.assertNotIn("通信料金小計", text)
            self.assertIn("修理保証サービス", text)
            self.assertIn("安心保証サービス", text)
            self.assertIn("No.", text)
            self.assertIn("月額合計", text)
            # 並び: 機種代金 → 修理保証 → 安心保証 → ユニバーサル → 月額合計
            device_pos = text.find("機種代金")
            ips_pos = text.find("修理保証サービス")
            support_pos = text.find("安心保証サービス")
            uni = text.find("ユニバーサルサービス料")
            total_pos = text.find("月額合計")
            self.assertTrue(
                0 <= device_pos < ips_pos < support_pos < uni < total_pos
            )
            self.assertIn("MNPお見積り", text)  # worst case uses test request sales_type

    def test_attention_notes_conditions(self):
        from quote_system.pdf_renderer import _attention_notes

        with_ips = _attention_notes(
            {
                "model": "iPhone 17(256GB)",
                "services": {"ips": {"billing_type": "subscription"}},
            },
            ips=True,
            support=True,
        )
        self.assertTrue(any("修理保証サービスへの加入が必要" in note for note in with_ips))
        self.assertTrue(any("携帯電話有料保証について" in note for note in with_ips))
        self.assertTrue(any("携帯電話機安心サポートについて" in note for note in with_ips))
        self.assertTrue(any("クレジットカードまたは口座振替" in note for note in with_ips))
        self.assertTrue(any("USB-C充電ケーブル" in note for note in with_ips))
        self.assertTrue(any("税込の記載がない限りすべて税抜" in note for note in with_ips))
        self.assertFalse(any("ランニングコスト表記" in note for note in with_ips))
        self.assertFalse(any("おうち割光セットは、対象の光回線" in note for note in with_ips))
        self.assertTrue(
            any(
                "修理保証サービスのサブスクリプション手数料として1請求あたり165円を別途頂戴しております。"
                in note
                for note in with_ips
            )
        )

        no_sub_ips = _attention_notes(
            {
                "model": "iPhone 17(256GB)",
                "services": {"ips": {"billing_type": "upfront", "upfront_total_tax_in": 1000}},
            },
            ips=True,
            support=False,
        )
        self.assertFalse(
            any("サブスクリプション手数料として" in note for note in no_sub_ips)
        )

        with_ouchi = _attention_notes(
            {"model": "Xperia 1 VII", "ouchi_discount_applied": True},
            ips=False,
            support=True,
        )
        self.assertTrue(any("おうち割光セットは、対象の光回線" in note for note in with_ouchi))

        running = _attention_notes(
            {
                "model": "iPhone 17(256GB)",
                "ips_display_mode": "monthly_as_running",
                "services": {
                    "ips": {
                        "billing_type": "upfront",
                        "upfront_total_tax_in": 40392,
                        "period_months": 24,
                    }
                },
            },
            ips=True,
            support=True,
        )
        self.assertTrue(any("ランニングコスト表記" in note for note in running))
        self.assertTrue(any("保証期間は契約から24か月" in note for note in running))
        self.assertTrue(
            any(
                "実際は契約時に一括で¥40,392（税込）のお支払いがあります。" in note
                for note in running
            )
        )

        no_ips = _attention_notes({"model": "Xperia 1 VII"}, ips=False, support=True)
        self.assertFalse(any("修理保証サービスへの加入が必要" in note for note in no_ips))
        self.assertFalse(any("携帯電話有料保証について" in note for note in no_ips))
        self.assertTrue(any("携帯電話機安心サポートについて" in note for note in no_ips))
        self.assertFalse(any("USB-C充電ケーブル" in note for note in no_ips))

    def test_price_diff_detection(self):
        updated = deepcopy(self.device_master)
        device = find_device(updated, "iPhone 17 256GB")
        device["payment_48"]["MNP"]["1_12"] = 2
        changed = changed_model_keys(self.device_master, updated)
        self.assertEqual(changed, {device["model_key"]})

    def test_individual_ips_variant_selection(self):
        from quote_system.batch_service import (
            _individual_ips_variants,
            _upfront_ips_plan_ids,
        )

        device = find_device(self.device_master, "iPhone 17 256GB")
        only_sub = _individual_ips_variants(
            device,
            include_ips_subscription=True,
            include_upfront_lump=False,
            include_upfront_running=False,
            include_no_ips=False,
        )
        self.assertEqual(only_sub, [({"type": "subscription"}, "lump")])

        lump_and_running = _individual_ips_variants(
            device,
            include_ips_subscription=False,
            include_upfront_lump=True,
            include_upfront_running=True,
            include_no_ips=False,
        )
        plan_ids = _upfront_ips_plan_ids(device)
        self.assertEqual(len(lump_and_running), len(plan_ids) * 2)
        self.assertTrue(all(item[0]["type"] == "upfront" for item in lump_and_running))
        self.assertEqual(
            {item[1] for item in lump_and_running},
            {"lump", "monthly_as_running"},
        )

        empty = _individual_ips_variants(
            device,
            include_ips_subscription=False,
            include_upfront_lump=False,
            include_upfront_running=False,
            include_no_ips=False,
        )
        self.assertEqual(empty, [])

    def test_run_individual_ips_patterns(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from quote_system.batch_service import run_individual

        common = dict(
            model="iPhone 17 256GB",
            sales_type="MNP",
            plan_id="biz_plus",
            data_plans=["50GB"],
            ouchi_options=[False],
            support_plan_id="auto",
            department="TM事業本部",
        )

        with self.assertRaises(ValueError):
            run_individual(
                **common,
                include_ips_subscription=False,
                include_upfront_lump=False,
                include_upfront_running=False,
                include_no_ips=False,
            )

        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT", out):
                result = run_individual(
                    **common,
                    include_ips_subscription=True,
                    include_upfront_lump=False,
                    include_upfront_running=False,
                    include_no_ips=False,
                )
            self.assertEqual(result.generated_files, 1)
            pdfs = list(out.rglob("*.pdf"))
            self.assertEqual(len(pdfs), 1)
            self.assertTrue(any("IPSサブスク" in p.parts for p in pdfs))

        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT", out):
                result = run_individual(
                    **common,
                    include_ips_subscription=False,
                    include_upfront_lump=True,
                    include_upfront_running=True,
                    include_no_ips=False,
                )
            from quote_system.batch_service import _upfront_ips_plan_ids

            device = find_device(self.device_master, "iPhone 17 256GB")
            expected = len(_upfront_ips_plan_ids(device)) * 2
            self.assertEqual(result.generated_files, expected)
            all_parts = {part for p in out.rglob("*.pdf") for part in p.parts}
            self.assertIn("IPS一括型", all_parts)
            self.assertIn("IPS一括型_月額換算", all_parts)

    def test_run_individual_pdf_content_and_merged_paths(self):
        """個別見積: 実PDF生成・1ページ・部署FAX・スーパー統合パスを検算。"""
        import re
        import pdfplumber
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from quote_system.batch_service import run_individual

        # サブスク＋ハイパー（MNP）→ IPSあり/IPSサブスク
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT", out):
                result = run_individual(
                    model="iPhone 17 256GB",
                    sales_type="MNP",
                    plan_id="hyper_light",
                    data_plans=["5GB"],
                    ouchi_options=[False],
                    include_ips_subscription=True,
                    include_upfront_lump=False,
                    include_upfront_running=False,
                    include_no_ips=False,
                    support_plan_id="auto",
                    department="RT事業部",
                )
            self.assertEqual(result.generated_files, 1)
            pdfs = list(out.rglob("*.pdf"))
            self.assertEqual(len(pdfs), 1)
            pdf = pdfs[0]
            self.assertEqual(
                pdf.parts[-4:],
                ("SB光なし", "IPSあり", "IPSサブスク", "iPhone17(256GB)_5GB.pdf"),
            )
            with pdfplumber.open(pdf) as doc:
                self.assertEqual(len(doc.pages), 1)
                text = "\n".join(page.extract_text() or "" for page in doc.pages)
            self.assertIn("RT事業部", text)
            self.assertIn("MNPお見積り", text)
            # company.json の RT に FAX があれば表記（ローカル専用マスタ）
            company = load_json(DATA_DIR / "company.json")
            rt_fax = str(
                (company.get("department_contacts") or {})
                .get("RT事業部", {})
                .get("fax")
                or ""
            ).strip()
            if rt_fax:
                self.assertRegex(text, rf"FAX：\s*{re.escape(rt_fax)}")
            else:
                self.assertNotIn("FAX：", text)

        # 機種変更×スーパー＋通常IPS両方表記 → IPSあり配下の表記フォルダ
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT", out):
                result = run_individual(
                    model="iPhone 17 256GB",
                    sales_type="機種変更・移動機物品販売",
                    plan_id="super_light",
                    data_plans=["50GB"],
                    ouchi_options=[False],
                    include_ips_subscription=True,
                    include_upfront_lump=True,
                    include_upfront_running=True,
                    include_no_ips=False,
                    support_plan_id="auto",
                    department="RT事業部",
                )
            pdfs = list(out.rglob("*.pdf"))
            self.assertEqual(result.generated_files, len(pdfs))
            self.assertGreaterEqual(result.generated_files, 3)
            parts_sets = [set(p.parts) for p in pdfs]
            self.assertTrue(any("IPSサブスク" in s and "IPSあり" in s for s in parts_sets))
            self.assertTrue(any("IPS一括表記" in s and "IPSあり" in s for s in parts_sets))
            self.assertTrue(
                any("通常IPSランニングコスト表記" in s and "IPSあり" in s for s in parts_sets)
            )
            self.assertFalse(any("Bizパッケージ" in str(p) for p in pdfs))
            for pdf in pdfs[:3]:
                with pdfplumber.open(pdf) as doc:
                    self.assertEqual(len(doc.pages), 1, msg=str(pdf))
                    text = doc.pages[0].extract_text() or ""
                self.assertIn("機種変更お見積り", text)
                self.assertIn("RT事業部", text)

        # 機種変更でライトは拒否
        with self.assertRaisesRegex(ValueError, "機種変更では"):
            run_individual(
                model="iPhone 17 256GB",
                sales_type="機種変更・移動機物品販売",
                plan_id="light",
                data_plans=["20GB"],
                ouchi_options=[False],
                include_ips_subscription=True,
            )

    def test_batch_checkpoint_pause_and_resume(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from quote_system.batch_service import (
            BatchControl,
            CHECKPOINT_PATH,
            _generate_for_devices,
            checkpoint_exists,
            clear_checkpoint,
            resume_batch,
        )

        device = find_device(self.device_master, "iPhone 17 256GB")
        company = load_json(DATA_DIR / "company.json")
        clear_checkpoint()
        control = BatchControl()
        # 3件目に入る直前で止める
        call_count = {"n": 0}

        def fake_render(quote, company_arg, output_path):
            call_count["n"] += 1
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"%PDF-1.4")
            if call_count["n"] >= 2:
                control.request_cancel()

        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("quote_system.batch_service.QUOTE_OUTPUT_ROOT", out), patch(
                "quote_system.batch_service.render_quote", side_effect=fake_render
            ), patch(
                "quote_system.batch_service.CHECKPOINT_PATH", Path(tmp) / "cp.json"
            ):
                # re-import path for clear uses CHECKPOINT_PATH module level - patch where used
                import quote_system.batch_service as bs

                old_cp = bs.CHECKPOINT_PATH
                bs.CHECKPOINT_PATH = Path(tmp) / "cp.json"
                try:
                    paused = _generate_for_devices(
                        [device],
                        device_master=self.device_master,
                        plan_master=self.plan_master,
                        service_master=self.service_master,
                        company=company,
                        mode="checkpoint-test",
                        source_pdf=Path("test.pdf"),
                        source_hash="x",
                        discontinued=(),
                        include_upfront_ips=False,
                        include_no_ips=False,
                        include_no_support=False,
                        include_standard_initial_fee=False,
                        progress=None,
                        update_state=False,
                        control=control,
                    )
                    self.assertTrue(paused.paused)
                    self.assertTrue(bs.checkpoint_exists())
                    self.assertEqual(paused.generated_files, 2)

                    resumed_control = BatchControl()
                    call_count["n"] = 0  # allow more without canceling early

                    def fake_render_resume(quote, company_arg, output_path):
                        call_count["n"] += 1
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(b"%PDF-1.4")

                    with patch(
                        "quote_system.batch_service.render_quote",
                        side_effect=fake_render_resume,
                    ):
                        done = resume_batch(control=resumed_control)
                    self.assertFalse(done.paused)
                    self.assertGreater(done.generated_files, 2)
                    self.assertFalse(bs.checkpoint_exists())
                finally:
                    bs.CHECKPOINT_PATH = old_cp
                    clear_checkpoint()


if __name__ == "__main__":
    unittest.main()
