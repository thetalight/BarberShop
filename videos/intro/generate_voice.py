"""Synthesize the daughter's English narration with the fixed local Kokoro voice."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
OUT = PROJECT / "assets/voice"
PYTHON = PROJECT / ".venv-tts/bin/python"
VOICE_PROFILE = json.loads((PROJECT.parents[1] / "series/xiangwei/voices.json").read_text(encoding="utf-8"))["voices"]["daughter"]
CLI = os.environ.get("HYPERFRAMES_CLI")
PIN = re.search(r"hyperframes@([0-9.]+)", json.loads((PROJECT / "package.json").read_text())["scripts"]["dev"]).group(1)
VOICE = VOICE_PROFILE["voice_id"]
SPEED = VOICE_PROFILE["speed"]
PITCH = VOICE_PROFILE.get("pitch_shift", 1.0)


def ffmpeg_binary(needs_pitch: bool) -> str:
    candidates = [os.environ.get("FFMPEG_BIN"), shutil.which("ffmpeg"), "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"]
    for candidate in filter(None, candidates):
        if not Path(candidate).is_file():
            continue
        if not needs_pitch or "rubberband" in subprocess.check_output([candidate, "-hide_banner", "-filters"], text=True):
            return candidate
    raise RuntimeError("FFmpeg with the rubberband audio filter is required for the daughter's voice")
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
    manifest_path = OUT / "manifest.json"
    previous = {item["id"]: item for item in json.loads(manifest_path.read_text(encoding="utf-8"))} if manifest_path.exists() else {}
    manifest = []
    for key, line, voice, speed in LINES:
        raw = OUT / f"{key}.raw.wav"
        wav = OUT / f"{key}.wav"
        env = dict(os.environ, HYPERFRAMES_PYTHON=str(PYTHON))
        cli = ["node", CLI] if CLI else ["npx", "--yes", f"hyperframes@{PIN}"]
        subprocess.run(cli + ["tts", line, "--voice", voice, "--speed", str(speed), "-o", str(raw)],
                       env=env, check=True)
        target = previous.get(key, {}).get("duration") if previous.get(key, {}).get("text") == line else None
        filters = []
        if PITCH != 1.0 or target and duration(raw) > target:
            tempo = max(1.0, duration(raw) / target * 1.02) if target else 1.0
            filters.append(f"rubberband=tempo={tempo:.5f}:pitch={PITCH}:formant={VOICE_PROFILE.get('formant', 'shifted')}:transients=smooth:pitchq=quality")
        filters.extend(["highpass=f=65", "loudnorm=I=-19:TP=-2:LRA=8"])
        subprocess.run([
            ffmpeg_binary(PITCH != 1.0), "-y", "-v", "error", "-i", str(raw), "-ar", "48000", "-ac", "1",
            "-af", ",".join(filters), str(wav),
        ], check=True)
        if target:
            aligned = OUT / f"{key}.aligned.wav"
            subprocess.run([
                ffmpeg_binary(False), "-y", "-v", "error", "-i", str(wav), "-ar", "48000", "-ac", "1",
                "-af", f"asetpts=PTS-STARTPTS,apad=whole_dur={target},atrim=duration={target}", str(aligned),
            ], check=True)
            aligned.replace(wav)
        seconds = duration(wav)
        if seconds < 0.25:
            raise RuntimeError(f"Voice synthesis produced no audio: {key}")
        manifest.append({"id": key, "text": line, "voice": voice, "pitch_shift": PITCH,
                         "duration": round(seconds, 3), "path": str(wav.relative_to(PROJECT))})
        raw.unlink()
        print(f"{key}: {seconds:.2f}s {line}", flush=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
