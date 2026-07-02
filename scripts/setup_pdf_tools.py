#!/usr/bin/env python3
"""First-use setup for EasySlides PDF extraction dependencies."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PDFFIGURES2_REPO_URL = "https://github.com/allenai/pdffigures2.git"
Runner = Callable[[list[str], Path | None], None]


def run_command(args: list[str], cwd: Path | None = None) -> None:
    """Run a setup command and raise a readable error on failure."""
    try:
        subprocess.run(
            args,
            cwd=cwd,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing executable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed ({exc.returncode}): {' '.join(args)}") from exc


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key.strip(), value


def read_env_file(env_path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a dotenv file."""
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            values[parsed[0]] = parsed[1]
    return values


def env_candidates(repo_root: Path = REPO_ROOT) -> list[Path]:
    """Return local config files in lookup order."""
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    try:
        candidates.append(Path.home() / ".ppt-master" / ".env")
    except RuntimeError:
        pass
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def read_env_value(key: str, *, repo_root: Path = REPO_ROOT, extra_paths: Iterable[Path] = ()) -> str | None:
    """Resolve a config value from process env and local dotenv files."""
    if os.environ.get(key):
        return os.environ[key].strip()
    for env_path in [*extra_paths, *env_candidates(repo_root)]:
        value = read_env_file(env_path).get(key)
        if value:
            return value
    return None


def write_env_value(env_path: Path, key: str, value: str) -> None:
    """Upsert a dotenv key without disturbing unrelated settings."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    output: list[str] = []
    updated = False
    for line in lines:
        parsed = _parse_env_line(line)
        if parsed and parsed[0] == key:
            if not updated:
                output.append(f"{key}={value}")
                updated = True
            continue
        output.append(line)
    if not updated:
        output.append(f"{key}={value}")
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def ensure_python_requirements(repo_root: Path = REPO_ROOT, *, runner: Runner = run_command) -> dict[str, str]:
    """Install Python requirements with the current interpreter."""
    requirements = repo_root / "requirements.txt"
    if not requirements.exists():
        return {"tool": "python", "status": "skipped", "detail": "requirements.txt not found"}
    runner([sys.executable, "-m", "pip", "install", "-r", str(requirements)], repo_root)
    return {"tool": "python", "status": "installed", "detail": str(requirements)}


def _configured_pdffigures2(repo_root: Path, env_path: Path | None = None) -> dict[str, str] | None:
    extra_paths = [env_path] if env_path else []
    command = read_env_value("PDFFIGURES2_CMD", repo_root=repo_root, extra_paths=extra_paths)
    if command:
        return {"tool": "pdffigures2", "status": "configured", "command": command}
    jar = read_env_value("PDFFIGURES2_JAR", repo_root=repo_root, extra_paths=extra_paths)
    if jar and Path(jar).exists():
        return {"tool": "pdffigures2", "status": "configured", "jar": jar}
    return None


def _find_pdffigures2_jar(source_dir: Path) -> Path | None:
    patterns = ("*assembly*.jar", "pdffigures2*.jar", "*.jar")
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in source_dir.rglob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _missing_tools(names: Iterable[str]) -> list[str]:
    return [name for name in names if shutil.which(name) is None]


def install_pdffigures2(
    repo_root: Path = REPO_ROOT,
    *,
    env_path: Path | None = None,
    source_dir: Path | None = None,
    runner: Runner = run_command,
) -> dict[str, str]:
    """Clone and build PDFFigures2, then pin the jar in local `.env`."""
    env_path = env_path or repo_root / ".env"
    source_dir = source_dir or repo_root / "tools" / "pdffigures2"

    configured = _configured_pdffigures2(repo_root, env_path)
    if configured:
        return configured

    missing = _missing_tools(("git", "java", "sbt"))
    if missing:
        raise RuntimeError(
            "Missing required tools for PDFFigures2 build: "
            + ", ".join(missing)
            + ". Install them, then rerun setup-pdf-tools --install."
        )

    if not source_dir.exists():
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        runner(["git", "clone", PDFFIGURES2_REPO_URL, str(source_dir)], repo_root)

    runner(["sbt", "assembly"], source_dir)
    jar = _find_pdffigures2_jar(source_dir)
    if not jar:
        raise RuntimeError(f"PDFFigures2 build completed but no jar was found under {source_dir}")

    write_env_value(env_path, "PDFFIGURES2_JAR", str(jar))
    return {"tool": "pdffigures2", "status": "installed", "jar": str(jar), "env": str(env_path)}


def check_mineru_token(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Report whether MinerU has a token configured."""
    token = os.environ.get("MINERU_API_TOKEN") or os.environ.get("MINERU_API_KEY")
    token_file = repo_root / ".mineru_token"
    if token:
        return {"tool": "mineru", "status": "configured", "detail": "environment variable"}
    if token_file.exists() and token_file.read_text(encoding="utf-8").strip():
        return {"tool": "mineru", "status": "configured", "detail": str(token_file)}
    return {
        "tool": "mineru",
        "status": "needs-token",
        "detail": "Set MINERU_API_TOKEN or save a token in .mineru_token.",
    }


def write_mineru_token(repo_root: Path, token: str) -> dict[str, str]:
    token_path = repo_root / ".mineru_token"
    token_path.write_text(token.strip() + "\n", encoding="utf-8")
    return {"tool": "mineru", "status": "configured", "detail": str(token_path)}


def setup_pdf_tools(
    repo_root: Path = REPO_ROOT,
    *,
    install: bool = False,
    skip_python: bool = False,
    mineru_token: str | None = None,
    env_path: Path | None = None,
    runner: Runner = run_command,
) -> list[dict[str, str]]:
    """Run first-use setup steps and return a small status report."""
    report: list[dict[str, str]] = []
    env_path = env_path or repo_root / ".env"
    if install and not skip_python:
        report.append(ensure_python_requirements(repo_root, runner=runner))
    elif skip_python:
        report.append({"tool": "python", "status": "skipped", "detail": "--skip-python"})

    report.append(write_mineru_token(repo_root, mineru_token) if mineru_token else check_mineru_token(repo_root))

    configured = _configured_pdffigures2(repo_root, env_path)
    if configured:
        report.append(configured)
    elif install:
        report.append(install_pdffigures2(repo_root, env_path=env_path, runner=runner))
    else:
        report.append(
            {
                "tool": "pdffigures2",
                "status": "missing",
                "detail": "Run setup-pdf-tools --install or set PDFFIGURES2_CMD/PDFFIGURES2_JAR.",
            }
        )
    return report


def print_report(report: list[dict[str, str]]) -> None:
    for item in report:
        detail = item.get("detail") or item.get("jar") or item.get("command") or ""
        suffix = f" - {detail}" if detail else ""
        print(f"[{item['status']}] {item['tool']}{suffix}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install/configure EasySlides PDF extraction dependencies.")
    parser.add_argument("--install", action="store_true", help="Install Python requirements and build PDFFigures2.")
    parser.add_argument("--skip-python", action="store_true", help="Do not install requirements.txt.")
    parser.add_argument("--mineru-token", default=None, help="Save a MinerU token to .mineru_token.")
    parser.add_argument("--env", dest="env_path", default=None, help="Dotenv file to update (default: repo .env).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    report = setup_pdf_tools(
        REPO_ROOT,
        install=args.install,
        skip_python=args.skip_python,
        mineru_token=args.mineru_token,
        env_path=Path(args.env_path) if args.env_path else None,
    )
    print_report(report)


if __name__ == "__main__":
    main()
