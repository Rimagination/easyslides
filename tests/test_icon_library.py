import tempfile
import unittest
from pathlib import Path


class IconLibraryTests(unittest.TestCase):
    def test_local_icon_families_are_productized(self):
        from scripts.icon_library import load_icon_library, validate_icon_library

        library = load_icon_library()
        report = validate_icon_library(library)

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(library["family_count"], 6)
        self.assertEqual(library["icon_count"], 11634)
        lucide = next(family for family in library["families"] if family["family"] == "lucide")
        self.assertEqual(lucide["count"], 3)
        self.assertEqual(lucide["role"], "stylistic")

    def test_search_supports_exact_and_semantic_aliases(self):
        from scripts.icon_library import search_icons

        exact = search_icons("calendar", family="lucide", limit=5)
        semantic = search_icons("environment", family="tabler-outline", limit=10)

        self.assertEqual([row["token"] for row in exact], ["lucide/calendar-days"])
        self.assertTrue(semantic)
        self.assertTrue(any(row["name"] in {"leaf", "tree", "plant", "recycle", "droplet", "water", "wind", "earth", "sun", "cloud"} for row in semantic))

    def test_sync_copies_project_assets_and_blocks_mixed_styles(self):
        from scripts.icon_library import sync_icons

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            copied = sync_icons(project, ["tabler-outline/home", "simple-icons/github"])
            mixed = sync_icons(project, ["tabler-outline/home", "phosphor-duotone/airplane"])

            self.assertEqual(copied["status"], "pass", copied)
            self.assertTrue((project / "icons/tabler-outline/home.svg").is_file())
            self.assertTrue((project / "icons/simple-icons/github.svg").is_file())
            self.assertEqual(mixed["status"], "fail")
            self.assertEqual(mixed["violations"][0]["code"], "ICON-STYLE-MIX")

    def test_icon_payload_must_match_registered_family(self):
        from scripts.icon_library import validate_icon_payload

        valid = validate_icon_payload("lucide", {"icon_name": "lucide/calendar-days"})
        invalid = validate_icon_payload("lucide", {"icon_name": "tabler-outline/home"})

        self.assertTrue(valid["passed"])
        self.assertFalse(invalid["passed"])
        self.assertEqual(invalid["violations"][0]["code"], "ICON-PAYLOAD-FAMILY")


if __name__ == "__main__":
    unittest.main()
