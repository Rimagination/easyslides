"""Release metadata and Git exclusions must work outside the author's workspace."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_plugin_versions_and_image_route_descriptions_agree(self):
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
        zcode = json.loads((ROOT / '.zcode-plugin/plugin.json').read_text(encoding='utf-8'))
        market = json.loads((ROOT / 'marketplace.json').read_text(encoding='utf-8'))
        versions = [codex['version'], zcode['version'], market['plugins'][0]['version']]
        self.assertEqual({v.split('+')[0] for v in versions}, {'1.1.0'})
        for text in (codex['description'], zcode['description'], market['plugins'][0]['description']):
            self.assertIn('selected', text)
        self.assertIn('imagegen', codex['interface']['longDescription'])
        self.assertIn('1.1.0', (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('git'), 'Git needed to check ignore semantics')
    def test_private_outputs_ignored_but_public_templates_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            shutil.copy2(ROOT / '.gitignore', Path(tmp) / '.gitignore')
            ignored = ['output/private.pptx', 'output/release_1_1_0/local_image_reference_registry.json',
                       '.playwright-cli/screenshot.png', 'build/plugin-bundle/easyslides/manifest.json']
            public = ['templates/image_references/nsfc_green.png', 'scripts/build_plugin_bundle.py',
                      '.codex-plugin/plugin.json', 'site/assets/decks/public-example.pptx']
            result = subprocess.run(['git', 'check-ignore', '--stdin', '-z'], cwd=tmp,
                                    input=('\0'.join(ignored + public) + '\0').encode('utf-8'),
                                    capture_output=True, check=True)
            self.assertEqual(set(result.stdout.decode('utf-8').rstrip('\0').split('\0')), set(ignored))

    def test_requirements_declares_encoding_for_windows_pip(self):
        first = (ROOT / 'requirements.txt').read_bytes().splitlines()[0]
        self.assertIn(b'coding: utf-8', first)


if __name__ == '__main__':
    unittest.main()
