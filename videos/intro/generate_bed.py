"""Create a quiet original music-box bed for the child's narration."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np


PROJECT = Path(__file__).resolve().parent
OUTPUT = PROJECT / "assets/audio/music_box.wav"
SAMPLE_RATE = 48000
DURATION = 39.5


def note_frequency(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    count = int(SAMPLE_RATE * DURATION)
    left = np.zeros(count, dtype=np.float32)
    right = np.zeros(count, dtype=np.float32)
    chords = [
        (60, 64, 67, 71),  # Cmaj7
        (57, 60, 64, 67),  # Am7
        (53, 57, 60, 64),  # Fmaj7
        (55, 59, 62, 67),  # Gadd9
    ]
    for bar in range(10):
        chord = chords[bar % len(chords)]
        for step, midi in enumerate(chord):
            start = bar * 4.0 + step * 0.82 + (0.09 if bar % 2 else 0)
            if start >= DURATION - 0.3:
                continue
            duration = min(2.2, DURATION - start)
            n = int(duration * SAMPLE_RATE)
            t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
            hz = note_frequency(midi + (12 if step == 3 and bar % 2 == 0 else 0))
            attack = np.minimum(1, t / 0.014)
            envelope = attack * np.exp(-2.6 * t)
            wavelet = (np.sin(2 * math.pi * hz * t) + 0.26 * np.sin(2 * math.pi * 2 * hz * t)
                       + 0.09 * np.sin(2 * math.pi * 3 * hz * t)) * envelope * 0.11
            offset = int(start * SAMPLE_RATE)
            pan = 0.45 + 0.17 * math.sin(bar + step)
            left[offset:offset + n] += wavelet * (1 - pan)
            right[offset:offset + n] += wavelet * pan
    fade = min(1.4, DURATION / 2)
    for channel in (left, right):
        channel[:int(fade * SAMPLE_RATE)] *= np.linspace(0, 1, int(fade * SAMPLE_RATE))
        channel[-int(fade * SAMPLE_RATE):] *= np.linspace(1, 0, int(fade * SAMPLE_RATE))
    stereo = np.stack((left, right), axis=1)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0.85:
        stereo *= 0.85 / peak
    with wave.open(str(OUTPUT), "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes((stereo * 32767).astype("<i2").tobytes())
    print(f"{OUTPUT}: {DURATION:.1f}s peak={peak:.3f}")


if __name__ == "__main__":
    main()
