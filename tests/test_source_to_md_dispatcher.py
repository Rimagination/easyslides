import json
import tempfile
import unittest
from pathlib import Path


class SourceToMarkdownDispatcherTests(unittest.TestCase):
    def test_dry_run_routes_multiple_input_kinds(self):
        from scripts.source_to_md.dispatcher import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "paper.pdf"
            docx = root / "brief.docx"
            pdf.write_bytes(b"%PDF-1.4\n")
            docx.write_bytes(b"not-a-real-docx")
            output_dir = root / "out"

            result = main([
                str(pdf),
                str(docx),
                "https://example.com/article",
                "-o",
                str(output_dir),
                "--dry-run",
                "--json",
            ])

        self.assertEqual(result, 0)

    def test_text_file_converts_to_markdown_and_profile(self):
        from scripts.source_to_md.dispatcher import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes.txt"
            output = root / "notes.md"
            source.write_text("hello\n", encoding="utf-8")

            result = main([str(source), "-o", str(output)])

            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "hello\n")
            profile = json.loads(output.with_suffix(".conversion_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["kind"], "text")
            self.assertEqual(profile["status"], "converted")


if __name__ == "__main__":
    unittest.main()
