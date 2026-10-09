"""Trial UI builds, and desktop_app.py is not rewritten."""

import unittest
from pathlib import Path

import tkinter as tk


class UiPreviewTest(unittest.TestCase):
    def test_preview_builds_and_keeps_the_same_switches(self) -> None:
        from ui_preview import PreviewQuoteApp

        app = PreviewQuoteApp()
        try:
            app.update_idletasks()
            app.update()
            self.assertIn("\u8a66\u9a13UI", app.title())
            self.assertGreater(app._scroll_inner.winfo_reqheight(), 400)
            self.assertIsInstance(app.log, tk.Text)
            self.assertIsNotNone(app.run_button)
            self.assertIsNotNone(app.progress)
            app.force_all_var.set(False)
            self.assertFalse(app.force_all_var.get())
            app.upfront_mode_var.set("monthly_as_running")
            self.assertEqual(app.upfront_mode_var.get(), "monthly_as_running")
            app.progress.configure(maximum=10, value=4)
            app.run_button.configure(state="disabled")
            app.run_button.configure(state="normal")
            app._toggle_details()
            self.assertTrue(app._details_open)
            self.assertIn("\u9589\u3058\u308b", app._chevron.get())
            app._toggle_details()
            self.assertFalse(app._details_open)
            app._write_log("trial-log")
            app.pdf_var.set("")
            app._sync_drop()
            self.assertIn("\u30c9\u30ed\u30c3\u30d7", app.drop_title.get())
            app._on_files_dropped(["C:/temp/not-a-pdf.txt"])
            app._on_files_dropped([r"C:\price\sample.pdf"])
            self.assertTrue(app.pdf_var.get().lower().endswith(".pdf"))
            self.assertIn("sample.pdf", app.drop_title.get())
            app._file_drop.install()
            app.update()
            app.individual_button.configure(state="disabled")
            app.individual_button.configure(state="normal")
            app.geometry("1000x820")
            app.update()
        finally:
            app.destroy()

    def test_switch_button_carries_selections_both_ways(self) -> None:
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        import desktop_app
        from ui_preview import PreviewQuoteApp

        with TemporaryDirectory() as tmp:
            mode_path = Path(tmp) / "ui_mode.json"
            with patch.object(desktop_app, "UI_MODE_PATH", mode_path):
                self.assertEqual(desktop_app.load_ui_mode(), desktop_app.UI_CLASSIC)

                classic = desktop_app.QuoteApp()
                classic.update()
                self.assertIsNotNone(classic.switch_ui_button)
                classic.pdf_var.set(r"C:\price\sample.pdf")
                classic.light_plan_var.set(True)
                classic.force_all_var.set(False)
                classic._write_log("carry-this-log")
                classic._switch_ui()
                self.assertEqual(classic.switch_to, desktop_app.UI_PREVIEW)
                self.assertEqual(desktop_app.load_ui_mode(), desktop_app.UI_PREVIEW)
                snapshot = classic.ui_snapshot

                preview = desktop_app._create_app(desktop_app.UI_PREVIEW, snapshot)
                try:
                    preview.update()
                    self.assertIsInstance(preview, PreviewQuoteApp)
                    self.assertEqual(preview.pdf_var.get(), r"C:\price\sample.pdf")
                    self.assertTrue(preview.light_plan_var.get())
                    self.assertFalse(preview.force_all_var.get())
                    self.assertIn("carry-this-log", preview.log.get("1.0", "end"))
                    preview._is_running = True
                    with patch.object(desktop_app.messagebox, "showinfo"):
                        preview._switch_ui()
                    self.assertIsNone(preview.switch_to)
                    preview._is_running = False
                    preview._switch_ui()
                    self.assertEqual(preview.switch_to, desktop_app.UI_CLASSIC)
                    self.assertEqual(desktop_app.load_ui_mode(), desktop_app.UI_CLASSIC)
                finally:
                    if preview.switch_to is None:
                        preview.destroy()
