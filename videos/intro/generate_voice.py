"""Synthesize the daughter's English narration with the fixed local Kokoro voice."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
OUT = PROJECT / "assets/voice"
PYTHON = PROJECT / ".venv-tts/bin/python"
VOICE_PROFILE = json.loads((PROJECT.parents[1] / "series/xiangwei/voices.json").read_text(encoding="utf-8"))["voices"]["daughter"]
VOICE = VOICE_PROFILE["voice_id"]
SPEED = VOICE_PROFILE["speed"]
LINES = [
    ("01", "My dad has a barbershop here in America. After school, I come right here.", VOICE, SPEED),
    ("02", "Dad has a big barber chair. And I have a little toy corner.", VOICE, SPEED),
    ("03", "Emma is always in a hurry. Mr. Miller loves talking about his dog, Milo.", VOICE, SPEED),
    ("04", "Our neighbor runs the coffee shop. Sometimes she brings us coffee.", VOICE, SPEED),
    ("05a", "When someone opens the door, Dad smiles and says:", VOICE, SPEED),
    ("05b", "Come on in!", VOICE, SPEED),
    ("05c", "I say it, too!", VOICE, SPEED),
    ("06", "I learn a new English phrase here every day. Come back tomorrow for another little story from our shop.", VOICE, SPEED),
    ("07", "See you tomorrow!", VOICE, SPEED),
]


def duration(path: Path) -> float:
    value = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip()
    return float(value)


def main() -> None:
    if not PYTHON.is_file():
        raise RuntimeError(f"Kokoro Python 环境不存在：{PYTHON}")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for key, line, voice, speed in LINES:
        raw = OUT / f"{key}.raw.wav"
        wav = OUT / f"{key}.wav"
        env = dict(os.environ, HYPERFRAMES_PYTHON=str(PYTHON))
        subprocess.run(["npx", "--yes", "hyperframes@0.8.144", "tts", line,
                        "--voice", voice, "--speed", str(speed), "-o", str(raw)],
                       env=env, check=True)
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ar", "48000", "-ac", "1",
            "-af", "highpass=f=65,loudnorm=I=-19:TP=-2:LRA=8", str(wav),
        ], check=True)
        seconds = duration(wav)
        if seconds < 0.25:
            raise RuntimeError(f"Voice synthesis produced no audio: {key}")
        manifest.append({"id": key, "text": line, "voice": voice, "duration": round(seconds, 3), "path": str(wav.relative_to(PROJECT))})
        raw.unlink()
        print(f"{key}: {seconds:.2f}s {line}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
