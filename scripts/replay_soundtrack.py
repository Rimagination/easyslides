"""Compose and render stereo orchestral beds from a local General MIDI DLS bank."""

from __future__ import annotations

import math
import os
from pathlib import Path
import struct


STYLE_TEMPOS = {"epic": 108, "ensemble": 138, "legato": 138}
SAMPLE_RATE = 44100

# Each entry contains a bass note, a chord voicing and the melody for one bar.
EPIC_FORM = (
    (38, (50, 57, 62, 65), ((0, 74), (1.5, 77), (2, 81))),
    (34, (46, 53, 58, 62), ((0, 82), (1.75, 81), (2.5, 77))),
    (29, (48, 53, 57, 60), ((0, 81), (2, 79), (3, 77))),
    (36, (48, 55, 60, 64), ((0, 76), (1.5, 79), (2.5, 84))),
    (38, (50, 57, 62, 65), ((0, 86), (1.9, 84), (3, 81))),
    (34, (46, 53, 58, 62), ((0, 82), (2.2, 81), (3, 77))),
    (31, (50, 55, 58, 62), ((0, 79), (1.5, 82), (2, 86))),
    (33, (49, 57, 61, 64), ((0, 85), (1.5, 83), (2, 81))),
)
ENSEMBLE_FORM = (
    (28, (52, 55, 59, 64), ((0, 76), (.75, 79), (1.5, 83), (3, 81))),
    (36, (48, 52, 55, 60), ((0, 79), (1.6, 76), (2.4, 74), (3, 72))),
    (31, (50, 55, 59, 62), ((0, 74), (.75, 71), (1.5, 79), (3.1, 83))),
    (38, (50, 54, 57, 62), ((0, 81), (1.1, 78), (1.9, 76), (2.6, 74))),
    (28, (52, 55, 59, 64), ((0, 76), (.75, 79), (1.5, 83), (2.25, 88))),
    (33, (48, 52, 57, 60), ((0, 84), (1.5, 81), (2.5, 76), (3.4, 79))),
    (36, (48, 52, 55, 60), ((0, 84), (1.25, 86), (2, 88))),
    (35, (47, 51, 54, 59), ((0, 87), (1.5, 83), (2.25, 81), (3.1, 78))),
)


def resolve_soundbank(path: Path | None = None) -> Path:
    """Resolve a caller-provided bank or the stock Windows General MIDI bank."""
    if path is not None:
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"DLS soundbank does not exist: {path}")
        return path
    windows = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windows:
        bank = Path(windows) / "System32" / "drivers" / "gm.dls"
        if bank.is_file():
            return bank
    raise ValueError(
        "No local General MIDI DLS soundbank found. Supply one with --soundbank "
        "or use an existing audio file."
    )


