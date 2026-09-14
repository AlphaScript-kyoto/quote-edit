from __future__ import annotations

import unittest

from quote_system.batch_service import load_device_master, load_included_model_keys
from quote_system.config import DATA_DIR, load_json
from quote_system.price_pdf_parser import find_device
from quote_system.quote_service import build_quote
from quote_system.temporary_devices import (
    merge_temporary_devices,
    temporary_devices_enabled,
    temporary_model_keys,
)


class TemporaryDevicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan_master = load_json(DATA_DIR / "plans.json")
        cls.service_master = load_json(DATA_DIR / "services.json")

    def test_temporary_overlay_enabled_and_keys(self) -> None:
        self.assertTrue(temporary_devices_enabled())
        keys = temporary_model_keys()
        self.assertIn("iphone18pro256gb", keys)
        self.assertIn("iphone18promax512gb", keys)
        self.assertEqual(len(keys), 8)

    def test_merge_and_include_list_force(self) -> None:
        base = {"schema_version": 1, "devices": []}
        merged = merge_temporary_devices(base)
        self.assertEqual(
            sum(1 for d in merged["devices"] if d["model_key"].startswith("iphone18")),
            8,
        )
        included = load_included_model_keys(merged)
        self.assertTrue(temporary_model_keys() <= included)

    def test_build_quote_iphone18_pro_mnp(self) -> None:
        master = load_device_master()
        device = find_device(master, "iPhone 18 Pro(256GB)")
        self.assertEqual(device["total"], 268560)
        self.assertEqual(device["payment_48"]["MNP"]["1_12"], 2365)
        self.assertEqual(device["payment_48"]["MNP"]["13_24"], 2365)
        self.assertEqual(device["payment_48"]["MNP"]["25_48"], 8825)
        quote = build_quote(
            {
                "quote_id": "TMP-I18P-256-MNP",
                "model": "iPhone 18 Pro(256GB)",
                "sales_type": "MNP",
                "plan_id": "biz_plus",
                "data_plan": "20GB",
                "ouchi_discount": False,
                "ips_id": None,
                "support_plan_id": None,
                "initial_fee_mode": "special_3000",
            },
            master,
            self.plan_master,
            self.service_master,
        )
        self.assertEqual(quote["device_total_tax_in"], 268560)
        self.assertEqual(quote["model"], "iPhone 18 Pro(256GB)")

    def test_pro_max_naming(self) -> None:
        master = load_device_master()
        device = find_device(master, "iPhone 18 Pro Max(1TB)")
        self.assertEqual(device["category"], "iPhone")
        self.assertEqual(device["payment_24"], None)


if __name__ == "__main__":
    unittest.main()
