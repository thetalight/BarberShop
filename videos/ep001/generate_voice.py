"""Generate English dialogue directly from the global ST001 story record."""

from __future__ import annotations

import json
import os
import subprocess
import argparse
import shutil
import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
OUT = PROJECT / "assets/voice"
PYTHON = ROOT / "videos/intro/.venv-tts/bin/python"
CLI = os.environ.get("HYPERFRAMES_CLI")
PIN = re.search(r"hyperframes@([0-9.]+)", json.loads((PROJECT / "package.json").read_text())["scripts"]["dev"]).group(1)
VOICES = json.loads((ROOT / "series/xiangwei/voices.json").read_text(encoding="utf-8"))["voices"]


def ffmpeg_binary(needs_pitch: bool) -> str:
    candidates = [os.environ.get("FFMPEG_BIN"), shutil.which("ffmpeg"), "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"]
    for candidate in filter(None, candidates):
        if not Path(candidate).is_file():
            continue
        if not needs_pitch or "rubberband" in subprocess.check_output([candidate, "-hide_banner", "-filters"], text=True):
            return candidate
    raise RuntimeError("FFmpeg with the rubberband audio filter is required for the daughter's voice")


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--speaker", help="Regenerate only one speaker, preserving all other recorded lines")
    parser.add_argument("--force", action="store_true", help="Regenerate matching recordings too")
    args = parser.parse_args()
    if not PYTHON.is_file():
        raise RuntimeError(f"Kokoro Python environment is missing: {PYTHON}")
    episode = story()
    lines = episode["dialogue"] + [
        {"speaker": "dad", "en": episode["core_expression"], "zh": episode["meaning"]},
        {"speaker": "dad", "en": episode["variant"], "zh": episode["variant_meaning"]},
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    previous = {item["id"]: item for item in json.loads(manifest_path.read_text(encoding="utf-8"))} if manifest_path.exists() else {}
    manifest = []
    for index, line in enumerate(lines, 1):
        key = f"{index:02d}"
        settings = VOICES[line["speaker"]]
        voice, speed = settings["voice_id"], line.get("voice_speed", settings["speed"])
        pitch = settings.get("pitch_shift", 1.0)
        existing = previous.get(key)
        if args.speaker and line["speaker"] != args.speaker:
            if not existing or existing["en"] != line["en"] or existing["zh"] != line["zh"]:
                raise RuntimeError(f"Recording {key} is stale; run without --speaker")
            manifest.append(existing)
            continue
        if (not args.force and existing and existing["en"] == line["en"]
                and existing["zh"] == line["zh"] and existing["voice"] == voice
                and existing.get("pitch_shift", 1.0) == pitch
                and existing.get("speed", settings["speed"]) == speed
                and (PROJECT / existing["path"]).is_file()):
            manifest.append(existing)
            print(f"{key}: reused {line['en']}", flush=True)
            continue
        raw = OUT / f"{key}.raw.wav"
        wav = OUT / f"{key}.wav"
        cli = ["node", CLI] if CLI else ["npx", "--yes", f"hyperframes@{PIN}"]
        env = dict(os.environ, HYPERFRAMES_PYTHON=str(PYTHON))
        subprocess.run(cli + ["tts", line["en"], "--voice", voice, "--speed", str(speed),
                              "-o", str(raw)], env=env, check=True)
        target = (existing.get("duration") if existing and existing.get("en") == line["en"]
                  and existing.get("speed", settings["speed"]) == speed else None)
        filters = []
        if pitch != 1.0 or target and duration(raw) > target:
            tempo = max(1.0, duration(raw) / target * 1.02) if target else 1.0
            filters.append(f"rubberband=tempo={tempo:.5f}:pitch={pitch}:formant={settings.get('formant', 'shifted')}:transients=smooth:pitchq=quality")
        filters.extend(["highpass=f=65", "loudnorm=I=-19:TP=-2:LRA=8"])
        subprocess.run([
            ffmpeg_binary(pitch != 1.0), "-y", "-v", "error", "-i", str(raw), "-ar", "48000", "-ac", "1",
            "-af", ",".join(filters), str(wav),
        ], check=True)
        if target:
            aligned = OUT / f"{key}.aligned.wav"
            subprocess.run([
                ffmpeg_binary(False), "-y", "-v", "error", "-i", str(wav), "-ar", "48000", "-ac", "1",
                "-af", f"asetpts=PTS-STARTPTS,apad=whole_dur={target},atrim=duration={target}", str(aligned),
            ], check=True)
            aligned.replace(wav)
        raw.unlink()
        seconds = duration(wav)
        if seconds < 0.25:
            raise RuntimeError(f"Voice synthesis produced no audio: {key}")
        manifest.append({"id": key, "speaker": line["speaker"], "en": line["en"], "zh": line["zh"],
                         "voice": voice, "speed": speed, "pitch_shift": pitch,
                         "duration": round(seconds, 3), "path": str(wav.relative_to(PROJECT))})
        print(f"{key}: {seconds:.2f}s {voice} {line['en']}", flush=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
