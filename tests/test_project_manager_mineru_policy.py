import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ProjectManagerMinerUPolicyTests(unittest.TestCase):
    def test_pdf_import_uses_pdffigures2_when_mineru_fails_in_structured_mode(self):
        from scripts.project_manager import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = project / "sources"
            sources.mkdir()
            pdf = sources / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            markdown = sources / "paper.md"

            manager = ProjectManager()
            pdffigures_dir = sources / "paper_pdffigures2" / "figures"
            pdffigures_dir.mkdir(parents=True)
            (pdffigures_dir / "fig1.png").write_bytes(b"figure")
            pdffigures_md = sources / "paper_pdffigures2.md"
            pdffigures_md.write_text("# PDFFigures2\n\n![Figure 1](paper_pdffigures2/figures/fig1.png)\n", encoding="utf-8")
            pdffigures_result = {
                "markdown_path": str(pdffigures_md),
                "figures_dir": str(pdffigures_dir),
                "method": "pdffigures2",
            }

            with (
                mock.patch("source_to_md.mineru_preprocess.extract_pdf", side_effect=RuntimeError("mineru down")),
                mock.patch("source_to_md.pdffigures2_preprocess.extract_pdf", return_value=pdffigures_result),
                mock.patch.object(manager, "_run_tool") as fallback,
            ):
                manager._import_pdf(pdf, markdown, require_structured_pdf=True)

            self.assertEqual(markdown.read_text(encoding="utf-8"), pdffigures_md.read_text(encoding="utf-8"))
            self.assertTrue((project / "images" / "fig1.png").exists())
            fallback.assert_not_called()

    def test_pdf_import_fails_fast_when_structured_extractors_fail(self):
        from scripts.project_manager import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            sources = project / "sources"
            sources.mkdir()
            pdf = sources / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            markdown = sources / "paper.md"

            manager = ProjectManager()
            with (
                mock.patch("source_to_md.mineru_preprocess.extract_pdf", side_effect=RuntimeError("mineru down")),
                mock.patch("source_to_md.pdffigures2_preprocess.extract_pdf", side_effect=RuntimeError("pdffigures2 missing")),
                mock.patch.object(manager, "_run_tool") as fallback,
            ):
                with self.assertRaisesRegex(RuntimeError, "Structured PDF extraction required"):
                    manager._import_pdf(pdf, markdown, require_structured_pdf=True)

            self.assertFalse(markdown.exists())
            fallback.assert_not_called()

    def test_mineru_put_file_preserves_presigned_url_query_and_length(self):
        from scripts.source_to_md import mineru_preprocess

        class FakeResponse:
            status = 204

            def read(self):
                return b""

        class FakeConnection:
            instances = []

            def __init__(self, netloc, timeout):
                self.netloc = netloc
                self.timeout = timeout
                self.request_args = None
                self.closed = False
                FakeConnection.instances.append(self)

            def request(self, method, target, body=None, headers=None):
                self.request_args = {
                    "method": method,
                    "target": target,
                    "body": body,
                    "headers": headers or {},
                }

            def getresponse(self):
                return FakeResponse()

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"pdf-bytes")

            with mock.patch.object(mineru_preprocess.http.client, "HTTPConnection", FakeConnection):
                mineru_preprocess._put_file(path, "http://upload.example.com/bucket/object?signature=abc")

        conn = FakeConnection.instances[0]
        self.assertEqual(conn.netloc, "upload.example.com")
        self.assertEqual(conn.request_args["method"], "PUT")
        self.assertEqual(conn.request_args["target"], "/bucket/object?signature=abc")
        self.assertEqual(conn.request_args["body"], b"pdf-bytes")
        self.assertEqual(conn.request_args["headers"]["Content-Length"], "9")
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
