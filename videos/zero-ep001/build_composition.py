"""Build EP01 picture, captions and sound from final recorded voice durations."""
from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from elevator.stories import ROOT, get_story, shots

PROJECT = Path(__file__).resolve().parent
VISUALS = PROJECT / 'assets/visuals'
VOICE = PROJECT / 'assets/voice'
AUDIO = PROJECT / 'assets/audio'
GSAP = PROJECT / 'assets/vendor/gsap.min.js'


def f(number: float) -> str:
    return f'{number:.3f}'


def copy_assets() -> None:
    VISUALS.mkdir(parents=True, exist_ok=True)
    for name, item in shots().items():
        shutil.copyfile(ROOT / item['path'], VISUALS / f'{name}.png')
    if not GSAP.is_file():
        raise RuntimeError(f'Missing local GSAP library: {GSAP}')


def make_soundscape(length: float, cues: list[float]) -> None:
    """Original soft music-box atmosphere; no prior-series audio is reused."""
    AUDIO.mkdir(parents=True, exist_ok=True)
    sr = 48000
    t = np.arange(math.ceil(length * sr), dtype=np.float64) / sr
    data = np.zeros(len(t), dtype=np.float64)
    chords = [(196, 233.08, 293.66), (174.61, 220, 261.63), (164.81, 196, 261.63), (196, 246.94, 293.66)]
    for index, chord in enumerate(chords):
        start = index * length / 4
        end = (index + 1) * length / 4
        active = (t >= start) & (t < end)
        local = t[active] - start
        attack = np.minimum(1, local / .8)
        release = np.minimum(1, (end - t[active]) / 1.1)
        for hz in chord:
            data[active] += .012 * attack * release * np.sin(2 * np.pi * hz * t[active])
    for cue in cues:
        start = int(cue * sr)
        n = min(int(.65 * sr), len(data) - start)
        if n <= 0: continue
        u = np.arange(n) / sr
        bell = .055 * np.exp(-5 * u) * (np.sin(2*np.pi*784*u) + .42*np.sin(2*np.pi*1176*u))
        data[start:start+n] += bell
    data = np.clip(data, -.9, .9)
    with wave.open(str(AUDIO/'soundscape.wav'), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(sr)
        out.writeframes((data * 32767).astype('<i2').tobytes())


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    h, r = divmod(millis, 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def media_duration(path: Path) -> float:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def main() -> None:
    story = get_story('EZ001')
    manifest_path = VOICE / 'manifest.json'
    if not manifest_path.is_file():
        raise RuntimeError('Generate the English voices before rebuilding the timeline')
    recordings = json.loads(manifest_path.read_text())
    expected = story['dialogue'] + [{'speaker':'lan','en':story['core_expression'],'zh':story['meaning']},
                                    {'speaker':'lan','en':story['variant'],'zh':story['variant_meaning']}]
    if len(recordings) != len(expected):
        raise RuntimeError('Voice manifest does not match story line count')
    for line, audio in zip(expected, recordings):
        if (line['speaker'], line['en'], line['zh']) != (audio['speaker'], audio['en'], audio['zh']):
            raise RuntimeError(f"Stale audio for {audio['id']}; regenerate voices first")
    copy_assets()

    timeline = []
    cursor = 0.0
    for i, (line, audio) in enumerate(zip(story['dialogue'], recordings[:len(story['dialogue'])]), 1):
        speak = float(audio['duration'])
        pause = float(line['pause_after']) * 1.3 + .25
        slot = speak + pause + (.5 if i in {3, 7, 9} else 0)
        timeline.append({'index':i,'start':round(cursor,3),'duration':round(slot,3),
                         'voice_duration':speak,'shot':line['shot'],'speaker':line['speaker'],
                         'en':line['en'],'zh':line['zh']})
        cursor += slot
    card_start = round(cursor, 3)
    card_duration = float(story['learning_card']['duration'])
    total = round(card_start + card_duration, 3)
    if story['learning_card']['repeat_at'] + recordings[-2]['duration'] > story['learning_card']['variant_at'] - .5:
        raise RuntimeError('Core phrase does not leave follow-along time')
    if story['learning_card']['variant_at'] + recordings[-1]['duration'] > card_duration - .8:
        raise RuntimeError('Variant does not leave follow-along time')
    make_soundscape(total, [0, timeline[6]['start'], timeline[7]['start'], card_start])

    visuals = []
    captions = []
    audio_tags = []
    tweens = []
    srt = []
    names = {'lan':'岚 · LAN','tick':'蒂克 · TICK','noah':'诺亚 · NOAH','sister':'妹妹 · SISTER'}
    # Story visuals are real LTX motion. The learning card is the only still frame.
    motion_segments = [
        (1, 1, 'door_rush_approved.mp4'),
        (2, 3, 'lan_holds_door_approved.mp4'),
        (4, 5, 'noah_explains_approved.mp4'),
        (6, 7, 'noah_destination_approved.mp4'),
        (8, 9, 'moon_delivery_approved.mp4'),
        (10, 10, 'moon_outro_approved.mp4'),
    ]
    for first, last, source in motion_segments:
        path = PROJECT / 'assets/ltx' / source
        if not path.is_file():
            raise RuntimeError(f'Missing approved LTX motion clip: {path}')
        start = timeline[first - 1]['start']
        end = timeline[last - 1]['start'] + timeline[last - 1]['duration']
        span = round(end - start, 3)
        rate = media_duration(path) / span
        if not .75 <= rate <= 1.35:
            raise RuntimeError(f'{source} needs an excessive playback change: {rate:.2f}x')
        visuals.append(f'<video id="motion-{first}-{last}" src="assets/ltx/{source}" data-start="{f(start)}" data-duration="{f(span)}" data-media-start="0" data-playback-rate="{rate:.4f}" data-track-index="{first-1}" data-track-kind="video" muted playsinline class="clip picture"></video>')
        visuals.append(f'<div id="scene-{first}-shade" class="clip video-vignette" data-start="{f(start)}" data-duration="{f(span)}" data-track-index="11"></div>')
    for row in timeline:
        i, start, duration = row['index'], row['start'], row['duration']
        # The timed captions all live on the single captions track.
        en = html.escape(row['en']); zh = html.escape(row['zh'])
        emphasis = ' emphasis' if 'hold the door' in row['en'].lower() else ''
        captions.append(f'<div id="caption-clip-{i}" class="clip caption" data-start="{f(start)}" data-duration="{f(duration-.08)}" data-track-index="20" data-track-kind="captions"><div id="caption-{i}" class="subtitle"><span class="speaker">{names[row["speaker"]]}</span><strong class="english{emphasis}">{en}</strong><span class="chinese">{zh}</span></div></div>')
        audio_tags.append(f'<audio id="voice-{i:02}" src="assets/voice/{i:02}.wav" data-start="{f(start)}" data-duration="{f(row["voice_duration"])}" data-track-index="30" data-volume="1"></audio>')
        tweens.append(f'tl.fromTo("#caption-{i}",{{y:22,opacity:0}},{{y:0,opacity:1,duration:0.23,ease:"power2.out",immediateRender:false}},{f(start+.04)});')
        srt.append(f'{i}\n{srt_time(start)} --> {srt_time(start+duration-.1)}\n{row["en"]}\n{row["zh"]}\n')

    card = f'''<section id="learning-card" class="clip card" data-start="{f(card_start)}" data-duration="{f(card_duration)}" data-track-index="10" data-track-kind="graphics" data-layout-allow-overflow><img src="assets/visuals/door_wide.png" alt="" class="card-picture"><div class="card-shade"></div><div class="card-body"><div class="card-kicker">SAY IT WITH THE STORY · 跟着故事开口</div><div class="card-title">今天学会这一句</div><div class="card-phrase">{html.escape(story['core_expression'])}</div><div class="card-meaning">{html.escape(story['meaning'])}</div><div class="card-prompt">听一遍 · 留给你跟读</div><div class="card-rule"></div><div class="card-variant-label">TRY ANOTHER · 换个说法</div><div class="card-variant">{html.escape(story['variant'])}</div><div class="card-variant-zh">{html.escape(story['variant_meaning'])}</div></div></section>'''
    repeat_start = card_start + story['learning_card']['repeat_at']
    variant_start = card_start + story['learning_card']['variant_at']
    for num, start, rec in ((11,repeat_start,recordings[-2]),(12,variant_start,recordings[-1])):
        audio_tags.append(f'<audio id="voice-{num:02}" src="assets/voice/{num:02}.wav" data-start="{f(start)}" data-duration="{f(rec["duration"])}" data-track-index="30" data-volume="1"></audio>')
    tweens.append(f'tl.fromTo(".card-body",{{y:30,opacity:0}},{{y:0,opacity:1,duration:.55,ease:"power2.out"}},{f(card_start)});')
    tweens.append(f'tl.fromTo(".card-rule",{{scaleX:0}},{{scaleX:1,duration:.5,ease:"power2.out"}},{f(variant_start)});')
    srt.append(f'11\n{srt_time(repeat_start)} --> {srt_time(card_start+3.5)}\n{story["core_expression"]}\n{story["meaning"]}\n')
    srt.append(f'12\n{srt_time(variant_start)} --> {srt_time(total)}\n{story["variant"]}\n{story["variant_meaning"]}\n')

    html_doc = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>零号电梯 · {html.escape(story['title'])}</title><script src="assets/vendor/gsap.min.js"></script><style>
*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#0e0d20}}#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#0e0d20;color:#fff;font-family:system-ui,sans-serif}}.clip{{position:absolute;inset:0}}.scene{{overflow:hidden}}.visual-frame{{position:absolute;inset:0;overflow:hidden}}.picture{{display:block;width:100%;height:100%;object-fit:cover}}.vignette,.video-vignette{{position:absolute;inset:0;background:linear-gradient(180deg,#10102566 0%,transparent 21%,transparent 62%,#080917b8 100%)}}.series-mark{{position:absolute;top:92px;left:68px;z-index:5;font-size:25px;font-weight:800;letter-spacing:.12em;color:#ffe2a0;text-shadow:0 3px 18px #151024}}.series-mark small{{display:block;font-size:15px;font-weight:500;letter-spacing:.24em;color:#fff;opacity:.85;margin-top:8px}}.caption{{z-index:10;display:flex;align-items:flex-end;justify-content:center;padding:0 65px 285px;pointer-events:none}}.subtitle{{width:100%;max-width:950px;text-align:center;border-radius:24px;padding:24px 32px 26px;background:#080b1be2;box-shadow:0 12px 45px #0007}}.speaker{{display:block;font-size:22px;font-weight:700;letter-spacing:.16em;color:#e9bd76;margin-bottom:12px}}.english{{display:block;color:#fff;font-size:50px;line-height:1.24;font-weight:800;text-wrap:balance;text-shadow:0 2px 9px #000}}.english.emphasis{{color:#ffdf8d}}.chinese{{display:block;color:#f2e9e6;font-size:32px;line-height:1.45;margin-top:12px}}.card{{overflow:hidden}}.card-picture{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;filter:blur(12px) brightness(.45);transform:scale(1.07)}}.card-shade{{position:absolute;inset:0;background:linear-gradient(160deg,#150e2ab8,#070719d6)}}.card-body{{position:absolute;inset:0;padding:260px 85px 180px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center}}.card-kicker{{color:#e7ba72;font-size:21px;letter-spacing:.17em;font-weight:800}}.card-title{{font-size:43px;font-weight:800;margin-top:65px;color:#fff3da}}.card-phrase{{font-size:83px;line-height:1.15;font-weight:900;color:#ffdb8f;margin-top:25px}}.card-meaning{{font-size:35px;color:#fff;margin-top:17px}}.card-prompt{{font-size:26px;color:#e0e0e8;margin-top:35px}}.card-rule{{width:100%;height:2px;background:#ba9f81;transform-origin:left center;margin:75px 0 54px}}.card-variant-label{{font-size:22px;letter-spacing:.13em;font-weight:800;color:#d7b785}}.card-variant{{font-size:47px;font-weight:800;color:#fff;margin-top:23px;line-height:1.2}}.card-variant-zh{{font-size:30px;color:#e5e3ec;margin-top:15px}}
</style></head><body><div id="root" data-composition-id="zero-ep001" data-start="0" data-duration="{f(total)}" data-width="1080" data-height="1920">{''.join(visuals)}{card}<div id="series-mark" class="series-mark clip" data-start="0" data-duration="{f(card_start)}" data-track-index="10">零号电梯<small>ELEVATOR ZERO · 01</small></div>{''.join(captions)}<audio id="soundscape" src="assets/audio/soundscape.wav" data-start="0" data-duration="{f(total)}" data-track-index="29" data-volume="0.42"></audio>{''.join(audio_tags)}</div><script>const tl=gsap.timeline({{paused:true}});{''.join(tweens)}window.__timelines['zero-ep001']=tl;</script></body></html>'''
    (PROJECT/'index.html').write_text(html_doc, encoding='utf-8')
    (PROJECT/'timing.json').write_text(json.dumps({'duration':total,'card_start':card_start,'dialogue':timeline,'repeat_start':round(repeat_start,3),'variant_start':round(variant_start,3)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PROJECT/'subtitles_bilingual.srt').write_text('\n'.join(srt),encoding='utf-8')
    print(f'Built {total:.3f}s from {len(timeline)} dialogue recordings; card starts {card_start:.3f}s')


if __name__ == '__main__':
    main()
