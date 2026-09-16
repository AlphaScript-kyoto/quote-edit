from __future__ import annotations

import unittest
from pathlib import Path

from quote_system.batch_service import latest_price_pdf, load_device_master
from quote_system.price_pdf_parser import (
    clean_model_name,
    is_mm_route_restricted,
    parse_price_pdf,
)

import desktop_app


class PriceListPolicyTests(unittest.TestCase):
    def test_mm_route_marker_detection(self) -> None:
        self.assertTrue(
            is_mm_route_restricted("Google Pixel 9 Pro(512GB) ※MM販路取扱不可")
        )
        self.assertTrue(
            is_mm_route_restricted({"model": "AQUOS R9 pro ※mm販路取扱不可", "notes": ""})
        )
        self.assertFalse(is_mm_route_restricted("iPhone 17(256GB)"))

    def test_clean_model_name_strips_list_annotations(self) -> None:
        self.assertEqual(
            clean_model_name("iPhone 18 Pro(256GB) 9/18発売"),
            "iPhone 18 Pro(256GB)",
        )
        self.assertEqual(
            clean_model_name("iPhone 18 Pro Max(1TB) 9/18発売"),
            "iPhone 18 Pro Max(1TB)",
        )
        self.assertEqual(clean_model_name("iPhone 17(256GB)"), "iPhone 17(256GB)")

    def test_parse_skips_mm_route_devices(self) -> None:
        pdf = latest_price_pdf()
        if pdf is None or not pdf.exists():
            self.skipTest("price PDF not present")
        master = parse_price_pdf(pdf)
        mm = [
            device["model"]
            for device in master["devices"]
            if is_mm_route_restricted(device)
        ]
        self.assertEqual(mm, [])
        self.assertFalse(
            any("MM販路" in str(device.get("model") or "") for device in master["devices"])
        )

    def test_picker_sections_follow_pdf_order(self) -> None:
        pdf = latest_price_pdf()
        if pdf is None or not pdf.exists():
            self.skipTest("price PDF not present")
        master = parse_price_pdf(pdf)
        on_sale = [
            device
            for device in master["devices"]
            if device.get("status") == "販売中" and not is_mm_route_restricted(device)
        ]
        sections = desktop_app.QuoteApp._device_picker_sections(on_sale)
        self.assertTrue(sections)
        self.assertEqual(sections[0][0], "iPhone")
        iphone_models = [device["model"] for device in sections[0][1]]
        self.assertTrue(iphone_models)
        self.assertIn("iPhone 18 Pro", iphone_models[0])
        self.assertNotIn("発売", iphone_models[0])
        self.assertTrue(all(not device.get("notes") for device in master["devices"][:20]))
        # First iPhone block in the 2026.9.17 list is Pro capacities then Pro Max.
        self.assertTrue(any("Pro Max" in model for model in iphone_models[:12]))
        flattened = [device["model"] for _label, group, _open in sections for device in group]
        expected = [device["model"] for device in on_sale]
        self.assertEqual(flattened, expected)

    def test_load_device_master_has_no_temporary_overlay(self) -> None:
        master = load_device_master({"schema_version": 1, "devices": []})
        self.assertFalse(master.get("temporary_devices"))
        self.assertEqual(master.get("devices"), [])


if __name__ == "__main__":
    unittest.main()
