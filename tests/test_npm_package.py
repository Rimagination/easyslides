"""The npm envelope must keep the established public runtime and no install hooks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_npm_package as builder

ROOT = Path(__file__).resolve().parents[1]


class NpmPackageTests(unittest.TestCase):
    def test_envelope_has_bundle_and_strict_files(self):
        package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(package['name'], 'easyslides')
        self.assertEqual(package['version'], codex['version'])
        self.assertEqual(package['files'], ['dsh/', 'runtime/'])
        self.assertEqual(package['dsh']['bundle']['patch'], './dsh/cordis.patch.yml')
        self.assertTrue((ROOT / package['main']).is_file())
        self.assertFalse(set(package['scripts']) & {'install', 'postinstall', 'preinstall', 'prepare'})
        self.assertFalse(package.get('dependencies'))

    def test_refuses_to_replace_handwritten_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.codex-plugin').mkdir()
            (root / '.codex-plugin/plugin.json').write_text('{"version":"1.2.1"}', encoding='utf-8')
            (root / 'package.json').write_text('{"name":"easyslides","version":"1.2.1"}', encoding='utf-8')
            (root / 'runtime').mkdir()
            source = root / 'runtime/keep.txt'
            source.write_text('user content', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'build_bundle') as bundle:
                with self.assertRaisesRegex(ValueError, 'generated bundle marker'):
                    builder.build_npm_runtime()
                bundle.assert_not_called()
            self.assertEqual(source.read_text(encoding='utf-8'), 'user content')

    def test_failed_rebuild_preserves_previous_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.codex-plugin').mkdir()
            (root / '.codex-plugin/plugin.json').write_text('{"version":"1.2.1"}', encoding='utf-8')
            (root / 'package.json').write_text('{"name":"easyslides","version":"1.2.1"}', encoding='utf-8')
            (root / 'runtime').mkdir()
            marker = root / 'runtime/bundle_manifest.json'
            marker.write_text('{"schema_version":"easyslides.plugin_bundle.v1"}', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'build_bundle', side_effect=ValueError('invalid bundle')):
                with self.assertRaisesRegex(ValueError, 'invalid bundle'):
                    builder.build_npm_runtime()
            self.assertTrue(marker.is_file())


if __name__ == '__main__':
    unittest.main()
