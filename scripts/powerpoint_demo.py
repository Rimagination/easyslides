#!/usr/bin/env python3
"""Show an editable deck appearing step by step in desktop PowerPoint."""

from __future__ import annotations

import argparse
from contextlib import nullcontext, suppress
import math
from pathlib import Path
import shutil
import subprocess
import sys
from time import sleep


MSO_TRUE = -1
MSO_FALSE = 0
MSO_GROUP = 6
PP_VIEW_NORMAL = 9
PP_WINDOW_MAXIMIZED = 2


def positive_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("delay must be a positive, finite number")
    return seconds


def slide_numbers(requested: list[int] | None, count: int) -> list[int]:
    if not count:
        raise ValueError("The deck has no slides.")
    if not requested:
        return list(range(1, count + 1))
    if any(number < 1 or number > count for number in requested):
        raise ValueError(f"Slide numbers must be between 1 and {count}.")
    return list(dict.fromkeys(requested))


def hidden_group_items(shape) -> list:
    if shape.Type != MSO_GROUP:
        return []
    hidden = []
    for child in shape.GroupItems:
        if child.Visible == MSO_FALSE:
            hidden.append(child)
        else:
            hidden.extend(hidden_group_items(child))
    return hidden


def activate_window(window) -> int:
    import win32con
    import win32gui
    import win32process
    from win32com.client import Dispatch

    window.Activate()
    window.WindowState = PP_WINDOW_MAXIMIZED
    title_prefix = f"{window.Caption} - "

    def find_window(hwnd, matches):
        if (
            win32gui.IsWindowVisible(hwnd)
            and win32gui.GetClassName(hwnd) == "PPTFrameClass"
            and win32gui.GetWindowText(hwnd).startswith(title_prefix)
        ):
            matches.append(hwnd)

    matches = []
    for _ in range(20):
        win32gui.EnumWindows(find_window, matches)
        if matches:
            break
        sleep(0.1)
    if len(matches) != 1:
        raise RuntimeError("Could not identify the PowerPoint demonstration window.")

    hwnd = matches[0]
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    Dispatch("WScript.Shell").AppActivate(pid)
    if win32gui.GetForegroundWindow() != hwnd:
        try:
            win32gui.SetForegroundWindow(hwnd)
        except win32gui.error:
            flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
    return hwnd


def run_demo(
    source: Path, requested: list[int] | None, delay: float, video: Path | None,
    ffmpeg: str | None, *, per_element: bool = False,
) -> None:
    from ctypes import windll

    from pywintypes import com_error
    from win32com.client import Dispatch

    if video is not None:
        from office.record_window import record_window

    windll.shcore.SetProcessDpiAwareness(2)
    app = Dispatch("PowerPoint.Application")
    deck = app.Presentations.Open(str(source), MSO_TRUE, MSO_TRUE, MSO_FALSE)
    if deck.Path:
        raise RuntimeError("PowerPoint did not create an independent demonstration copy.")

    completed = False
    try:
        pages = slide_numbers(requested, deck.Slides.Count)
        steps = {}
        for page in pages:
            slide_shapes = deck.Slides.Item(page).Shapes
            if per_element:
                # The open presentation is a disposable copy. Images and tables remain intact.
                groups = [shape for shape in slide_shapes if shape.Type == MSO_GROUP and shape.Visible != MSO_FALSE]
                while groups:
                    children = groups.pop().Ungroup()
                    groups.extend(shape for shape in children if shape.Type == MSO_GROUP and shape.Visible != MSO_FALSE)
            shapes = [shape for shape in slide_shapes if shape.Visible != MSO_FALSE]
            shapes.sort(key=lambda shape: shape.ZOrderPosition)
            steps[page] = [(shape, hidden_group_items(shape)) for shape in shapes]
            for shape in shapes:
                shape.Visible = MSO_FALSE

        window = deck.NewWindow()
        window.ViewType = PP_VIEW_NORMAL
        window.View.GotoSlide(pages[0])
        hwnd = activate_window(window)
        sleep(0.4)
        recording = record_window(hwnd, ffmpeg, video) if video is not None else nullcontext(sleep)
        with recording as pause:
            for page, shapes in steps.items():
                window.View.GotoSlide(page)
                print(f"Slide {page}/{deck.Slides.Count}: {len(shapes)} objects", flush=True)
                pause(delay)
                for shape, hidden in shapes:
                    shape.Visible = MSO_TRUE
                    # PowerPoint applies a group's visibility change to its children as well.
                    for child in hidden:
                        child.Visible = MSO_FALSE
                    with suppress(com_error):
                        shape.Select()
                    pause(delay)
                window.Selection.Unselect()
            pause(delay)

        completed = True
    finally:
        with suppress(com_error):
            deck.Saved = MSO_TRUE
            if not completed:
                deck.Close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path, help="Editable .pptx to demonstrate.")
    parser.add_argument("--slide", type=int, action="append", help="1-based slide number. Repeat to choose several. Default: all.")
    parser.add_argument("--delay", type=positive_seconds, default=3.0, help="Seconds to pause at each step. Default: 3.")
    parser.add_argument("--per-element", action="store_true", help="Reveal individual elements inside groups in the demonstration copy.")
    parser.add_argument("--record", type=Path, metavar="VIDEO.mp4", help="Optionally record the PowerPoint window to MP4.")
    args = parser.parse_args(argv)
    source = args.pptx.resolve()
    video = args.record.resolve() if args.record is not None else None
    if not source.is_file() or source.suffix.lower() != ".pptx":
        parser.error(f"Expected an existing .pptx file: {source}")
    if video is not None:
        if video.suffix.lower() != ".mp4":
            parser.error("--record requires an .mp4 output path")
        if video.exists():
            parser.error(f"Recording already exists: {video}")
    if sys.platform != "win32":
        parser.error("PowerPoint demonstration requires Windows and desktop Microsoft PowerPoint.")
    try:
        from pywintypes import com_error
        from pywintypes import error as win32_error
    except ImportError:
        parser.error("PowerPoint demonstration requires pywin32. Install it with: python -m pip install pywin32")

    ffmpeg = shutil.which("ffmpeg") if video is not None else None
    if video is not None and ffmpeg is None:
        parser.error("Recording requires FFmpeg on PATH.")
    try:
        run_demo(source, args.slide, args.delay, video, ffmpeg, per_element=args.per_element)
    except KeyboardInterrupt:
        print("PowerPoint demonstration cancelled.", file=sys.stderr)
        return 130
    except (com_error, win32_error, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"PowerPoint demonstration failed: {exc}", file=sys.stderr)
        return 1
    if video is not None:
        print(f"Recording saved: {video}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
