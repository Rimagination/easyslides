#!/usr/bin/env python3
"""Stage only the existing public plugin bundle for npm's explicit file allowlist."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

try:
    from scripts.build_plugin_bundle import ROOT, build_bundle
except ModuleNotFoundError:
    from build_plugin_bundle import ROOT, build_bundle


def build_npm_runtime() -> dict:
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
    plugin = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    if package['name'] != 'easyslides' or package['version'] != plugin['version']:
        raise ValueError('npm name/version must match the EasySlides plugin release')
    destination = ROOT / 'runtime'
    # Only replace our own generated directory, never a linked or handwritten runtime.
    if destination.is_symlink() or destination.resolve() != destination:
        raise ValueError('npm runtime destination must be a physical directory in this checkout')
    if destination.exists():
        marker = destination / 'bundle_manifest.json'
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('schema_version') != 'easyslides.plugin_bundle.v1':
            raise ValueError('refusing to replace a runtime without the generated bundle marker')
    build_root = ROOT / 'build'
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='npm-runtime-', dir=build_root) as temporary:
        staged = Path(temporary) / 'runtime'
        manifest = build_bundle(staged)
        if destination.exists():
            # The resolved absolute path and generated marker were checked above.
            shutil.rmtree(destination)
        shutil.move(str(staged), str(destination))
    print(f"Staged npm runtime: {manifest['file_count']} files, {manifest['size_bytes']:,} bytes; {len(manifest['layouts'])} official templates", file=sys.stderr)
    return manifest


if __name__ == '__main__':
    build_npm_runtime()
