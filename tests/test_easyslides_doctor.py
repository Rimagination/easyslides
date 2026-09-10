from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts import easyslides_doctor as doctor
from scripts.image_acquisition import detect_imagegen_capability


class DoctorTests(unittest.TestCase):
    def test_skill_file_does_not_prove_callable_tool(self):
        with patch("scripts.image_acquisition.detect_imagegen_skill", return_value=Path("imagegen/SKILL.md")):
            report = detect_imagegen_capability(environment={})
        self.assertTrue(report["imagegen_skill_available"])
        self.assertFalse(report["host_native_available"])
        self.assertFalse(report["available"])

    def test_failing_binary_is_not_available(self):
        with patch.object(doctor.shutil, "which", return_value="tool"), patch.object(doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "failed")):
            self.assertFalse(doctor._command_version("tool")["available"])

    def test_registered_office_requires_verification(self):
        with patch.object(doctor, "_powerpoint_check", return_value={"available": None}), patch.object(doctor, "_command_version", return_value={"available": False}), patch.object(doctor, "_module_check", return_value={"available": True}), patch.object(doctor, "_template_checks", return_value=[]):
            report = doctor.build_report(host_native_imagegen=True)
        self.assertEqual(report["status"], "needs_verification")

    def test_missing_renderer_blocks_delivery(self):
        with patch.object(doctor, "_powerpoint_check", return_value={"available": False}), patch.object(doctor, "_command_version", return_value={"available": False}), patch.object(doctor, "_module_check", return_value={"available": True}), patch.object(doctor, "_template_checks", return_value=[]):
            self.assertEqual(doctor.build_report()["status"], "fail")
