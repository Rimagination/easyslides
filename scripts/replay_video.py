#!/usr/bin/env python3
"""Edit an EasySlides recording or render an original soundtrack."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from replay_soundtrack import STYLE_TEMPOS, render_soundtrack, resolve_soundbank


def finite_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("Expected a finite number.")
    return number


def positive_number(value: str) -> float:
    number = finite_number(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive number.")
    return number


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ValueError(f"{name} is required on PATH.")
    return path


def run_command(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace", check=False)
    if result.returncode:
        detail = result.stderr.strip() or str(result.returncode)
        raise RuntimeError(f"{Path(command[0]).stem} failed: {detail}")
    return result.stdout


def ffmpeg_run(ffmpeg: str, *args: str) -> None:
    run_command([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", *args])


def read_streams(path: Path, ffprobe: str) -> list[dict]:
    metadata = json.loads(run_command(
        [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
    ))
    return metadata.get("streams", [])


def primary_clip(path: Path, ffprobe: str) -> tuple[dict, bool]:
    streams = read_streams(path, ffprobe)
    video = next((item for item in streams if item.get("codec_type") == "video"
                  and not item.get("disposition", {}).get("attached_pic")), None)
    if not video:
        raise ValueError(f"No video stream in {path}")
    duration = positive_number(video.get("duration", "0"))
    video["duration"] = duration
    return video, any(item.get("codec_type") == "audio" for item in streams)


def audio_tempo(speed: float) -> list[str]:
    factors = []
    while speed > 2:
        factors.append("atempo=2")
        speed /= 2
    while speed < .5:
        factors.append("atempo=0.5")
        speed *= 2
    factors.append(f"atempo={speed:.12g}")
    return factors


def publish(candidate: Path, destination: Path) -> None:
    # The staged file lives on the destination filesystem. Publish atomically
    # and refuse to replace a file produced by a concurrent run.
    if os.name == "nt":
        candidate.rename(destination)
    else:
        os.link(candidate, destination)


def music_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bpm", type=positive_number, help="Override the preset tempo.")
    parser.add_argument("--soundbank", type=Path, help="General MIDI DLS sound bank. Defaults to Windows gm.dls.")


def edit_video(args: argparse.Namespace, work: Path, ffmpeg: str, ffprobe: str) -> Path:
    source_info, has_audio = primary_clip(args.video, ffprobe)
    expected = source_info["duration"] / args.speed
    if not math.isfinite(expected) or expected < .001:
        raise ValueError("The requested speed does not produce a usable MP4 duration.")
    video = args.video
    stream_index = source_info["index"]
    if args.speed != 1:
        video = work / "retimed.mp4"
        rate = f"{args.speed:.12g}"
        timestamps = f"setts=pts=PTS/{rate}:dts=DTS/{rate}:duration=DURATION/{rate}"
        ffmpeg_run(ffmpeg, "-i", str(args.video), "-map", f"0:{stream_index}",
                   "-c:v", "copy", "-bsf:v", timestamps, str(video))
        stream_index = 0

    inputs = ["-threads", "2", "-i", str(video)]
    video_output = ["-map", f"0:{stream_index}", "-c:v", "copy"]
    encoding = ["-movflags", "+faststart"]
    next_input = 1
    if args.credit:
        from replay_credit import render_credit

        overlay = work / "credit.png"
        x, y = render_credit(overlay, text=args.credit, frame_width=source_info["width"],
                             frame_height=source_info["height"], style=args.credit_style,
                             accent=args.credit_accent, font_path=args.credit_font)
        inputs.extend(["-i", str(overlay)])
        next_input += 1
        video_output = [
            "-filter_complex_threads", "1",
            "-filter_complex", f"[0:{stream_index}][1:v]overlay=W-w-{x}:H-h-{y}[credit]",
            "-map", "[credit]", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast",
            "-tune", "zerolatency", "-crf", "16", "-pix_fmt", "yuv420p",
            "-fps_mode", "passthrough",
        ]

    audio_output = ["-an"]
    seconds = f"{expected:.9f}"
    if args.music or args.music_file:
        if args.music_file:
            inputs.extend(["-stream_loop", "-1", "-i", str(args.music_file)])
        else:
            soundtrack = work / "soundtrack.wav"
            render_soundtrack(soundtrack, duration=expected, style=args.music,
                              bpm=args.bpm, soundbank=args.soundbank)
            inputs.extend(["-i", str(soundtrack)])
        filters = [f"volume={args.music_gain:.8g}dB", f"atrim=duration={seconds}", "asetpts=PTS-STARTPTS"]
        if args.music_file:
            fade = min(.45, expected / 4)
            filters.append(f"afade=t=out:st={expected - fade:.9f}:d={fade:.9f}")
            encoding.extend(["-t", seconds])
        audio_output = ["-map", f"{next_input}:a:0", "-af", ",".join(filters),
                        "-ar", "48000", "-c:a", "aac", "-b:a", "192k"]
    elif has_audio:
        if args.speed == 1:
            audio_output = ["-map", "0:a:0", "-c:a", "copy"]
        else:
            inputs.extend(["-i", str(args.video)])
            filters = [*audio_tempo(args.speed), "apad", f"atrim=duration={seconds}"]
            audio_output = ["-map", f"{next_input}:a:0", "-af", ",".join(filters),
                            "-c:a", "aac", "-b:a", "192k"]

    candidate = work / "edited.mp4"
    ffmpeg_run(ffmpeg, *inputs, *video_output, *audio_output, *encoding, str(candidate))
    actual, audio_found = primary_clip(candidate, ffprobe)
    source_frames, output_frames = source_info.get("nb_frames"), actual.get("nb_frames")
    if source_frames and output_frames and source_frames != output_frames:
        raise RuntimeError(f"Expected {source_frames} video frames, encoded {output_frames}.")
    if abs(actual["duration"] - expected) > .025:
        raise RuntimeError(f"Expected video duration {expected:.3f}s, encoded {actual['duration']:.3f}s.")
    if (args.music or args.music_file or has_audio) and not audio_found:
        raise RuntimeError("The audio stream was not written.")
    return candidate


def parser_for_replay() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    edit = actions.add_parser("edit", help="Change speed, add music, or add a bottom-right credit.")
    edit.add_argument("video", type=Path, help="Existing MP4 recording.")
    edit.add_argument("--out", type=Path, required=True, metavar="VIDEO.mp4")
    edit.add_argument("--speed", type=positive_number, default=1, help="Playback speed multiplier, e.g. 2.")
    music = edit.add_mutually_exclusive_group()
    music.add_argument("--music", choices=STYLE_TEMPOS, help="Replace audio with an original soundtrack preset.")
    music.add_argument("--music-file", type=Path, help="Replace audio with a local track, fitted to the video.")
    edit.add_argument("--music-gain", type=finite_number, default=-2.5, help="Music level in dB. Default: -2.5.")
    music_options(edit)
    edit.add_argument("--credit", "--watermark", help="One line of watermark text in the lower-right corner.")
    edit.add_argument("--credit-style", "--watermark-style", choices=("plain", "flourish"),
                      help="Watermark appearance. Default: plain.")
    edit.add_argument("--credit-accent", "--watermark-accent",
                      help="Exact text to highlight in flourish style. Defaults to an @mention.")
    edit.add_argument("--credit-font", "--watermark-font", type=Path, help="Local font file for the watermark.")

    score = actions.add_parser("music", help="Render a standalone WAV or MP3 soundtrack.")
    score.add_argument("--out", type=Path, required=True, metavar="TRACK.wav|mp3")
    score.add_argument("--duration", type=positive_number, required=True, help="Track length in seconds.")
    score.add_argument("--style", choices=STYLE_TEMPOS, default="epic", help="Default: epic.")
    music_options(score)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = parser_for_replay()
    args = parser.parse_args(argv)
    destination = args.out.resolve()
    suffix = destination.suffix.lower()
    if destination.exists():
        parser.error(f"Output already exists: {destination}")
    if args.action == "edit":
        if not args.video.is_file() or args.video.suffix.lower() != ".mp4" or suffix != ".mp4":
            parser.error("Video editing requires an existing input MP4 and an output ending in .mp4.")
        if not (args.speed != 1 or args.music or args.music_file or args.credit):
            parser.error("Select a change with --speed, --music, --music-file or --credit.")
        if args.music_file and not args.music_file.is_file():
            parser.error(f"Music file does not exist: {args.music_file}")
        if not args.music and (args.bpm is not None or args.soundbank is not None):
            parser.error("--bpm and --soundbank require a --music preset for video editing.")
        if not args.credit and (args.credit_style or args.credit_accent or args.credit_font):
            parser.error("Credit options require --credit text.")
        if args.credit and ("\n" in args.credit or "\r" in args.credit or not args.credit.strip()):
            parser.error("--credit must be a single nonempty line.")
        if args.credit_accent and (args.credit_style != "flourish" or args.credit_accent not in args.credit):
            parser.error("--credit-accent must occur in the credit and requires --credit-style flourish.")
    elif suffix not in {".wav", ".mp3"}:
        parser.error("Music output must end in .wav or .mp3.")

    try:
        if args.action == "music" or args.music:
            args.soundbank = resolve_soundbank(args.soundbank)
        ffmpeg = executable("ffmpeg") if suffix != ".wav" else None
        ffprobe = executable("ffprobe") if args.action == "edit" else None
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".easyslides-replay-", dir=destination.parent) as temporary:
            work = Path(temporary)
            if args.action == "edit":
                candidate = edit_video(args, work, ffmpeg, ffprobe)
            else:
                candidate = work / "soundtrack.wav"
                render_soundtrack(candidate, duration=args.duration, style=args.style, bpm=args.bpm,
                                  soundbank=args.soundbank)
                if suffix == ".mp3":
                    encoded = work / "soundtrack.mp3"
                    ffmpeg_run(ffmpeg, "-i", str(candidate), "-c:a", "libmp3lame",
                               "-b:a", "256k", str(encoded))
                    candidate = encoded
            publish(candidate, destination)
    except (argparse.ArgumentTypeError, ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"Replay video failed: {exc}", file=sys.stderr)
        return 1
    print(f"Saved: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
