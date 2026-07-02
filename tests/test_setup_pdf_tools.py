import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class SetupPdfToolsTests(unittest.TestCase):
    def test_write_env_value_updates_existing_key_once(self):
        from scripts.setup_pdf_tools import write_env_value

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "KEEP=1\nPDFFIGURES2_JAR=old.jar\nOTHER=2\n",
                encoding="utf-8",
            )

            write_env_value(env_path, "PDFFIGURES2_JAR", r"C:\tools\pdffigures2.jar")

            lines = env_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["KEEP=1", r"PDFFIGURES2_JAR=C:\tools\pdffigures2.jar", "OTHER=2"])

    def test_ensure_python_requirements_invokes_pip_install(self):
        from scripts.setup_pdf_tools import ensure_python_requirements

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            requirements = repo_root / "requirements.txt"
            requirements.write_text("python-pptx\n", encoding="utf-8")
            calls = []

            def fake_runner(args, cwd=None):
                calls.append((args, cwd))

            result = ensure_python_requirements(repo_root, runner=fake_runner)

            self.assertEqual(result["status"], "installed")
            self.assertEqual(calls, [([sys.executable, "-m", "pip", "install", "-r", str(requirements)], repo_root)])

    def test_install_pdffigures2_clones_builds_and_pins_jar(self):
        from scripts.setup_pdf_tools import install_pdffigures2

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            env_path = repo_root / ".env"
            calls = []

            def fake_runner(args, cwd=None):
                calls.append((args, cwd))
                if args == ["sbt", "assembly"]:
                    jar = Path(cwd) / "target" / "scala-2.13" / "pdffigures2-assembly.jar"
                    jar.parent.mkdir(parents=True)
                    jar.write_bytes(b"jar")

            with mock.patch("scripts.setup_pdf_tools.shutil.which", return_value="found"):
                result = install_pdffigures2(repo_root, env_path=env_path, runner=fake_runner)

            source_dir = repo_root / "tools" / "pdffigures2"
            self.assertEqual(
                calls[0],
                (
                    ["git", "clone", "https://github.com/allenai/pdffigures2.git", str(source_dir)],
                    repo_root,
                ),
            )
            self.assertEqual(calls[1], (["sbt", "assembly"], source_dir))
            self.assertEqual(result["status"], "installed")
            self.assertIn("PDFFIGURES2_JAR=", env_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(result["jar"]).exists())

    def test_pdffigures2_command_reads_jar_from_env_file(self):
        from scripts.source_to_md import pdffigures2_preprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jar = root / "pdffigures2.jar"
            jar.write_bytes(b"jar")
            env_path = root / ".env"
            env_path.write_text(f"PDFFIGURES2_JAR={jar}\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                command = pdffigures2_preprocess._pdffigures2_command(
                    root / "paper.pdf",
                    root / "out",
                    env_paths=[env_path],
                )

            self.assertEqual(command, ["java", "-jar", str(jar), str(root / "paper.pdf"), "-d", str(root / "out")])


if __name__ == "__main__":
    unittest.main()
