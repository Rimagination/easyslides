#!/usr/bin/env python3
"""Shared EasySlides workflow manifest helpers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "easyslides.workflow_manifest.v1"
MANIFEST_NAME = "workflow_manifest.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _manifest_path(project_path: str | Path) -> Path:
    path = Path(project_path)
    if path.suffix.lower() == ".json":
        return path
    return path / MANIFEST_NAME


def _empty_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "updated_at": None,
        "current": {},
        "artifacts": {},
        "history": [],
    }


def load_manifest(project_path: str | Path) -> dict[str, Any]:
    path = _manifest_path(project_path)
    if not path.exists():
        return _empty_manifest()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.setdefault("schema_version", SCHEMA_VERSION)
    manifest.setdefault("created_at", _now())
    manifest.setdefault("updated_at", None)
    manifest.setdefault("current", {})
    manifest.setdefault("artifacts", {})
    manifest.setdefault("history", [])
    return manifest


def save_manifest(project_path: str | Path, manifest: dict[str, Any]) -> Path:
    path = _manifest_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_manifest(
    project_path: str | Path,
    *,
    route: str,
    stage: str,
    status: str,
    artifacts: dict[str, Any] | None = None,
    command: list[str] | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(project_path)
    timestamp = _now()
    entry: dict[str, Any] = {
        "route": route,
        "stage": stage,
        "status": status,
        "updated_at": timestamp,
    }
    if command:
        entry["command"] = command
    if artifacts:
        entry["artifacts"] = artifacts
        manifest["artifacts"].update(artifacts)
    if notes:
        entry["notes"] = notes
    if metadata:
        entry["metadata"] = metadata

    manifest["current"] = entry
    manifest["updated_at"] = timestamp
    manifest["history"].append(entry)
    save_manifest(project_path, manifest)
    return manifest


def parse_artifacts(values: list[str] | None) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"artifact must use KEY=VALUE syntax: {value}")
        key, item = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"artifact key is empty: {value}")
        artifacts[key] = item.strip()
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and update EasySlides workflow manifests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser("write-manifest", help="Append a workflow manifest entry.")
    write.add_argument("project_path")
    write.add_argument("--route", required=True)
    write.add_argument("--stage", required=True)
    write.add_argument("--status", required=True)
    write.add_argument("--artifact", action="append", default=[], help="Artifact as KEY=VALUE. Repeatable.")
    write.add_argument("--note", default=None)

    show = subparsers.add_parser("show", help="Print a workflow manifest.")
    show.add_argument("project_path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "write-manifest":
            manifest = update_manifest(
                args.project_path,
                route=args.route,
                stage=args.stage,
                status=args.status,
                artifacts=parse_artifacts(args.artifact),
                command=["easyslides", "workflow", "write-manifest"],
                notes=args.note,
            )
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.command == "show":
            print(json.dumps(load_manifest(args.project_path), ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
