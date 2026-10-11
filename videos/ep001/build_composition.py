"""Build ST001 from the global story and the local Kokoro voice manifest."""

from __future__ import annotations

import html
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
GAPS = [0.42, 0.36, 0.62, 0.35, 0.42, 0.72, 1.65, 0.44, 0.50, 0.52]
CARD_SECONDS = 4.8


def story() -> dict:
    for line in (ROOT / "series/xiangwei/stories.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["id"] == "ST001":
            return item
    raise RuntimeError("ST001 is missing")


def timing(manifest: list[dict]) -> tuple[list[float], float, float]:
    starts = []
    at = 0.12
    for index, item in enumerate(manifest[:10]):
        starts.append(round(at, 3))
        at += item["duration"] + GAPS[index]
    card_start = round(at, 3)
    starts.append(round(card_start + 0.42, 3))
    return starts, card_start, round(card_start + CARD_SECONDS, 3)


def scene_html(name: str, duration: float, image: str, scale_a: float, scale_b: float,
               x: int, y: int) -> str:
    scene_id = f"scene-{name}"
    root_id = f"{scene_id}-root"
    return f'''<!doctype html><html lang="en"><body><template>
<style>
#{root_id}{{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:#251f18}}
#{root_id} img{{display:block;width:100%;height:100%;object-fit:cover;object-position:center center;transform-origin:50% 50%;will-change:transform}}
</style>
<div id="{root_id}" data-composition-id="{scene_id}" data-width="1080" data-height="1920" data-duration="{duration:.3f}" data-layout-allow-overflow>
  <img src="assets/stills/{image}" alt="{name}">
</div>
<script>(function(){{
const tl=gsap.timeline({{paused:true}});
tl.fromTo("#{root_id} img",{{scale:{scale_a},x:0,y:0}},{{scale:{scale_b},x:{x},y:{y},duration:{duration:.3f},ease:"sine.inOut"}},0);
window.__timelines["{scene_id}"]=tl;
}})();</script>
</template></body></html>'''


def captions_html(data: dict, manifest: list[dict], starts: list[float],
                  card_start: float, total: float) -> str:
    captions = []
    for index, line in enumerate(data["dialogue"]):
        start = max(0, starts[index] - 0.08)
        duration = manifest[index]["duration"] + 0.30
        captions.append(f'''<div id="caption-{index+1:02d}" class="clip caption" data-start="{start:.3f}" data-duration="{duration:.3f}" data-track-index="0">
<div class="caption-copy"><span class="english">{html.escape(line['en'])}</span><span class="chinese">{html.escape(line['zh'])}</span></div></div>''')
    phrase = html.escape(data["core_expression"])
    meaning = html.escape(data["meaning"])
    return f'''<!doctype html><html lang="en"><body><template>
<style>
#captions-root{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;color:#fff9ec;font-family:system-ui,-apple-system,sans-serif}}
#captions-root .shade{{position:absolute;left:0;right:0;bottom:0;height:660px;background:linear-gradient(to top,rgba(22,17,13,.91),rgba(22,17,13,.52) 57%,transparent)}}
#captions-root .clip{{position:absolute;inset:0}}
#captions-root .caption{{display:flex;align-items:flex-end;justify-content:center;padding:0 76px 240px}}
#captions-root .caption-copy{{max-width:928px;text-align:center;text-shadow:0 3px 0 #241b15,3px 0 #241b15,-3px 0 #241b15,0 8px 26px #000}}
#captions-root .english{{display:block;font-size:51px;line-height:1.2;font-weight:800}}
#captions-root .chinese{{display:block;margin-top:13px;font-size:39px;line-height:1.22;font-weight:720;color:#f6dbad}}
#captions-root .phrase-card{{display:flex;align-items:flex-end;justify-content:center;padding:0 70px 340px}}
#captions-root .phrase-inner{{width:100%;border:2px solid rgba(243,197,129,.70);border-radius:30px;background:rgba(31,24,19,.9);padding:36px 30px 42px;text-align:center;box-shadow:0 20px 55px rgba(0,0,0,.35)}}
#captions-root .phrase-kicker{{display:block;color:#f3c581;font-size:28px;font-weight:780;letter-spacing:.14em;margin-bottom:18px}}
#captions-root .phrase-en{{display:block;font-size:68px;line-height:1.11;font-weight:850;letter-spacing:-.025em}}
#captions-root .phrase-zh{{display:block;margin-top:19px;color:#f3c581;font-size:48px;font-weight:750}}
#captions-root .follow{{display:block;margin-top:23px;color:#fff0d8;font-size:31px;font-weight:650}}
</style>
<div id="captions-root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="{total:.3f}">
  <div class="shade"></div>
  {''.join(captions)}
  <div id="phrase-card" class="clip phrase-card" data-start="{card_start:.3f}" data-duration="{CARD_SECONDS:.3f}" data-track-index="0"><div class="phrase-inner">
    <span class="phrase-kicker">TODAY'S ENGLISH</span><span class="phrase-en">{phrase}</span>
    <span class="phrase-zh">{meaning}</span><span class="follow">跟着说一遍 · Say it with us</span>
  </div></div>
</div>
<script>(function(){{
const tl=gsap.timeline({{paused:true}});
document.querySelectorAll("#captions-root .caption").forEach(c=>{{const t=Number(c.dataset.start);
tl.fromTo(c.querySelector(".caption-copy"),{{opacity:0,y:16}},{{opacity:1,y:0,duration:.23,ease:"power2.out",immediateRender:false}},t+.02);}});
tl.fromTo("#phrase-card .phrase-inner",{{opacity:0,scale:.96,y:14}},{{opacity:1,scale:1,y:0,duration:.38,ease:"power3.out",immediateRender:false}},{card_start + 0.08:.3f});
window.__timelines["captions"]=tl;
}})();</script>
</template></body></html>'''


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def main() -> None:
    data = story()
    manifest = json.loads((PROJECT / "assets/voice/manifest.json").read_text(encoding="utf-8"))
    if len(data["dialogue"]) != 10 or len(manifest) != 11:
        raise RuntimeError("ST001 dialogue and voice manifest do not match")
    expected = data["dialogue"] + [{"en": data["core_expression"], "zh": data["meaning"]}]
    if any(item["en"] != line["en"] or item["zh"] != line["zh"] for item, line in zip(manifest, expected)):
        raise RuntimeError("Voice manifest is stale; regenerate from the global story")
    starts, card_start, total = timing(manifest)
    scene_specs = [
        ("arrival", 0.0, starts[1], "01_miller_arrives.jpg", 1.01, 1.05, -9, -4),
        ("confession", starts[1], starts[3], "02_miller_confesses.jpg", 1.01, 1.06, -12, -6),
        ("surprise", starts[3], starts[4], "01_miller_arrives.jpg", 1.05, 1.09, 6, -5),
        ("encourage", starts[4], starts[6], "03_dad_encourages.jpg", 1.02, 1.08, -10, -7),
        ("call", starts[6], starts[8], "04_miller_calls.jpg", 1.01, 1.08, -8, -9),
        ("answer", starts[8], card_start, "05_dad_hurries.jpg", 1.01, 1.06, -9, -5),
        ("phrase", card_start, total, "05_dad_hurries.jpg", 1.06, 1.03, 6, 3),
    ]
    scenes = [(name, round(a, 3), round(b-a, 3), img, sa, sb, x, y)
              for name, a, b, img, sa, sb, x, y in scene_specs]
    comps = PROJECT / "compositions"
    comps.mkdir(exist_ok=True)
    hosts = []
    for track, (name, start, duration, asset, a, b, x, y) in enumerate(scenes):
        scene_id = f"scene-{name}"
        (comps / f"{scene_id}.html").write_text(scene_html(name, duration, asset, a, b, x, y), encoding="utf-8")
        hosts.append(f'<div id="{scene_id}" class="clip scene-host" data-composition-id="{scene_id}" data-composition-src="compositions/{scene_id}.html" data-start="{start:.3f}" data-duration="{duration:.3f}" data-track-index="{track}" data-track-kind="graphics" data-width="1080" data-height="1920"></div>')
    (comps / "captions.html").write_text(captions_html(data, manifest, starts, card_start, total), encoding="utf-8")
    audios = [f'<audio id="music" src="assets/audio/music_box.wav" data-start="0" data-duration="{total:.3f}" data-track-index="30" data-volume="0.13"></audio>']
    for index, item in enumerate(manifest):
        audios.append(f'<audio id="voice-{item["id"]}" src="{item["path"]}" data-audio-group="voiceover" data-start="{starts[index]:.3f}" data-duration="{item["duration"]:.3f}" data-track-index="31" data-volume="1"></audio>')
    html_text = f'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1">
<title>老爸的英语理发店 · {html.escape(data['title'])}</title><script src="assets/vendor/gsap.min.js"></script>
<style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#251f18}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#251f18}}.clip{{position:absolute;inset:0}}
.scene-host{{overflow:hidden}}.brand{{inset:112px auto auto 72px;height:auto;width:auto;padding:14px 20px;border-radius:14px;background:rgba(25,18,13,.91);color:#fff9ec;font-family:system-ui,-apple-system,sans-serif;font-size:31px;font-weight:800;letter-spacing:.05em;text-shadow:0 3px 12px #201810}}
.brand span{{display:block;width:160px;height:4px;margin-top:13px;background:#f3c581;border-radius:2px}}</style></head>
<body><div id="root" data-composition-id="ep001" data-start="0" data-duration="{total:.3f}" data-width="1080" data-height="1920">
{''.join(hosts)}
<div id="brand" class="clip brand" data-start="0" data-duration="{card_start:.3f}" data-track-index="10">老爸的英语理发店<span></span></div>
<div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" data-track-index="20" data-track-kind="captions" data-width="1080" data-height="1920"></div>
{''.join(audios)}
</div><script>window.__timelines["ep001"]=gsap.timeline({{paused:true}});</script></body></html>'''
    (PROJECT / "index.html").write_text(html_text, encoding="utf-8")
    subtitles = []
    for index, item in enumerate(manifest):
        start = max(0, starts[index]-0.08)
        end = min(total, start + item["duration"] + (0.30 if index < 10 else 0.40))
        subtitles.append(f"{index+1}\n{srt_time(start)} --> {srt_time(end)}\n{item['en']}\n{item['zh']}\n")
    (PROJECT / "subtitles_bilingual.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (PROJECT / "timing.json").write_text(json.dumps({"scenes": scenes, "voice_starts": starts,
                   "card_start": card_start, "duration": total}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Built {PROJECT / 'index.html'} ({total:.2f}s, {len(scenes)} scenes, {len(manifest)} voice clips)")


if __name__ == "__main__":
    main()
