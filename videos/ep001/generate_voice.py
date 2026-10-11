"""Generate English dialogue directly from the global ST001 story record."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
OUT = PROJECT / "assets/voice"
PYTHON = ROOT / "videos/intro/.venv-tts/bin/python"
CLI = os.environ.get("HYPERFRAMES_CLI")
VOICES = json.loads((ROOT / "series/xiangwei/voices.json").read_text(encoding="utf-8"))["voices"]


def story() -> dict:
    for line in (ROOT / "series/xiangwei/stories.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["id"] == "ST001":
            return item
    raise RuntimeError("ST001 is missing from the global story catalog")


def duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip())


def main() -> None:
    if not PYTHON.is_file():
        raise RuntimeError(f"Kokoro Python environment is missing: {PYTHON}")
    episode = story()
    lines = episode["dialogue"] + [{"speaker": "dad", "en": episode["core_expression"],
                                     "zh": episode["meaning"]}]
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, line in enumerate(lines, 1):
        key = f"{index:02d}"
        settings = VOICES[line["speaker"]]
        voice, speed = settings["voice_id"], settings["speed"]
        raw = OUT / f"{key}.raw.wav"
        wav = OUT / f"{key}.wav"
        cli = ["node", CLI] if CLI else ["npx", "--yes", "hyperframes@0.8.144"]
        env = dict(os.environ, HYPERFRAMES_PYTHON=str(PYTHON))
        subprocess.run(cli + ["tts", line["en"], "--voice", voice, "--speed", str(speed),
                              "-o", str(raw)], env=env, check=True)
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ar", "48000", "-ac", "1",
            "-af", "highpass=f=65,loudnorm=I=-19:TP=-2:LRA=8", str(wav),
        ], check=True)
        raw.unlink()
        seconds = duration(wav)
        if seconds < 0.25:
            raise RuntimeError(f"Voice synthesis produced no audio: {key}")
        manifest.append({"id": key, "speaker": line["speaker"], "en": line["en"], "zh": line["zh"],
                         "voice": voice, "duration": round(seconds, 3), "path": str(wav.relative_to(PROJECT))})
        print(f"{key}: {seconds:.2f}s {voice} {line['en']}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
