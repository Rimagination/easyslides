"""Capture a Windows application window to MP4 using PrintWindow and FFmpeg."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from math import ceil
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import Callable, Iterator


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
        ("planes", wintypes.WORD), ("bit_count", wintypes.WORD), ("compression", wintypes.DWORD),
        ("image_size", wintypes.DWORD), ("x_pixels_per_meter", wintypes.LONG),
        ("y_pixels_per_meter", wintypes.LONG), ("colors_used", wintypes.DWORD),
        ("important_colors", wintypes.DWORD),
    ]


@contextmanager
def capture_surface(width: int, height: int) -> Iterator[tuple[int, memoryview]]:
    import win32gui

    create_bitmap = ctypes.windll.gdi32.CreateDIBSection
    create_bitmap.argtypes = (
        wintypes.HDC, ctypes.POINTER(BitmapInfoHeader), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    )
    create_bitmap.restype = wintypes.HBITMAP
    header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), width, -height, 1, 32)
    address = ctypes.c_void_p()
    dc = win32gui.CreateCompatibleDC(0)
    try:
        bitmap = create_bitmap(dc, ctypes.byref(header), 0, ctypes.byref(address), None, 0)
        if not bitmap:
            raise RuntimeError("Windows could not allocate a capture surface.")
        try:
            previous_bitmap = win32gui.SelectObject(dc, bitmap)
            try:
                pixels = (ctypes.c_ubyte * (width * height * 4)).from_address(address.value)
                yield dc, memoryview(pixels).cast("B")
            finally:
                win32gui.SelectObject(dc, previous_bitmap)
        finally:
            win32gui.DeleteObject(bitmap)
    finally:
        win32gui.DeleteDC(dc)


@contextmanager
def record_window(hwnd: int, ffmpeg: str, destination: Path) -> Iterator[Callable[[float], None]]:
    """Yield a pause function that records the selected window during each step."""
    import win32gui

    print_window = ctypes.windll.user32.PrintWindow
    print_window.argtypes = (wintypes.HWND, wintypes.HDC, wintypes.UINT)
    print_window.restype = wintypes.BOOL
    fps = 10
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    if width < 2 or height < 2 or win32gui.IsIconic(hwnd):
        raise RuntimeError("PowerPoint has no visible window to record.")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix=".easyslides-video-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "recording.mp4"
        with (Path(temporary) / "ffmpeg.log").open("w+b") as log:
            with subprocess.Popen(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
                    "-f", "rawvideo", "-pixel_format", "bgr0",
                    "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0",
                    "-an", "-vf", r"scale=w=trunc(min(1920\,iw)/2)*2:h=-2:flags=lanczos",
                    "-c:v", "libx264", "-threads", "2", "-preset", "veryfast",
                    "-tune", "zerolatency", "-crf", "15",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(candidate),
                ],
                stdin=subprocess.PIPE,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ) as encoder:
                try:
                    with capture_surface(width, height) as (capture_dc, pixels):

                        def pause(seconds: float) -> None:
                            started = monotonic()
                            for index in range(ceil(seconds * fps)):
                                sleep(max(0, started + index / fps - monotonic()))
                                x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
                                if win32gui.IsIconic(hwnd) or (x2 - x1, y2 - y1) != (width, height):
                                    raise RuntimeError("Keep the PowerPoint window open at the same size while recording.")
                                if not print_window(hwnd, capture_dc, 2):
                                    raise RuntimeError("Windows could not capture the PowerPoint window.")
                                ctypes.windll.gdi32.GdiFlush()
                                if index == 0 and len(set(pixels[2::16384])) <= 1:
                                    raise RuntimeError("PowerPoint returned a blank window capture.")
                                encoder.stdin.write(pixels)
                            sleep(max(0, started + seconds - monotonic()))

                        try:
                            yield pause
                            encoder.stdin.close()
                        except OSError as exc:
                            log.seek(0)
                            detail = log.read().decode("utf-8", errors="replace").strip()
                            raise RuntimeError(f"FFmpeg stopped while recording: {detail or exc}") from exc
                    if encoder.wait(timeout=30) != 0 or not candidate.is_file():
                        log.seek(0)
                        detail = log.read().decode("utf-8", errors="replace").strip()
                        raise RuntimeError(f"FFmpeg could not finish the recording: {detail}")
                except BaseException:
                    if encoder.poll() is None:
                        encoder.kill()
                    raise

        # The candidate lives beside the output. On Windows rename is atomic
        # and also fails if another invocation already created the destination.
        candidate.rename(destination)
