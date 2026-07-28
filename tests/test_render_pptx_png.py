import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RenderPptxPngTests(unittest.TestCase):
    def test_render_pptx_to_png_uses_soffice_then_pdftoppm(self):
        from scripts.render_pptx_png import render_pptx_to_png

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pptx = root / "demo.pptx"
            out_dir = root / "renders"
            pptx.write_bytes(b"fake pptx")
            calls: list[list[str]] = []

            def fake_runner(command, **kwargs):
                calls.append([str(item) for item in command])
                if "--convert-to" in command:
                    output_dir = Path(command[command.index("--outdir") + 1])
                    (output_dir / "demo.pdf").write_bytes(b"%PDF-1.7")
                elif command[0] == "pdftoppm":
                    prefix = Path(command[-1])
                    prefix.parent.mkdir(parents=True, exist_ok=True)
                    Path(f"{prefix}-1.png").write_bytes(b"png")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            report = render_pptx_to_png(
                pptx,
                out_dir,
                dpi=120,
                runner=fake_runner,
                soffice_executable="soffice",
                pdftoppm_executable="pdftoppm",
            )

        self.assertEqual(report["schema_version"], "easyslides.pptx_render_png_report.v1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["renderer"], "pdftoppm")
        self.assertEqual(report["slide_count"], 1)
        self.assertEqual(report["files"], ["slide_001.png"])
        self.assertIn("--convert-to", calls[0])
        self.assertEqual(calls[1][0], "pdftoppm")
        self.assertIn("-r", calls[1])
        self.assertIn("120", calls[1])

    def test_auto_prefers_powerpoint_when_available(self):
        from scripts import render_pptx_png

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pptx = root / "demo.pptx"
            out_dir = root / "renders"
            pptx.write_bytes(b"fake pptx")
            calls: list[list[str]] = []

            def fake_runner(command, **kwargs):
                calls.append([str(item) for item in command])
                output_dir = Path(command[command.index("-OutputDir") + 1])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "Slide1.PNG").write_bytes(b"png")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with patch.object(render_pptx_png, "_find_powerpoint_executable", return_value="POWERPNT.EXE"), patch.object(
                render_pptx_png, "_find_powershell_executable", return_value="powershell.exe"
            ):
                report = render_pptx_png.render_pptx_to_png(
                    pptx,
                    out_dir,
                    dpi=144,
                    runner=fake_runner,
                )

        self.assertEqual(report["backend"], "powerpoint")
        self.assertEqual(report["renderer"], "powerpoint")
        self.assertEqual(report["files"], ["slide_001.png"])
        self.assertEqual(len(calls), 1)
        self.assertIn("render_powerpoint.ps1", calls[0][calls[0].index("-File") + 1])
        self.assertIn("144", calls[0])

    def test_auto_fallback_clears_partial_powerpoint_output(self):
        from scripts import render_pptx_png

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pptx = root / "demo.pptx"
            out_dir = root / "renders"
            pptx.write_bytes(b"fake pptx")

            def fake_runner(command, **kwargs):
                if "-File" in command:
                    output_dir = Path(command[command.index("-OutputDir") + 1])
                    output_dir.mkdir(parents=True, exist_ok=True)
                    (output_dir / "Slide1.PNG").write_bytes(b"partial-powerpoint")
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="COM failed")
                if "--convert-to" in command:
                    output_dir = Path(command[command.index("--outdir") + 1])
                    (output_dir / "demo.pdf").write_bytes(b"%PDF-1.7")
                elif command[0] == "pdftoppm":
                    prefix = Path(command[-1])
                    prefix.parent.mkdir(parents=True, exist_ok=True)
                    Path(f"{prefix}-1.png").write_bytes(b"fallback")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with patch.object(render_pptx_png, "_find_powerpoint_executable", return_value="POWERPNT.EXE"), patch.object(
                render_pptx_png, "_find_powershell_executable", return_value="powershell.exe"
            ), patch.object(render_pptx_png, "_find_soffice_executable", return_value="soffice"):
                report = render_pptx_png.render_pptx_to_png(
                    pptx,
                    out_dir,
                    runner=fake_runner,
                    pdftoppm_executable="pdftoppm",
                )
            rendered_bytes = (out_dir / "slide_001.png").read_bytes()

        self.assertEqual(report["backend"], "soffice")
        self.assertEqual(report["renderer"], "pdftoppm")
        self.assertEqual(report["files"], ["slide_001.png"])
        self.assertEqual(rendered_bytes, b"fallback")


if __name__ == "__main__":
    unittest.main()
