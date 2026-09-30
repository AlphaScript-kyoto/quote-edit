"""Per-edition config checks (standard / tm_special / agency)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parents[1]

# Japanese literals as escapes so the file stays intact in any editor/encoding.
QUOTE_PDF = "\u898b\u7a4dPDF"  # ??PDF
APP_NAME = "\u898b\u7a4d\u3082\u308a\u4e00\u62ec\u4f5c\u6210"  # ????????
TM_LABEL = "TM\u517c\u4efb\u4e8b\u696d\u90e8\u7528"  # TM??????
AGENCY_LABEL = "\u4ee3\u7406\u5e97\u7528"  # ????
TM_SUFFIX = "_TM\u7279\u4f8b"  # _TM??
AGENCY_SUFFIX = "_\u4ee3\u7406\u5e97"  # _???
KAI = "\u56de"  # ?
RT_DEPT = "RT\u4e8b\u696d\u90e8"  # RT???
TM_DEPT = "TM\u4e8b\u696d\u672c\u90e8"  # TM????
CRM_DEPT = "CRM\u4e8b\u696d\u90e8"  # CRM???
PAREN_OPEN, PAREN_CLOSE = "\uff08", "\uff09"

_PROBE = (
    "import json\n"
    "from quote_system import config as c\n"
    "print(json.dumps({\n"
    "  'edition': c.APP_EDITION,\n"
    "  'special': c.IS_SPECIAL_EDITION,\n"
    "  'tm': c.IS_TM_SPECIAL,\n"
    "  'agency': c.IS_AGENCY,\n"
    "  'forced': c.FORCED_DEPARTMENT,\n"
    "  'title': c.app_window_title(),\n"
    "  'package': c.package_dir_name(),\n"
    "  'out48': c.QUOTE_OUTPUT_DIRNAME,\n"
    "  'out36': c.QUOTE_OUTPUT_DIRNAME_36,\n"
    "  'out24': c.QUOTE_OUTPUT_DIRNAME_24,\n"
    "}, ensure_ascii=True))\n"
)


def _probe(edition: str) -> dict:
    env = {**os.environ, "QUOTE_APP_EDITION": edition}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=SYSTEM_DIR,
        env=env,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout.decode("ascii"))


def _outputs(suffix: str) -> tuple[str, str, str]:
    return (
        f"{QUOTE_PDF}{suffix}",
        f"{QUOTE_PDF}{suffix}_36{KAI}",
        f"{QUOTE_PDF}{suffix}_24{KAI}",
    )


class EditionConfigTests(unittest.TestCase):
    def test_standard_edition(self):
        got = _probe("standard")
        self.assertFalse(got["special"])
        self.assertIsNone(got["forced"])
        self.assertEqual((got["out48"], got["out36"], got["out24"]), _outputs(""))
        self.assertNotIn(PAREN_OPEN, got["title"])

    def test_tm_special_edition_unchanged(self):
        got = _probe("tm_special")
        self.assertTrue(got["special"])
        self.assertTrue(got["tm"])
        self.assertIsNone(got["forced"])
        self.assertIn(f"{PAREN_OPEN}{TM_LABEL}{PAREN_CLOSE}", got["title"])
        self.assertTrue(got["package"].startswith(f"{APP_NAME}_{TM_LABEL}ver"))
        self.assertEqual((got["out48"], got["out36"], got["out24"]), _outputs(TM_SUFFIX))

    def test_agency_edition_same_rules_as_tm_with_rt_fixed(self):
        got = _probe("agency")
        self.assertEqual(got["edition"], "agency")
        self.assertTrue(got["special"])
        self.assertTrue(got["agency"])
        self.assertFalse(got["tm"])
        self.assertEqual(got["forced"], RT_DEPT)
        self.assertIn(f"{PAREN_OPEN}{AGENCY_LABEL}{PAREN_CLOSE}", got["title"])
        self.assertIn("ver.", got["title"])
        self.assertTrue(got["package"].startswith(f"{APP_NAME}_{AGENCY_LABEL}ver"))
        self.assertEqual(
            (got["out48"], got["out36"], got["out24"]), _outputs(AGENCY_SUFFIX)
        )


class ForcedDepartmentTests(unittest.TestCase):
    def test_forced_department_wins_over_selection(self):
        from quote_system.batch_service import resolve_department

        self.assertEqual(resolve_department(TM_DEPT, RT_DEPT), RT_DEPT)
        self.assertEqual(resolve_department(None, RT_DEPT), RT_DEPT)

    def test_without_forced_department_uses_selection(self):
        from quote_system.batch_service import resolve_department

        self.assertEqual(resolve_department(f" {CRM_DEPT} ", None), CRM_DEPT)
        self.assertIsNone(resolve_department("  ", None))


if __name__ == "__main__":
    unittest.main()
