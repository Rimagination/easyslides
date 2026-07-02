"""MinerU API integration for structured PDF extraction.

Fallback chain: Precision Extract API (token) → Agent Lightweight API → PyMuPDF

Precision API returns: Markdown + JSON layout + extracted images (zip)
Agent API returns: Markdown only (CDN link)
"""

import json
import http.client
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRECISION_BASE = "https://mineru.net/api/v4"
AGENT_BASE = "https://mineru.net/api/v1"

POLL_INTERVAL = 3
POLL_TIMEOUT = 300


class MinerUError(Exception):
    """MinerU API error."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_token() -> Optional[str]:
    """Read MinerU API token from env var or .mineru_token file."""
    token = os.environ.get("MINERU_API_TOKEN") or os.environ.get("MINERU_API_KEY")
    if token:
        return token.strip()

    # If the user set a Windows user-level env var after Codex started, child
    # processes may not inherit it yet. Read the registry directly as a fallback.
    if os.name == "nt":
        try:
            import winreg

            for root, key_path in (
                (winreg.HKEY_CURRENT_USER, "Environment"),
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                ),
            ):
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        for name in ("MINERU_API_TOKEN", "MINERU_API_KEY"):
                            try:
                                value, _ = winreg.QueryValueEx(key, name)
                            except FileNotFoundError:
                                continue
                            if isinstance(value, str) and value.strip():
                                return value.strip()
                except OSError:
                    continue
        except ImportError:
            pass

    # Search for .mineru_token in cwd, then easyslides root
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent.parent]
    for d in candidates:
        p = d / ".mineru_token"
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def _json_request(url: str, method: str = "GET", data: Optional[dict] = None,
                  headers: Optional[dict] = None, timeout: int = 30) -> dict:
    """HTTP request with JSON body/response using stdlib urllib."""
    hdrs: Dict[str, str] = {"Accept": "*/*"}
    body = None
    if data is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    if headers:
        hdrs.update(headers)

    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise MinerUError(f"HTTP {e.code}: {err_body}") from e
    except URLError as e:
        raise MinerUError(f"Network error: {e.reason}") from e


def _put_file(file_path: Path, upload_url: str, timeout: int = 120) -> None:
    """Upload file bytes to a pre-signed URL via PUT."""
    data = file_path.read_bytes()
    parsed = urlsplit(upload_url)
    if parsed.scheme not in {"http", "https"}:
        raise MinerUError(f"Unsupported upload URL scheme: {parsed.scheme}")
    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    conn = connection_cls(parsed.netloc, timeout=timeout)
    try:
        conn.request("PUT", target, body=data, headers={"Content-Length": str(len(data))})
        resp = conn.getresponse()
        detail = resp.read().decode("utf-8", errors="replace")
        if resp.status not in {200, 201, 204}:
            raise MinerUError(f"Upload HTTP {resp.status}: {detail}") from None
    except OSError as e:
        raise MinerUError(f"Upload network error: {e}") from e
    finally:
        conn.close()


def _download(url: str, dest: Path, timeout: int = 120) -> Path:
    """Download URL to file."""
    req = Request(url)
    try:
        with urlopen(req, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
    except (HTTPError, URLError) as e:
        raise MinerUError(f"Download failed: {e}") from e
    return dest


def _find_markdown(search_dir: Path, stem: str) -> Optional[Path]:
    """3-level MD matching: <stem>.md → full.md → first *.md."""
    md_files = list(search_dir.rglob("*.md"))
    for md in md_files:
        if md.stem == stem:
            return md
    for md in md_files:
        if md.name.lower() == "full.md":
            return md
    return md_files[0] if md_files else None


# ---------------------------------------------------------------------------
# Precision Extract API (requires token)
# ---------------------------------------------------------------------------

def extract_precision(
    pdf_path: Path,
    output_dir: Path,
    token: Optional[str] = None,
    model_version: str = "vlm",
    enable_formula: bool = True,
    enable_table: bool = True,
    is_ocr: bool = False,
    language: str = "en",
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> Dict[str, Any]:
    """Extract PDF via MinerU Precision API (v4/file-urls/batch).

    Returns dict: markdown_path, figures_dir, layout_json, method.
    """
    token = token or _get_token()
    if not token:
        raise MinerUError(
            "No MinerU API token. Set MINERU_API_TOKEN or create .mineru_token."
        )

    file_stem = pdf_path.stem
    auth = {"Authorization": f"Bearer {token}"}

    print(f"[MinerU Precision] Uploading {pdf_path.name} ...")

    # 1. Request upload URL
    resp = _json_request(
        f"{PRECISION_BASE}/file-urls/batch",
        method="POST",
        data={
            "files": [{"name": pdf_path.name}],
            "model_version": model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "language": language,
        },
        headers=auth,
    )
    if resp.get("code") != 0:
        raise MinerUError(f"Upload URL request failed: {resp.get('msg')}")

    batch_id = resp["data"]["batch_id"]
    # Official docs: field may be "file_urls" (example) or "files" (param table)
    file_urls = resp["data"].get("file_urls") or resp["data"].get("files")
    if not file_urls:
        raise MinerUError("No upload URL returned")
    upload_url = file_urls[0]

    # 2. Upload file
    _put_file(pdf_path, upload_url)
    print(f"[MinerU Precision] Uploaded. batch_id={batch_id}")

    # 3. Poll batch results
    print("[MinerU Precision] Extracting ...")
    start = time.time()
    zip_url = None

    while True:
        if time.time() - start > poll_timeout:
            raise MinerUError(f"Timeout after {poll_timeout}s")

        poll = _json_request(
            f"{PRECISION_BASE}/extract-results/batch/{batch_id}",
            headers=auth,
        )
        if poll.get("code") != 0:
            raise MinerUError(f"Poll error: {poll.get('msg')}")

        for item in poll["data"]["extract_result"]:
            state = item.get("state", "")
            if state == "done":
                zip_url = item.get("full_zip_url")
            elif state == "failed":
                raise MinerUError(f"Extraction failed: {item.get('err_msg')}")
            elif state == "running":
                prog = item.get("extract_progress")
                if prog:
                    print(f"  {prog.get('extracted_pages', '?')}/{prog.get('total_pages', '?')} pages")

        if zip_url:
            break
        time.sleep(poll_interval)

    # 4. Download & extract zip
    print("[MinerU Precision] Downloading results ...")
    mineru_dir = output_dir / f"{file_stem}_mineru"
    if mineru_dir.exists():
        shutil.rmtree(mineru_dir)
    mineru_dir.mkdir(parents=True, exist_ok=True)

    zip_path = mineru_dir / "result.zip"
    _download(zip_url, zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(mineru_dir)
    zip_path.unlink()

    # 5. Locate outputs
    md_path = _find_markdown(mineru_dir, file_stem)
    if not md_path:
        raise MinerUError("No Markdown found in extraction results")

    figures_dir = mineru_dir / "images"
    if not figures_dir.is_dir():
        figures_dir = None

    layout_json = None
    for name in ("content_list.json", "layout.json"):
        p = mineru_dir / name
        if p.exists():
            layout_json = p
            break

    # Copy markdown to standard location
    final_md = output_dir / f"{file_stem}_mineru.md"
    shutil.copy2(str(md_path), str(final_md))

    print(f"[MinerU Precision] Done → {final_md}")
    return {
        "markdown_path": final_md,
        "figures_dir": figures_dir,
        "layout_json": layout_json,
        "images_dir": figures_dir,
        "method": "mineru_precision",
    }


# ---------------------------------------------------------------------------
# Agent Lightweight API (no token, IP-rate limited, ≤10 MB / ≤20 pages)
# ---------------------------------------------------------------------------

def extract_agent(
    pdf_path: Path,
    output_dir: Path,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> Dict[str, Any]:
    """Extract PDF via MinerU Agent Lightweight API (no token).

    Returns dict: markdown_path, method.
    """
    file_stem = pdf_path.stem
    file_size = pdf_path.stat().st_size
    if file_size > 10 * 1024 * 1024:
        raise MinerUError(f"File too large for Agent API ({file_size / 1024 / 1024:.1f} MB > 10 MB)")

    print(f"[MinerU Agent] Uploading {pdf_path.name} ...")

    # 1. Get signed upload URL via multipart POST
    boundary = f"----MinerU{int(time.time())}"
    file_bytes = pdf_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{pdf_path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = Request(
        f"{AGENT_BASE}/agent/parse/file",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            init = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        raise MinerUError(f"Agent init failed: {e}") from e

    data = init.get("data", {})
    task_id = data.get("task_id")
    put_url = data.get("put_url") or data.get("upload_url")

    if not task_id:
        raise MinerUError("No task_id from Agent API")

    # 2. Upload to signed URL (if provided separately)
    if put_url:
        _put_file(pdf_path, put_url)

    # 3. Trigger parsing
    try:
        _json_request(f"{AGENT_BASE}/agent/parse/{task_id}", method="POST")
    except MinerUError:
        pass  # may auto-start

    # 4. Poll
    print(f"[MinerU Agent] Extracting (task_id={task_id}) ...")
    start = time.time()
    markdown_url = None

    while True:
        if time.time() - start > poll_timeout:
            raise MinerUError(f"Agent timeout after {poll_timeout}s")
        try:
            poll = _json_request(f"{AGENT_BASE}/agent/parse/{task_id}")
        except MinerUError:
            time.sleep(poll_interval)
            continue

        state = poll.get("data", {}).get("state", "")
        if state == "done":
            markdown_url = poll["data"].get("markdown_url")
            break
        if state == "failed":
            raise MinerUError(f"Agent extraction failed: {poll['data'].get('err_msg')}")

        time.sleep(poll_interval)

    if not markdown_url:
        raise MinerUError("No markdown_url in completed response")

    # 5. Download
    final_md = output_dir / f"{file_stem}_mineru.md"
    _download(markdown_url, final_md)
    print(f"[MinerU Agent] Done → {final_md}")

    return {
        "markdown_path": final_md,
        "figures_dir": None,
        "layout_json": None,
        "images_dir": None,
        "method": "mineru_agent",
    }


# ---------------------------------------------------------------------------
# Unified entry point (fallback chain)
# ---------------------------------------------------------------------------

def extract_pdf(
    pdf_path: str | Path,
    output_dir: str | Path,
    token: Optional[str] = None,
    poll_interval: int = POLL_INTERVAL,
    poll_timeout: int = POLL_TIMEOUT,
) -> Dict[str, Any]:
    """Try MinerU extraction: Precision → Agent → raise (caller falls back to PyMuPDF).

    Returns dict: markdown_path, figures_dir, layout_json, method.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    effective_token = token or _get_token()

    # Precision API (requires token)
    if effective_token:
        try:
            return extract_precision(
                pdf_path, output_dir,
                token=effective_token,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
            )
        except MinerUError as exc:
            print(f"[MinerU] Precision API failed: {exc}")
            print("[MinerU] Trying Agent Lightweight API ...")
    else:
        print("[MinerU] No token, using Agent Lightweight API ...")

    # Agent API (no token)
    try:
        return extract_agent(
            pdf_path, output_dir,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
    except MinerUError as exc:
        print(f"[MinerU] Agent API failed: {exc}")
        print("[MinerU] Falling back to PyMuPDF extraction ...")

    raise MinerUError("All MinerU extraction methods failed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MinerU PDF extraction")
    parser.add_argument("pdf", help="PDF file path")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    parser.add_argument("--token", default=None, help="API token (or set MINERU_API_TOKEN)")
    parser.add_argument("--timeout", type=int, default=POLL_TIMEOUT, help="Poll timeout (seconds)")
    args = parser.parse_args()

    result = extract_pdf(args.pdf, args.output, token=args.token, poll_timeout=args.timeout)
    print(f"\nResult: {json.dumps({k: str(v) for k, v in result.items()}, indent=2)}")
