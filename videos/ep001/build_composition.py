"""Rebuild ST001 limited animation from the global story and actual voice durations."""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def story():
    for row in (ROOT / "series/xiangwei/stories.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(row)
        if item.get("id") == "ST001":
            return item
    raise RuntimeError("ST001 missing")


def inputs():
    data = story()
    voices = json.loads((HERE / "assets/voice/manifest.json").read_text(encoding="utf-8"))
    lines = data["dialogue"] + [
        {"speaker": "dad", "en": data["core_expression"], "zh": data["meaning"]},
        {"speaker": "dad", "en": data["variant"], "zh": data["variant_meaning"]},
    ]
    if len(data["dialogue"]) != 10 or len(voices) != 12:
        raise RuntimeError("Expected 10 dialogue lines, a repeat and a variant")
    for i, (line, voice) in enumerate(zip(lines, voices), 1):
        if any(line[k] != voice[k] for k in ("speaker", "en", "zh")):
            raise RuntimeError(f"Voice {i:02d} is stale; run generate_voice.py")
        if not (HERE / voice["path"]).is_file():
            raise RuntimeError(f"Voice file {i:02d} missing")
    return data, voices, lines


def times(data, voices):
    starts, ends = [], []
    at = 0.12
    for line, voice in zip(data["dialogue"], voices[:10]):
        starts.append(round(at, 3))
        end = round(at + voice["duration"], 3)
        ends.append(end)
        at = end + float(line["pause_after"])
    card_start = round(at, 3)
    card = data["learning_card"]
    total = round(card_start + float(card["duration"]), 3)
    voice_starts = starts + [
        round(card_start + float(card["repeat_at"]), 3),
        round(card_start + float(card["variant_at"]) + 0.35, 3),
    ]
    if voice_starts[-1] + voices[-1]["duration"] > total - 0.8:
        raise RuntimeError("Variant needs a follow-along pause")
    return starts, ends, card_start, total, voice_starts


def sh(asset, at, scale=1.02, x=0, y=0):
    # Keep the source image covering the 1080x1920 frame throughout its small move.
    x_limit = max(0, (scale - 1) * 1080 / 2 - 8)
    y_limit = max(0, (scale - 1) * 1920 / 2 - 8)
    x = max(-x_limit, min(x_limit, x))
    y = max(-y_limit, min(y_limit, y))
    return {"src": "assets/" + asset, "at": round(at, 3), "scale": scale,
            "x": round(x, 2), "y": round(y, 2)}


def scenes(starts, ends, card_start, total):
    return [
        ("arrival", 0, starts[1], [
            sh("stills/01_miller_arrives-daughter.jpg", 0),
            sh("motion/arrival-asks-daughter.jpg", .58, 1.46, 335, 420)]),
        ("confession", starts[1], starts[3], [
            sh("stills/02_miller_confesses-daughter.jpg", 0, 1.52, -335, 420),
            sh("motion/confession-shy-daughter.jpg", starts[2]-starts[1], 1.48, 350, 410),
            sh("stills/03_dad_encourages-daughter.jpg", ends[2]-starts[1]+.12, 1.52, -335, 420)]),
        ("surprise", starts[3], starts[5], [
            sh("motion/confession-shy-daughter.jpg", 0, 1.55, -350, 430),
            sh("stills/03_dad_encourages-daughter.jpg", starts[4]-starts[3], 1.46, 340, 405)]),
        ("encourage", starts[5], starts[6], [
            sh("stills/03_dad_encourages-daughter.jpg", 0, 1.35, -235, 310),
            sh("motion/phone-raise-daughter.jpg", ends[5]-starts[5]+.12, 1.04)]),
        ("call", starts[6], starts[8], [
            sh("stills/04_miller_calls-right-hand.jpg", 0, 1.35, 15, 325),
            sh("stills/04_daughter_reacts-right-hand.jpg", starts[7]-starts[6], 1.03)]),
        ("answer", starts[8], card_start, [
            sh("stills/05_dad_hurries-daughter.jpg", 0, 1.45, 350, 385),
            sh("motion/chair-invite-daughter.jpg", starts[9]-starts[8], 1.03)]),
        ("phrase", card_start, total, [
            sh("motion/chair-invite-daughter.jpg", 0, 1.03)]),
    ]


def scene_html(name, duration, shots):
    if shots[0]["at"] != 0 or any(p["at"] < 0 or p["at"] >= duration for p in shots):
        raise RuntimeError(f"Bad shot timing: {name}")
    root = f"scene-{name}-root"
    images = "\n".join(
        f'<img id="scene-{name}-shot-{i}" src="{p["src"]}" alt="{name} shot {i+1}">'
        for i, p in enumerate(shots))
    poses = json.dumps([{k: p[k] for k in ("at", "scale", "x", "y")} for p in shots])
    return f'''<!doctype html><html lang="en"><body><template>
<style>
#{root}{{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:#251f18}}
#{root} img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transform-origin:50% 50%;will-change:transform,opacity}}
#{root} img:first-child{{opacity:1}}
</style>
<div id="{root}" data-composition-id="scene-{name}" data-width="1080" data-height="1920" data-duration="{duration:.3f}" data-layout-allow-overflow>{images}</div>
<script>(function(){{
const poses={poses}, tl=gsap.timeline({{paused:true}});
poses.forEach((p,i)=>{{
 const id="#scene-{name}-shot-"+i;
 const until=i+1<poses.length?poses[i+1].at:{duration:.3f};
 tl.fromTo(id,{{scale:p.scale,x:p.x,y:p.y}},{{scale:p.scale+.012,x:p.x+3,y:p.y-3,duration:Math.max(.1,until-p.at),ease:"sine.inOut",immediateRender:false}},p.at);
 if(i){{tl.set("#scene-{name}-shot-"+(i-1),{{opacity:0}},p.at);tl.set(id,{{opacity:1}},p.at);}}
}});
window.__timelines["scene-{name}"]=tl;
}})();</script></template></body></html>'''


def captions_html(data, voices, starts, card_start, total):
    names = {"dad": "DAD", "retired_regular": "MR. MILLER", "daughter": "DAUGHTER"}
    blocks = []
    core = html.escape(data["core_expression"])
    for i, (line, voice) in enumerate(zip(data["dialogue"], voices[:10]), 1):
        en = html.escape(line["en"]).replace(core, f"<em>{core}</em>")
        blocks.append(
            f'<div id="caption-{i:02d}" class="clip caption" data-start="{max(0, starts[i-1]-.05):.3f}" '
            f'data-duration="{voice["duration"]+.23:.3f}" data-track-index="0"><div class="caption-copy">'
            f'<span class="speaker">{names[line["speaker"]]}</span><span class="english">{en}</span>'
            f'<span class="chinese">{html.escape(line["zh"])}</span></div></div>')
    card = data["learning_card"]
    variant_at = card_start + float(card["variant_at"])
    variant = html.escape(data["variant"])
    return f'''<!doctype html><html lang="en"><body><template>
<style>
#captions-root{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;color:#fff9ec;font-family:system-ui,-apple-system,sans-serif}}
#captions-root .shade{{position:absolute;left:0;right:0;bottom:0;height:690px;background:linear-gradient(to top,rgba(22,17,13,.91),rgba(22,17,13,.48) 58%,transparent)}}
#captions-root .clip{{position:absolute;inset:0}}
#captions-root .caption{{display:flex;align-items:flex-end;justify-content:center;padding:0 76px 232px}}
#captions-root .caption-copy{{max-width:928px;text-align:center;text-shadow:0 3px 0 #241b15,3px 0 #241b15,-3px 0 #241b15,0 8px 26px #000}}
#captions-root .speaker{{display:inline-block;margin-bottom:18px;padding:7px 15px;border-radius:8px;background:rgba(35,25,17,.83);color:#f3c581;font-size:24px;font-weight:800;letter-spacing:.1em}}
#captions-root .english{{display:block;font-size:51px;line-height:1.19;font-weight:800}}
#captions-root .english em{{font-style:normal;color:#ffda93;text-decoration:underline;text-decoration-color:#f3b957;text-underline-offset:7px}}
#captions-root .chinese{{display:block;margin-top:13px;font-size:39px;line-height:1.22;font-weight:720;color:#f6dbad}}
#captions-root .phrase-card{{display:flex;align-items:flex-end;justify-content:center;padding:0 70px 335px}}
#captions-root .phrase-inner{{width:100%;border:2px solid rgba(243,197,129,.75);border-radius:30px;background:rgba(31,24,19,.93);padding:36px 30px 42px;text-align:center;box-shadow:0 20px 55px rgba(0,0,0,.35)}}
#captions-root .phrase-kicker{{display:block;color:#f3c581;font-size:28px;font-weight:780;letter-spacing:.14em;margin-bottom:18px}}
#captions-root .phrase-en{{display:block;font-size:65px;line-height:1.12;font-weight:850;letter-spacing:-.025em}}
#captions-root .phrase-en em{{color:#f3c581;font-style:normal}}
#captions-root .phrase-zh{{display:block;margin-top:19px;color:#f3c581;font-size:46px;font-weight:750}}
#captions-root .follow{{display:block;margin-top:23px;color:#fff0d8;font-size:31px;font-weight:650}}
</style>
<div id="captions-root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="{total:.3f}">
<div class="shade"></div>{''.join(blocks)}
<div id="phrase-card" class="clip phrase-card" data-start="{card_start:.3f}" data-duration="{variant_at-card_start:.3f}" data-track-index="0"><div class="phrase-inner">
<span class="phrase-kicker">TODAY'S ENGLISH</span><span class="phrase-en">{core}</span><span class="phrase-zh">{html.escape(data["meaning"])}</span>
<span class="follow">{html.escape(card["repeat_prompt"])}</span></div></div>
<div id="variant-card" class="clip phrase-card" data-start="{variant_at:.3f}" data-duration="{total-variant_at:.3f}" data-track-index="0"><div class="phrase-inner">
<span class="phrase-kicker">SAY IT YOUR WAY</span><span class="phrase-en">{variant}</span>
<span class="phrase-zh">{html.escape(data["variant_meaning"])}</span><span class="follow">{html.escape(card["variant_prompt"])}</span></div></div>
</div>
<script>(function(){{
const tl=gsap.timeline({{paused:true}});
document.querySelectorAll("#captions-root .caption").forEach(c=>{{const t=Number(c.dataset.start);
tl.fromTo(c.querySelector(".caption-copy"),{{opacity:0,y:12}},{{opacity:1,y:0,duration:.2,ease:"power2.out",immediateRender:false}},t+.02);}});
for(const id of ["phrase-card","variant-card"]){{const c=document.getElementById(id);
tl.fromTo(c.querySelector(".phrase-inner"),{{opacity:0,y:14}},{{opacity:1,y:0,duration:.27,ease:"power2.out",immediateRender:false}},Number(c.dataset.start)+.04);}}
window.__timelines["captions"]=tl;
}})();</script></template></body></html>'''


def srt_time(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    data, voices, lines = inputs()
    starts, ends, card_start, total, voice_starts = times(data, voices)
    specs = scenes(starts, ends, card_start, total)
    comps = HERE / "compositions"
    comps.mkdir(exist_ok=True)
    hosts = []
    for track, (name, start, end, shots) in enumerate(specs):
        (comps / f"scene-{name}.html").write_text(scene_html(name, end-start, shots), encoding="utf-8")
        hosts.append(f'<div id="scene-{name}" class="clip scene-host" data-composition-id="scene-{name}" data-composition-src="compositions/scene-{name}.html" data-start="{start:.3f}" data-duration="{end-start:.3f}" data-track-index="{track}" data-track-kind="graphics" data-width="1080" data-height="1920"></div>')
    (comps / "captions.html").write_text(captions_html(data, voices, starts, card_start, total), encoding="utf-8")
    audio = [f'<audio id="music" src="assets/audio/music_box.wav" data-start="0" data-duration="{total:.3f}" data-track-index="30" data-volume="0.10"></audio>']
    for i, voice in enumerate(voices):
        audio.append(f'<audio id="voice-{voice["id"]}" src="{voice["path"]}" data-audio-group="voiceover" data-start="{voice_starts[i]:.3f}" data-duration="{voice["duration"]:.3f}" data-track-index="31" data-volume="1"></audio>')
    page = f'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1">
<title>老爸的英语理发店 · {html.escape(data["title"])}</title><script src="assets/vendor/gsap.min.js"></script>
<style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#251f18}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#251f18}}.clip{{position:absolute;inset:0}}
.scene-host{{overflow:hidden}}.brand{{inset:112px auto auto 72px;height:auto;width:auto;padding:14px 20px;border-radius:14px;background:rgba(25,18,13,.91);color:#fff9ec;font-family:system-ui,-apple-system,sans-serif;font-size:31px;font-weight:800;letter-spacing:.05em;text-shadow:0 3px 12px #201810}}
.brand span{{display:block;width:160px;height:4px;margin-top:13px;background:#f3c581;border-radius:2px}}</style></head>
<body><div id="root" data-composition-id="ep001" data-start="0" data-duration="{total:.3f}" data-width="1080" data-height="1920">
{''.join(hosts)}
<div id="brand" class="clip brand" data-start="0" data-duration="{card_start:.3f}" data-track-index="10">老爸的英语理发店<span></span></div>
<div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" data-track-index="20" data-track-kind="captions" data-width="1080" data-height="1920"></div>
{''.join(audio)}
</div><script>window.__timelines["ep001"]=gsap.timeline({{paused:true}});</script></body></html>'''
    (HERE / "index.html").write_text(page, encoding="utf-8")
    subtitles = []
    for i, (line, voice) in enumerate(zip(lines, voices), 1):
        begin = max(0, voice_starts[i-1]-.05)
        end = min(total, voice_starts[i-1]+voice["duration"]+.2)
        subtitles.append(f"{i}\n{srt_time(begin)} --> {srt_time(end)}\n{line['en']}\n{line['zh']}\n")
    (HERE / "subtitles_bilingual.srt").write_text("\n".join(subtitles), encoding="utf-8")
    meta = {"scenes": [[name, round(start,3), round(end-start,3), [p["src"] for p in shots]] for name,start,end,shots in specs],
            "dialogue_starts": starts, "dialogue_ends": ends, "voice_starts": voice_starts,
            "card_start": card_start, "duration": total}
    (HERE / "timing.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Built {HERE / 'index.html'} ({total:.2f}s, {len(specs)} animated scenes, {len(voices)} voice clips)")


if __name__ == "__main__":
    main()
