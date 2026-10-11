"""Assemble the verified stills, motion opener and voice clips into HyperFrames."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCENES = [
    ("hold", 3.60, 2.10, "opening_hold.png", "父女站在理发店门前", 1.01, 1.08, -12, -8),
    ("chair", 5.70, 5.08, "scene_02b.png", "爸爸和女儿在理发椅旁", 1.02, 1.09, -15, -6),
    ("commuter", 10.78, 2.97, "scene_03.png", "上班族熟客走进店里", 1.04, 1.11, -12, -8),
    ("retiree", 13.75, 3.17, "scene_04b.png", "退休熟客讲故事", 1.22, 1.28, -18, -34),
    ("neighbor", 16.92, 4.45, "scene_05b.png", "邻店老板带咖啡来串门", 1.03, 1.10, -12, -8),
    ("welcome", 21.37, 7.28, "scene_01.jpg", "爸爸打开店门迎客", 1.03, 1.11, -14, -12),
    ("drawing", 28.65, 7.03, "scene_06.png", "女儿把画给爸爸看", 1.02, 1.10, 14, -10),
    ("closing", 35.68, 3.92, "scene_01.jpg", "父女站在店门前", 1.05, 1.12, -10, -10),
]
CAPTIONS = [
    (0.25, 2.42, "My dad has a barbershop here in America.", "我爸爸在美国开了一家理发店。"),
    (2.67, 2.42, "After school, I come right here.", "放学后，我就来这里。"),
    (5.80, 1.75, "Dad has a big barber chair.", "爸爸有一把大大的理发椅。"),
    (7.55, 2.05, "And I have a little toy corner.", "我有一个小小的玩具角。"),
    (10.88, 2.10, "Emma is always in a hurry.", "艾玛总是有点赶时间。"),
    (12.98, 3.15, "Mr. Miller loves talking about his dog, Milo.", "米勒爷爷爱讲他的小狗米洛。"),
    (17.02, 2.10, "Our neighbor runs the coffee shop.", "邻居阿姨开着隔壁的咖啡店。"),
    (19.12, 2.10, "Sometimes she brings us coffee.", "有时候她会给我们带咖啡。"),
    (21.70, 3.58, "When someone opens the door, Dad smiles and says:", "有人推门进来，爸爸就笑着说："),
    (26.95, 1.69, "I say it, too!", "我也跟着说！"),
    (28.78, 2.83, "I learn a new English phrase here every day.", "我每天都在这里学一句新英语。"),
    (31.61, 3.14, "Come back tomorrow for another little story from our shop.", "明天再来听理发店里的小故事吧。"),
]
AUDIO_STARTS = {"01": 0.25, "02": 5.80, "03": 10.88, "04": 17.02, "05a": 21.70,
                "05b": 25.38, "05c": 26.95, "06": 28.78, "07": 35.79}

STYLE = """
*{box-sizing:border-box} html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:#251f18}
body{font-family:system-ui,-apple-system,sans-serif;color:#fff9ec} #root{position:relative;width:100%;height:100%;overflow:hidden;background:#251f18}
.clip{position:absolute;inset:0}.scene,.opening{overflow:hidden;background:#251f18}.camera{position:absolute;inset:0;transform-origin:50% 50%;will-change:transform}
.camera img,.opening{width:100%;height:100%;object-fit:cover;display:block}.retiree .camera{transform-origin:50% 35%}
.shade{position:absolute;inset:auto 0 0;height:700px;background:linear-gradient(to top,rgba(22,17,13,.88),rgba(22,17,13,.45) 54%,transparent);pointer-events:none}
.brand{top:78px;left:72px;right:72px;bottom:auto;display:flex;justify-content:space-between;align-items:center;font-size:31px;font-weight:780;letter-spacing:.05em;text-shadow:0 3px 12px #201810}
.brand:after{content:'';position:absolute;left:0;top:54px;width:165px;height:4px;background:#f3c581;border-radius:2px}
.caption{display:flex;align-items:flex-end;justify-content:center;padding:0 78px 245px;pointer-events:none}
.caption-text{max-width:924px;text-align:center;color:#fff9ec;text-shadow:0 3px 0 #241b15,3px 0 #241b15,-3px 0 #241b15,0 8px 26px #000}
.caption-text .english{display:block;font-size:55px;line-height:1.24;font-weight:820}
.caption-text .chinese{display:block;margin-top:14px;font-size:42px;line-height:1.25;font-weight:720;color:#f6dbad}
.phrase{display:flex;align-items:flex-end;justify-content:center;padding:0 70px 330px;pointer-events:none}.phrase-inner{text-align:center;text-shadow:0 5px 22px #000}
.phrase .english{display:block;font-size:106px;line-height:1.08;font-weight:850;letter-spacing:-.04em}.phrase .translation{display:block;margin-top:22px;font-size:54px;font-weight:750;color:#f3c581}
.end-card{display:flex;align-items:flex-end;padding:0 72px 276px;background:linear-gradient(to top,rgba(20,17,13,.72),transparent 58%)}
.end-content{max-width:930px;text-shadow:0 5px 25px #000}.end-content .small{display:block;color:#f3c581;font-size:29px;font-weight:760;letter-spacing:.14em;margin-bottom:24px}
.end-content h1{margin:0;font-size:89px;line-height:1.12;font-weight:850}.end-content .cn-title{display:block;margin-top:14px;font-size:47px;font-weight:740;color:#f3c581}
.end-content .tagline{margin:28px 0 0;max-width:850px;font-size:43px;line-height:1.27;font-weight:650}.end-content .cn-tagline{display:block;margin-top:12px;font-size:35px;color:#f6dbad}
.end-content .bye{margin:34px 0 0;font-size:49px;font-weight:760;color:#f3c581}.end-content .bye span{display:block;font-size:34px;margin-top:8px}
"""


def main() -> None:
    manifest = json.loads((ROOT / "assets/voice/manifest.json").read_text(encoding="utf-8"))
    scenes = ['<video id="opening" class="clip opening" src="assets/video/opening.mp4" muted playsinline data-start="0" data-duration="3.6" data-track-index="0"></video>']
    for key, start, duration, file, alt, *_ in SCENES:
        scenes.append(f'<section id="{key}" class="clip scene {key}" data-start="{start}" data-duration="{duration}" data-track-index="0"><div class="camera"><img src="assets/stills/{file}" alt="{alt}"></div></section>')
    captions = [f'<div id="caption-{index:02d}" class="clip caption" data-start="{start}" data-duration="{duration}" data-track-index="3"><div class="caption-text"><span class="english">{html.escape(en)}</span><span class="chinese">{html.escape(zh)}</span></div></div>'
                for index, (start, duration, en, zh) in enumerate(CAPTIONS, 1)]
    audios = ['<audio id="music" src="assets/audio/music_box.wav" data-start="0" data-duration="39.5" data-track-index="10" data-volume="1"></audio>']
    for item in manifest:
        key = item["id"]
        audios.append(f'<audio id="voice-{key}" src="{item["path"]}" data-start="{AUDIO_STARTS[key]}" data-duration="{item["duration"]}" data-track-index="11" data-volume="1"></audio>')
    motion = []
    for key, start, duration, _, _, first, last, x, y in SCENES:
        settle = min(1.25, duration * 0.3)
        motion.append(f'''tl.fromTo("#{key} .camera",{{scale:{first},x:0,y:0}},{{scale:{(first+last)/2:.4f},x:{x*.35:.2f},y:{y*.35:.2f},duration:{settle:.3f},ease:"power2.out",immediateRender:false}},{start});
tl.to("#{key} .camera",{{scale:{last},x:{x},y:{y},duration:{duration-settle:.3f},ease:"sine.inOut"}},{start+settle:.3f});''')
    html_text = f'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>Dad's English Barbershop</title><script src="assets/vendor/gsap.min.js"></script><style>{STYLE}</style></head>
<body><div id="root" data-composition-id="intro" data-start="0" data-duration="39.6" data-width="1080" data-height="1920">
{''.join(scenes)}<div class="shade"></div>
<div id="brand" class="clip brand" data-start="0" data-duration="35.68" data-track-index="2"><span>老爸的英语理发店</span></div>
{''.join(captions)}
<div id="welcome-phrase" class="clip phrase" data-start="25.38" data-duration="1.48" data-track-index="4"><div class="phrase-inner"><span class="english">Come on in!</span><span class="translation">进来吧！</span></div></div>
<div id="end-card" class="clip end-card" data-start="35.68" data-duration="3.92" data-track-index="5"><div class="end-content"><span class="small">SERIES INTRO</span><h1>Dad's English Barbershop</h1><span class="cn-title">老爸的英语理发店</span><p class="tagline">A story a day. English along the way.<span class="cn-tagline">每天一个故事，一起学生活英语。</span></p><p class="bye">See you tomorrow!<span>明天见！</span></p></div></div>
{''.join(audios)}</div>
<script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});
{''.join(motion)}
document.querySelectorAll('.caption').forEach(c=>{{let t=Number(c.dataset.start);tl.fromTo(c.querySelector('.caption-text'),{{opacity:0,y:24}},{{opacity:1,y:0,duration:.34,ease:'power2.out',immediateRender:false}},t+.02)}});
tl.fromTo('.phrase-inner',{{opacity:0,y:32,scale:.96}},{{opacity:1,y:0,scale:1,duration:.42,ease:'power3.out',immediateRender:false}},25.38);
tl.fromTo('.end-content',{{opacity:0,y:56}},{{opacity:1,y:0,duration:.62,ease:'power3.out',immediateRender:false}},35.72);
window.__timelines['intro']=tl;</script></body></html>'''
    (ROOT / "index.html").write_text(html_text, encoding="utf-8")
    (ROOT / "timing.json").write_text(json.dumps({"scenes": SCENES, "captions": CAPTIONS, "audio_starts": AUDIO_STARTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {ROOT / 'index.html'} with {len(SCENES)+1} visual clips and {len(manifest)} voice clips")


if __name__ == "__main__":
    main()
