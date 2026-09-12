"""Bind generated artifacts to their actual inputs; used at creation and delivery."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def fingerprint(path: str | Path) -> dict[str, Any]:
    path = Path(path).resolve()
    with path.open('rb') as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
        digest = hasher.hexdigest()
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}


def matches(record: dict[str, Any], path: str | Path) -> bool:
    try:
        current = fingerprint(path)
        return all(record.get(key) == current[key] for key in ('sha256', 'bytes'))
    except (OSError, TypeError, AttributeError):
        return False