class DlsBank:
    """Read the PCM samples and tuning needed for melodic General MIDI programs."""

    def __init__(self, path: Path):
        self.data = path.read_bytes()
        end = struct.unpack_from("<I", self.data, 4)[0] + 8 if len(self.data) >= 12 else 0
        if self.data[:4] != b"RIFF" or self.data[8:12] != b"DLS " or not 12 <= end <= len(self.data):
            raise ValueError(f"Invalid RIFF DLS soundbank: {path}")
        root = list(self.chunks(12, end))
        self.wave_start, self.wave_end = self.find_list(root, b"wvpl")
        table_start, table_end = self.find(root, b"ptbl")
        header, count = struct.unpack_from("<II", self.data[table_start:table_end])
        if header < 8 or table_start + header + 4 * count > table_end:
            raise ValueError("Invalid DLS wave pool table.")
        self.wave_offsets = struct.unpack_from(f"<{count}I", self.data, table_start + header)
        self.regions = {}
        self.waves = {}
        for code, start, end in self.chunks(*self.find_list(root, b"lins")):
            if code != b"LIST" or self.data[start:start + 4] != b"ins ":
                continue
            instrument = list(self.chunks(start + 4, end))
            first, last = self.find(instrument, b"insh")
            _, bank, program = struct.unpack_from("<III", self.data[first:last])
            if bank != 0:
                continue
            regions = []
            for code, first, last in self.chunks(*self.find_list(instrument, b"lrgn")):
                if code != b"LIST" or self.data[first:first + 4] not in (b"rgn ", b"rgn2"):
                    continue
                region = list(self.chunks(first + 4, last))
                first_key, last_key = self.find(region, b"rgnh")
                low, high = struct.unpack_from("<HH", self.data[first_key:last_key])
                first_link, last_link = self.find(region, b"wlnk")
                wave = struct.unpack_from("<I", self.data[first_link:last_link], 8)[0]
                tuning = self.tuning(region)
                regions.append((low, high, wave, tuning))
            if regions:
                self.regions[program] = regions

    def chunks(self, start: int, end: int):
        while start + 8 <= end:
            code, size = struct.unpack_from("<4sI", self.data, start)
            stop = start + 8 + size
            if stop > end:
                raise ValueError("A DLS chunk extends beyond its parent chunk.")
            yield code, start + 8, stop
            start = stop + (size & 1)

    def find(self, entries, tag: bytes):
        for name, start, end in entries:
            if name == tag:
                return start, end
        raise ValueError(f"DLS soundbank is missing the {tag.decode('ascii')} chunk.")

    def find_list(self, entries, tag: bytes):
        for name, start, end in entries:
            if name == b"LIST" and self.data[start:start + 4] == tag:
                return start + 4, end
        raise ValueError(f"DLS soundbank is missing the {tag.decode('ascii')} list.")

    def tuning(self, entries):
        for name, start, end in entries:
            if name != b"wsmp":
                continue
            header, root, cents, attenuation, _, loop_count = struct.unpack_from("<IHhiII", self.data[start:end])
            if root > 127:
                raise ValueError("The DLS soundbank contains an invalid sample root note.")
            loop = None
            if loop_count and 20 <= header <= end - start - 16:
                _, _, loop_start, loop_length = struct.unpack_from("<IIII", self.data, start + header)
                loop = loop_start, loop_length
            return root, cents, attenuation, loop
        return None

    def wave(self, wave_id: int):
        import numpy as np

        if wave_id in self.waves:
            return self.waves[wave_id]
        if wave_id >= len(self.wave_offsets):
            raise ValueError(f"DLS region references an unknown wave {wave_id}.")
        start = self.wave_start + self.wave_offsets[wave_id]
        if not self.wave_start <= start <= self.wave_end - 12 or self.data[start:start + 4] != b"LIST":
            raise ValueError(f"Invalid DLS wave {wave_id}.")
        end = start + 8 + struct.unpack_from("<I", self.data, start + 4)[0]
        if end > self.wave_end or self.data[start + 8:start + 12] != b"wave":
            raise ValueError(f"Invalid DLS wave {wave_id}.")
        entries = list(self.chunks(start + 12, end))
        fmt_start, fmt_end = self.find(entries, b"fmt ")
        encoding, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", self.data[fmt_start:fmt_end])
        if encoding != 1 or channels not in (1, 2) or rate <= 0 or bits not in (8, 16):
            raise ValueError("Use a General MIDI DLS bank with 8-bit or 16-bit PCM samples.")
        first, last = self.find(entries, b"data")
        raw = self.data[first:last]
        if len(raw) < channels * bits // 8 or len(raw) % (channels * bits // 8):
            raise ValueError(f"Invalid PCM samples in DLS wave {wave_id}.")
        samples = np.frombuffer(raw, "<i2" if bits == 16 else "u1").astype(np.float32)
        samples = samples / 32768 if bits == 16 else (samples - 128) / 128
        if channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)
        self.waves[wave_id] = samples, rate, self.tuning(entries)
        return self.waves[wave_id]

    def voice(self, program: int, pitch: int):
        regions = self.regions.get(program)
        if not regions:
            raise ValueError(f"The DLS bank is missing General MIDI program {program + 1}.")
        _, _, wave_id, tuning = min(
            regions, key=lambda item: max(item[0] - pitch, pitch - item[1], 0)
        )
        samples, rate, wave_tuning = self.wave(wave_id)
        return samples, rate, tuning or wave_tuning or (60, 0, 0, None)


