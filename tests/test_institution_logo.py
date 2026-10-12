import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image

from scripts.institution_logo import fetch_logo


def json_response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def logo_metadata(**changes):
    payload = {
        "id": "ror-03cve4549",
        "name": "Tsinghua University",
        "name_zh": "清华大学",
        "image_url": "/logo-assets/00/logos/images/ror-03cve4549/revision/512.png",
        "svg_url": "/logo-assets/00/logos/images/ror-03cve4549/revision/logo.svg",
        "asset": {"variant": "emblem", "revision": "revision", "review_status": "reviewed"},
    }
    payload.update(changes)
    return payload


class InstitutionLogoTests(unittest.TestCase):
    def test_no_identified_institution_keeps_placeholder_without_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.institution_logo.urlopen") as request:
            report = fetch_logo(tmp)
            self.assertEqual(report["reason"], "institution_not_identified")
            self.assertIsNone(report["asset_path"])
            request.assert_not_called()

    def test_exact_match_downloads_transparent_logo_and_records_provenance(self):
        png = io.BytesIO()
        Image.new("RGBA", (16, 16), (90, 30, 130, 0)).save(png, format="PNG")
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.institution_logo.urlopen",
            side_effect=[json_response(logo_metadata()), io.BytesIO(png.getvalue())],
        ) as request:
            report = fetch_logo(tmp, "清华大学", variant="emblem")
            self.assertEqual(report["status"], "resolved", report)
            asset = Path(tmp) / report["asset_path"]
            self.assertEqual(asset.read_bytes(), png.getvalue())
            self.assertEqual(report["metadata"]["svg_url"], logo_metadata()["svg_url"])
            self.assertIn("q=%E6%B8%85%E5%8D%8E%E5%A4%A7%E5%AD%A6", request.call_args_list[0].args[0].full_url)
            saved = json.loads((Path(tmp) / "assets/logos/institution_logo.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, report)

    def test_ambiguous_or_unknown_name_never_downloads_first_candidate(self):
        for status, reason in ((409, "institution_ambiguous"), (404, "institution_not_found")):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.institution_logo.urlopen",
                side_effect=HTTPError("https://www.scansci.com/api/logos/resolve", status, "lookup", {},
                                      json_response({"candidates": [{"id": "candidate"}]})),
            ) as request:
                report = fetch_logo(tmp, "Ambiguous University")
                self.assertEqual(report["status"], "fallback")
                self.assertEqual(report["reason"], reason)
                self.assertIsNone(report["asset_path"])
                self.assertEqual(request.call_count, 1)
                if status == 409:
                    self.assertEqual(report["candidates"], [{"id": "candidate"}])

    def test_missing_variant_or_image_keeps_placeholder(self):
        for metadata in (logo_metadata(image_url=None), logo_metadata()):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.institution_logo.urlopen", return_value=json_response(metadata),
            ) as request:
                report = fetch_logo(tmp, "ecnu.edu.cn", variant="lockup_horizontal")
                self.assertEqual(report["status"], "fallback")
                self.assertIsNone(report["asset_path"])
                self.assertEqual(request.call_count, 1)

    def test_invalid_image_or_network_failure_is_a_recorded_fallback(self):
        for responses in ([json_response(logo_metadata()), io.BytesIO(b"<html>Error</html>")],
                          [URLError("offline")], [json_response([])],
                          [json_response(logo_metadata(asset=["invalid"]))]):
            with self.subTest(responses=responses), tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.institution_logo.urlopen", side_effect=responses,
            ):
                report = fetch_logo(tmp, "tsinghua.edu.cn")
                self.assertEqual(report["status"], "fallback", report)
                self.assertIsNone(report["asset_path"])
                self.assertFalse(list((Path(tmp) / "assets/logos").glob("*.png")))

    def test_download_failure_keeps_resolved_identity_and_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.institution_logo.urlopen", side_effect=[
                json_response(logo_metadata()),
                HTTPError("https://www.scansci.com/logo-assets/missing.png", 404, "missing", {}, None),
            ],
        ):
            report = fetch_logo(tmp, "tsinghua.edu.cn")
            self.assertEqual(report["reason"], "image_unavailable")
            self.assertEqual(report["metadata"]["name"], "Tsinghua University")
            self.assertIsNone(report["asset_path"])

    def test_same_published_revision_reuses_existing_logo_without_downloading(self):
        png = io.BytesIO()
        Image.new("RGBA", (16, 16)).save(png, format="PNG")
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.institution_logo.urlopen", side_effect=[
                json_response(logo_metadata()), io.BytesIO(png.getvalue()),
            ]):
                first = fetch_logo(tmp, "tsinghua.edu.cn")
            with patch("scripts.institution_logo.urlopen", return_value=json_response(logo_metadata())) as request:
                second = fetch_logo(tmp, "tsinghua.edu.cn")
            self.assertEqual(second["asset_path"], first["asset_path"])
            self.assertEqual(second["status"], "resolved")
            self.assertEqual(request.call_count, 1)

    def test_remote_metadata_cannot_escape_logo_directory_or_fetch_other_origins(self):
        for changes in ({"id": "../../outside"}, {"image_url": "https://example.com/logo.png"}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.institution_logo.urlopen", return_value=json_response(logo_metadata(**changes)),
            ) as request:
                report = fetch_logo(tmp, "tsinghua.edu.cn")
                self.assertEqual(report["status"], "fallback", report)
                self.assertEqual(request.call_count, 1)
                self.assertIsNone(report["asset_path"])


if __name__ == "__main__":
    unittest.main()
