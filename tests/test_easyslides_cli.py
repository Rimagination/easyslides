import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class EasySlidesCliTests(unittest.TestCase):
    def test_help_is_printable_and_lists_product_commands(self):
        result = run_cli("scripts/easyslides.py", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EasySlides command hub", result.stdout)
        self.assertIn("source-to-md", result.stdout)
        self.assertIn("distill", result.stdout)
        self.assertIn("semantic-render", result.stdout)
        self.assertIn("template-gate", result.stdout)
        self.assertIn("template-fill", result.stdout)
        self.assertIn("beautify", result.stdout)
        self.assertIn("clarify", result.stdout)
        self.assertIn("component", result.stdout)
        self.assertIn("chart", result.stdout)
        self.assertIn("icon", result.stdout)
        self.assertIn("logo", result.stdout)
        self.assertIn("powerpoint-demo", result.stdout)

    def test_powerpoint_demo_help_lists_playback_and_recording_options(self):
        result = run_cli("scripts/easyslides.py", "powerpoint-demo", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--slide", result.stdout)
        self.assertIn("--delay", result.stdout)
        self.assertIn("--record", result.stdout)
        self.assertIn("--per-element", result.stdout)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
    def test_replay_video_speed_preserves_video_frames_and_retimes_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "recording.mp4"
            output = Path(tmp) / "recording 2x.mp4"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                 "-f", "lavfi", "-i", "sine=f=440:d=1", "-c:v", "mpeg4", "-c:a", "aac", str(source)],
                check=True,
            )
            original = source.read_bytes()
            result = run_cli(
                "scripts/easyslides.py", "replay-video", "edit", str(source),
                "--out", str(output), "--speed", "2",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(source.read_bytes(), original)
            probe = json.loads(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)],
            ))
            video, audio = probe["streams"]
            self.assertEqual(int(video["nb_frames"]), 10)
            self.assertAlmostEqual(float(video["duration"]), 0.5, places=3)
            self.assertAlmostEqual(float(audio["duration"]), 0.5, places=2)

    def test_logo_help_delegates_to_institution_resource(self):
        result = run_cli("scripts/easyslides.py", "logo", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("explicitly identified user institution", result.stdout)
        self.assertIn("--institution", result.stdout)

    def test_component_pack_help_delegates_to_pack_manager(self):
        result = run_cli("scripts/easyslides.py", "component", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("declarative EasySlides component packs", result.stdout)

    def test_chart_help_delegates_to_chart_library(self):
        result = run_cli("scripts/easyslides.py", "chart", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Inspect the EasySlides chart asset library", result.stdout)

    def test_icon_help_delegates_to_icon_library(self):
        result = run_cli("scripts/easyslides.py", "icon", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Inspect, search, validate, and sync EasySlides icon assets", result.stdout)

    def test_source_to_md_help_delegates_to_dispatcher(self):
        result = run_cli("scripts/easyslides.py", "source-to-md", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Convert files, directories, or URLs to Markdown", result.stdout)

    def test_distill_help_delegates_to_fail_closed_distiller(self):
        result = run_cli("scripts/easyslides.py", "distill", "--help")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Distill a source PPTX", result.stdout)
        self.assertIn("--promote-assets", result.stdout)

    def test_semantic_render_and_template_gate_help_are_available(self):
        render = run_cli("scripts/easyslides.py", "semantic-render", "--help")
        gate = run_cli("scripts/easyslides.py", "template-gate", "--help")

        self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
        self.assertIn("named-slot semantic", render.stdout)
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertIn("fail-closed semantic template", gate.stdout)

    def test_workflow_write_manifest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            result = run_cli(
                "scripts/easyslides.py",
                "workflow",
                "write-manifest",
                str(project),
                "--route",
                "template-fill-pptx",
                "--stage",
                "scaffold",
                "--status",
                "ready",
                "--artifact",
                "fill_plan=analysis/fill_plan.json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((project / "workflow_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["current"]["route"], "template-fill-pptx")
            self.assertEqual(manifest["current"]["stage"], "scaffold")
            self.assertEqual(manifest["artifacts"]["fill_plan"], "analysis/fill_plan.json")


if __name__ == "__main__":
    unittest.main()
