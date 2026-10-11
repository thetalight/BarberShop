"""Register the verified intro and publish its history/sidecar files."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from build_composition import CAPTIONS, SCENES
from generate_voice import LINES, VOICE_PROFILE


PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(ROOT))
from barber import stories  # noqa: E402


TRANSLATIONS = [
    "我爸爸在美国开了一家理发店。放学后，我就来这里。",
    "爸爸有一把大大的理发椅。我有一个小小的玩具角。",
    "艾玛总是有点赶时间。米勒爷爷爱讲他的小狗米洛。",
    "邻居阿姨开着隔壁的咖啡店。有时候她会给我们带咖啡。",
    "有人推门进来，爸爸就笑着说：",
    "进来吧！",
    "我也跟着说！",
    "我每天都在这里学一句新英语。明天再来听理发店里的小故事吧。",
    "明天见！",
]


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    whole, fraction = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02},{fraction:03}"


def main() -> None:
    output = ROOT / "outputs/ep000_daily"
    video = output / "final.mp4"
    if not video.is_file() or video.stat().st_size < 100_000:
        raise RuntimeError(f"未找到已导出的成片：{video}")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                           capture_output=True, text=True, check=True)
    duration = float(probe.stdout.strip())
    if not 39.3 <= duration <= 40.0:
        raise RuntimeError(f"成片时长异常：{duration:.2f}s")

    story = {
        "schema_version": 1,
        "series_id": "xiangwei",
        "record_type": "story",
        "format": "series_intro",
        "id": "ST000",
        "day": 0,
        "title": "老爸的英语理发店",
        "intro": "四岁女儿带你认识爸爸的美国理发店。",
        "premise": "四岁女儿用英语介绍爸爸在美国开的社区理发店、常来的熟客和邻店老板，并邀请观众每天跟着她学习一句生活英语。",
        "event_key": "daughter_introduces_barbershop",
        "category": "intro",
        "setting": "shop",
        "language": "en-US",
        "subtitle_languages": ["en", "zh-CN"],
        "participants": ["daughter", "dad", "commuter_regular", "retired_regular", "neighbor_owner"],
        "core_expression": "Come on in!",
        "meaning": "进来吧！",
        "beats": ["女儿介绍爸爸和店铺", "介绍常来的顾客和邻居", "爸爸迎客说 Come on in!", "女儿邀请观众明天再来"],
        "payoff": "女儿也学着爸爸说 Come on in!，邀请观众继续听故事。",
        "voiceover": [line for _, line, _, _ in LINES],
        "voiceover_zh": TRANSLATIONS,
        "continuity_in": [],
        "continuity_out": ["女儿的画留在玩具角", "米勒先生养狗米洛", "艾玛经常赶时间"],
        "status": "produced",
        "episode_ids": ["ep000_daily"],
    }
    stories.validate(story)
    existing = stories.read_catalog(ROOT)
    findings = stories.check_candidate(ROOT, story, exclude_id="ST000" if any(item["id"] == "ST000" for item in existing) else None)
    if findings:
        raise RuntimeError("系列开场与故事库重复：" + "；".join(findings))
    stories.write_catalog(ROOT, [story] + [item for item in existing if item["id"] != "ST000"])

    episode = ROOT / "episodes/ep000_daily"
    episode.mkdir(parents=True, exist_ok=True)
    shots = [{"id": "opening", "start": 0, "duration": 3.6, "asset": "videos/intro/assets/video/opening.mp4"}]
    shots.extend({"id": key, "start": start, "duration": clip_duration,
                  "asset": f"videos/intro/assets/stills/{file}"}
                 for key, start, clip_duration, file, *_ in SCENES)
    (episode / "episode.json").write_text(json.dumps({
        "id": "ep000_daily", "series_id": "xiangwei", "story_id": "ST000",
        "title": story["title"], "intro": story["intro"],
        "language": "en-US", "subtitle_languages": ["en", "zh-CN"],
        "source_project": "videos/intro", "shots": shots,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    selected = {shot["id"]: shot["asset"] for shot in shots}
    (output / "generation_manifest.json").write_text(json.dumps({
        "updated_at": now, "selected": selected,
        "jobs": {
            "stills": {"status": "ready", "started_at": now},
            "english_voice": {"status": "ready", "started_at": now, "provider": VOICE_PROFILE["provider"], "voice_id": VOICE_PROFILE["voice_id"]},
            "bilingual_captions": {"status": "ready", "started_at": now},
            "final_render": {"status": "ready", "started_at": now},
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    subtitles = [(start, start + length, en, zh) for start, length, en, zh in CAPTIONS]
    subtitles += [(25.38, 26.86, "Come on in!", "进来吧！"),
                  (35.79, 37.67, "See you tomorrow!", "明天见！")]
    subtitles.sort(key=lambda item: item[0])
    (output / "subtitles.srt").write_text("\n".join(
        f"{index}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{en}\n{zh}\n"
        for index, (start, end, en, zh) in enumerate(subtitles, 1)
    ), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.7", "-i", str(video),
                    "-frames:v", "1", str(output / "cover.png")], check=True)
    print(f"ST000 登记完成；成片 {duration:.2f}s；双语字幕 {len(subtitles)} 条。")


if __name__ == "__main__":
    main()
