"""Record the episode from the single global story archive before timing pictures."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from elevator.stories import get_story

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parent
OUT = PROJECT / "assets/voice"
KOKORO = PROJECT / ".venv-tts/bin/python"
VOICE = json.loads((ROOT / 'series/elevator_zero/voices.json').read_text(encoding='utf-8'))['voices']


def tts_cli() -> list[str]:
    specified = os.environ.get('HYPERFRAMES_CLI')
    candidates = [Path(specified)] if specified else []
    candidates += [PROJECT / 'node_modules/hyperframes/bin/hyperframes.mjs',
                   Path('/Users/esun/.npm/_npx/11735d66eed7d088/node_modules/hyperframes/bin/hyperframes.mjs')]
    for candidate in candidates:
        if candidate.is_file():
            return ['node', str(candidate)]
    return ['npx', '--yes', 'hyperframes@0.8.146']


def seconds(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip())


def main() -> None:
    story = get_story("EZ001")
    lines = story["dialogue"] + [
        {"speaker": "lan", "en": story["core_expression"], "zh": story["meaning"]},
        {"speaker": "lan", "en": story["variant"], "zh": story["variant_meaning"]},
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    previous_path = OUT / "manifest.json"
    previous = {item["id"]: item for item in json.loads(previous_path.read_text())} if previous_path.exists() else {}
    manifest = []
    for number, line in enumerate(lines, 1):
        key = f"{number:02d}"
        profile = VOICE[line["speaker"]]
        voice, speed, pitch = profile['voice_id'], profile['speed'], profile['pitch']
        wav = OUT / f"{key}.wav"
        before = previous.get(key)
        if before and before["en"] == line["en"] and before["voice"] == voice and before["pitch"] == pitch and wav.is_file():
            manifest.append(before)
            print(f"{key} reused", flush=True)
            continue
        raw = OUT / f"{key}.raw.wav"
        env = dict(os.environ, HYPERFRAMES_PYTHON=str(KOKORO))
        subprocess.run(tts_cli() + ["tts", line["en"], "--voice", voice,
                        "--speed", str(speed), "-o", str(raw)], env=env, check=True)
        filters = []
        if pitch != 1.0:
            filters.append(f"rubberband=pitch={pitch}:formant=shifted:transients=smooth:pitchq=quality")
        filters += ["highpass=f=70", "loudnorm=I=-19:TP=-2:LRA=8"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ar", "48000", "-ac", "1",
                        "-af", ",".join(filters), str(wav)], check=True)
        raw.unlink()
        item = {"id": key, "speaker": line["speaker"], "en": line["en"], "zh": line["zh"],
                "voice": voice, "speed": speed, "pitch": pitch,
                "duration": round(seconds(wav), 3), "path": f"assets/voice/{key}.wav"}
        manifest.append(item)
        print(f"{key} {item['duration']:.2f}s {voice}: {line['en']}", flush=True)
    previous_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