def tone_filter(samples, frequency, kind, *, axis=-1):
    from scipy import signal

    filter_bank = signal.butter(2, frequency, btype=kind, fs=SAMPLE_RATE, output="sos")
    return signal.sosfilt(filter_bank.astype("float32"), samples, axis=axis)


class Orchestra:
    def __init__(self, bank: DlsBank, frames: int, bpm: float):
        import numpy as np

        self.bank = bank
        self.samples = np.zeros((frames, 2), dtype=np.float32)
        self.beat_seconds = 60 / bpm
        self.random = np.random.default_rng(31626)

    def place(self, signal, start: int, pan: float):
        end = min(len(self.samples), start + len(signal))
        if end <= start:
            return
        angle = (1 + pan) * math.pi / 4
        self.samples[start:end, 0] += signal[:end - start] * math.cos(angle)
        self.samples[start:end, 1] += signal[:end - start] * math.sin(angle)

    def note(self, program, pitch, beat, beats, gain, pan=0, *, attack=.05, release=.20):
        import numpy as np

        start = max(0, round((beat * self.beat_seconds + self.random.uniform(-.008, .008)) * SAMPLE_RATE))
        held = beats * self.beat_seconds
        count = min(len(self.samples) - start, round((held + release) * SAMPLE_RATE))
        if beats <= 0 or count <= 0:
            return
        wave, rate, (root, cents, attenuation, loop) = self.bank.voice(program, pitch)
        time = np.arange(count, dtype=np.float32) / SAMPLE_RATE
        ratio = 2 ** ((pitch - root + cents / 100) / 12)
        source = time * (rate * ratio)
        if loop is not None:
            first, loop_length = loop
            end = first + loop_length
            if loop_length > 8 and end <= len(wave):
                source = np.where(source >= end, first + np.mod(source - first, loop_length), source)
            else:
                loop = None
        index = np.minimum(source, len(wave) - 1).astype(np.int32)
        after = np.minimum(index + 1, len(wave) - 1)
        if loop is not None:
            after = np.where(after == end, first, after)
        fraction = np.minimum(source - index, 1)
        sound = wave[index] + (wave[after] - wave[index]) * fraction
        if loop is None:
            sound[source >= len(wave) - 1] = 0
        rise = np.sin(np.minimum(time / attack, 1) * math.pi / 2)
        fall = np.maximum(1 - np.maximum(time - held, 0) / release, 0) ** 1.35
        volume = gain * 10 ** (min(120, attenuation / 65536) / 200)
        self.place(sound * rise * fall * volume, start, pan)

    def drum(self, beat: float, gain: float, kind: str):
        import numpy as np

        if kind == "kick":
            time = np.arange(round(.8 * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
            phase = 2 * math.pi * (45 * time + 1.75 * (1 - np.exp(-time / .038)))
            sound = np.sin(phase) * np.exp(-time * 5.8) * (1 - np.exp(-time * 240))
            pan = -.04
        else:
            time = np.arange(round((.18 if kind == "snare" else 1.3) * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
            frequency = [700, 5300] if kind == "snare" else [3100, 9800]
            noise = tone_filter(self.random.standard_normal(len(time), dtype=np.float32), frequency, "bandpass")
            envelope = (
                (1 - np.exp(-time * 240)) * np.exp(-time * 26)
                if kind == "snare" else np.sin(math.pi * time / 1.3) ** 2
            )
            sound = noise * envelope
            pan = .30
        self.place(sound * gain, round(beat * self.beat_seconds * SAMPLE_RATE), pan)


def arrange(orchestra: Orchestra, length: float, style: str) -> None:
    """Lay out the selected orchestration on a tempo grid with a final cadence."""
    beat_count = length / orchestra.beat_seconds
    cadence = beat_count - min(2.38, beat_count * .30)
    starts = list(range(0, math.ceil(cadence), 4))
    if len(starts) > 1 and cadence - starts[-1] < .75:
        starts.pop()
    starts.extend((cadence, beat_count))
    form = EPIC_FORM if style == "epic" else ENSEMBLE_FORM
    finale = (38, (50, 57, 62, 66), ((0, 86),)) if style == "epic" else (
        31, (50, 55, 59, 62), ((0, 91),)
    )
    melody = []

    for bar, (start, end) in enumerate(zip(starts, starts[1:])):
        closing = start == cadence
        root, chord, motif = finale if closing else form[bar % len(form)]
        section = start / beat_count
        beats = end - start
        level = .62 + .42 * section
        orchestra.note(43, root + 12, start, beats, .065 * level, -.12, attack=.12, release=.28)
        for index, (pitch, pan) in enumerate(zip(chord, (-.52, .47, -.30, .30))):
            bedding = pitch + (12 if index in (1, 3) else 0)
            orchestra.note(
                49 if style == "legato" else 48, bedding, start, beats, .048 * level, pan,
                attack=.24 if style == "legato" else .13, release=.39,
            )
            if section > .46 and index in (1, 3):
                orchestra.note(52, bedding, start, beats, .018 * level, -pan, attack=.24, release=.36)
        if style == "legato" and len(motif) > 2:
            motif = (motif[0], motif[2])
        for offset, pitch in motif:
            if offset < beats and (style != "legato" or not melody or pitch != melody[-1][1]):
                melody.append((start + offset, pitch))

        if style != "legato" and not closing:
            for eighth, voice in enumerate((0, 2, 1, 3, 0, 2, 1, 3)):
                offset = eighth * .5
                if offset >= beats:
                    break
                pitch = chord[voice]
                available = min(.37, beats - offset)
                if style == "ensemble":
                    orchestra.note(0, pitch + 12, start + offset, available, .068 * level, -.15, attack=.008)
                    if eighth % 2:
                        orchestra.note(12 if bar % 2 == 0 else 46, pitch + 24, start + offset, available,
                                       .052 * level, .44, attack=.01)
                    if section > .24:
                        orchestra.note(45, pitch, start + offset, min(.25, available), .046 * level, -.49)
                elif eighth % 2 == 0 or section > .40:
                    program = 46 if section < .28 else 42
                    orchestra.note(program, pitch + 12, start + offset, available, .050 * level, .37)

        orchestra.drum(start, (.060 if style == "legato" else .11) * level, "kick")
        if not closing and beats > 2.55 and section > .12:
            orchestra.drum(start + 2.5, (.035 if style == "legato" else .059) * level, "kick")
        if style != "legato" and beats > 3.05 and section > .19:
            orchestra.drum(start + 1, .038 * level, "snare")
            orchestra.drum(start + 3, .056 * level, "snare")
        if closing or (section > .35 and bar % 4 == 0):
            orchestra.note(47, root + 24, start, min(1.1, beats), .088 * level, -.32, attack=.015)
            if style == "ensemble":
                orchestra.note(9, motif[0][1], start, min(.4, beats), .036 * level, .32, attack=.008)
        if closing and style == "epic":
            orchestra.note(14, chord[-1] + 12, start, beats, .029, .36, attack=.01)
        elif not closing and bar % 4 == 3 and beats > 3.3:
            orchestra.drum(start + 1, .024 if style == "legato" else .057, "swell")

    for index, (start, pitch) in enumerate(melody):
        end = melody[index + 1][0] if index + 1 < len(melody) else beat_count
        section = start / beat_count
        beats = end - start
        level = .77 + .28 * section
        if style == "legato":
            orchestra.note(48, pitch, start, beats, .117 * level, -.32, attack=.21, release=.31)
            program = 73 if section < .44 else 60
            orchestra.note(program, pitch if program == 73 else pitch - 12, start, beats,
                           .075 * level, .27, attack=.22, release=.31)
            orchestra.note(71 if section < .48 else 42, pitch - 24, start, beats,
                           .037 * level, -.10, attack=.22, release=.31)
            if section > .56:
                orchestra.note(40, pitch, start, beats, .058 * level, .41, attack=.23, release=.32)
            continue
        span = beats * .84
        if style == "ensemble" and section < .52:
            program = 68 if section < .19 else 73 if section < .36 else 71
            orchestra.note(program, pitch - (0 if program == 73 else 12), start, span,
                           .112 * level, .20, attack=.066)
        elif style == "epic" and section < .20:
            orchestra.note(42, pitch - 24, start, span, .118 * level, -.16, attack=.088)
        else:
            orchestra.note(60, pitch - 12, start, span, .122 * level, .14, attack=.079)
            orchestra.note(40, pitch, start, span, .085 * level, -.39, attack=.09)
            if section > .62:
                orchestra.note(56 if style == "ensemble" else 61, pitch - 12, start, span,
                               .055 * level, .44, attack=.053)


def mixdown(orchestra: Orchestra, style: str):
    import numpy as np
    from scipy import signal

    samples = orchestra.samples
    frames = len(samples)
    ir_size = min(frames, round(1.9 * SAMPLE_RATE))
    time = np.arange(ir_size, dtype=np.float32) / SAMPLE_RATE
    hall = np.exp(-time * 4.0) * np.minimum(time * 24, 1)
    for channel in range(2):
        noise = orchestra.random.standard_normal(ir_size, dtype=np.float32)
        impulse = tone_filter(noise, [220, 5100], "bandpass") * hall
        impulse *= .25 / max(float(np.linalg.norm(impulse)), 1e-6)
        for delay, amplitude in ((.027, .092), (.048, .069), (.080, .041)):
            at = round((delay + channel * .005) * SAMPLE_RATE)
            if at < ir_size:
                impulse[at] += amplitude
        wet = .82 * samples[:, channel] + .18 * samples[:, 1 - channel]
        samples[:, channel] += signal.oaconvolve(wet, impulse)[:frames] * (.67 if style == "legato" else .48)
    samples[:] = tone_filter(samples, 28, "highpass", axis=0)
    if style == "legato":
        samples[:] = .44 * samples + .56 * tone_filter(samples, 2100, "lowpass", axis=0)
    samples *= .8 / max(float(np.percentile(np.abs(samples), 99.8)), 1e-6)
    np.tanh(samples, out=samples)
    peak = float(np.max(np.abs(samples)))
    if peak > 0:
        samples *= .83 / peak
    fade_out = min(round(.42 * SAMPLE_RATE), max(frames // 4, 1))
    fade_in = min(round(.018 * SAMPLE_RATE), max(frames // 4, 1))
    samples[-fade_out:] *= (np.cos(np.linspace(0, math.pi / 2, fade_out, dtype=np.float32)) ** 2)[:, None]
    samples[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)[:, None]
    return (samples * 32767).astype(np.int16)


def render_soundtrack(
    destination: Path,
    *,
    duration: float,
    style: str,
    bpm: float | None = None,
    soundbank: Path | None = None,
) -> None:
    """Write a two-channel, 44.1 kHz PCM WAV with the requested sample length."""
    if style not in STYLE_TEMPOS:
        raise ValueError(f"Unknown soundtrack style: {style}")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Soundtrack duration must be a positive, finite number.")
    tempo = STYLE_TEMPOS[style] if bpm is None else bpm
    if not math.isfinite(tempo) or not 20 <= tempo <= 360:
        raise ValueError("Soundtrack tempo must be between 20 and 360 BPM.")
    bank = resolve_soundbank(soundbank)
    try:
        from scipy.io import wavfile
    except ImportError as exc:
        raise ValueError("Soundtrack synthesis requires NumPy and SciPy.") from exc
    frame_count = duration * SAMPLE_RATE
    if not math.isfinite(frame_count):
        raise ValueError("Soundtrack duration exceeds the renderer's sample count range.")
    frames = max(1, round(frame_count))
    try:
        orchestra = Orchestra(DlsBank(bank), frames, tempo)
        arrange(orchestra, frames / SAMPLE_RATE, style)
        wavfile.write(destination, SAMPLE_RATE, mixdown(orchestra, style))
    except struct.error as exc:
        raise ValueError(f"Invalid or truncated General MIDI DLS bank: {bank}") from exc
