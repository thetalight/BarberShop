"""Build any scripted daily episode from the JSONL story, executable takes and WAV lengths."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from barber import stories  # noqa: E402

LIBRARY_PATH = ROOT / 'series/xiangwei/assets/shot_library.json'


def read_inputs(story_id: str, project: Path):
    data = stories.get_story(ROOT, story_id)  # validates story and take IDs before generation
    if data.get('format') != 'daily_english' or data.get('status') not in {'scripted', 'produced'}:
        raise ValueError(f'{story_id} is not a scripted daily episode')
    voices = json.loads((project / 'assets/voice/manifest.json').read_text(encoding='utf-8'))
    lines = data['dialogue'] + [
        {'speaker': 'dad', 'en': data['core_expression'], 'zh': data['meaning']},
        {'speaker': 'dad', 'en': data['variant'], 'zh': data['variant_meaning']},
    ]
    if len(voices) != len(lines):
        raise ValueError(f'{story_id} needs {len(lines)} recordings; found {len(voices)}')
    for i, (line, voice) in enumerate(zip(lines, voices), 1):
        if any(line[k] != voice[k] for k in ('speaker', 'en', 'zh')):
            raise ValueError(f'Voice {i:02d} is stale; regenerate voices first')
        if not (project / voice['path']).is_file() or voice['duration'] <= 0:
            raise ValueError(f'Voice {i:02d} is missing or empty')
    library = json.loads(LIBRARY_PATH.read_text(encoding='utf-8'))
    takes = {tuple(t[k] for k in ('shot', 'speaker', 'emotion', 'action')): t for t in library['takes']}
    return data, voices, lines, takes


def timeline(data: dict, voices: list[dict]):
    starts, ends = [], []
    at = 0.12
    for line, voice in zip(data['dialogue'], voices):
        starts.append(round(at, 3))
        end = round(at + voice['duration'], 3)
        ends.append(end)
        at = end + line['pause_after']
    card_start = round(at, 3)
    card = data['learning_card']
    total = round(card_start + card['duration'], 3)
    card_voice = [round(card_start + card['repeat_at'], 3),
                  round(card_start + card['variant_at'] + 0.35, 3)]
    if card_voice[0] + voices[-2]['duration'] > card_start + card['variant_at'] - 1.0:
        raise ValueError('Original phrase needs at least 1s for the viewer to repeat')
    if card_voice[1] + voices[-1]['duration'] > total - 1.0:
        raise ValueError('Variant needs at least 1s for the viewer to repeat')
    return starts, ends, card_start, total, starts + card_voice


def local_take(project: Path, take: dict) -> str:
    source = (ROOT / take['asset']).resolve()
    if not source.is_file() or ROOT not in source.parents:
        raise ValueError(f"Missing or external take asset: {take['asset']}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    target = project / 'assets/takes' / f'{digest}-{source.name}'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        shutil.copy2(source, target)
    return target.relative_to(project).as_posix()


def pose(take: dict, src: str, at: float) -> dict:
    scale = float(take.get('scale', 1.04))
    x, y = float(take.get('x', 0)), float(take.get('y', 0))
    xlim, ylim = max(0, (scale - 1) * 540 - 8), max(0, (scale - 1) * 960 - 8)
    return {'src': src, 'at': round(at, 3), 'scale': scale,
            'x': round(max(-xlim, min(xlim, x)), 2),
            'y': round(max(-ylim, min(ylim, y)), 2)}


def scene_html(name: str, duration: float, poses: list[dict]) -> str:
    if not poses or poses[0]['at'] != 0 or any(p['at'] < 0 or p['at'] >= duration for p in poses):
        raise ValueError(f'Invalid scene poses: {name}')
    root = f'scene-{name}-root'
    images = '\n'.join(f'<img id="scene-{name}-shot-{i}" src="../{html.escape(p["src"])}" alt="{name} {i+1}">'
                       for i, p in enumerate(poses))
    values = json.dumps([{k: p[k] for k in ('at', 'scale', 'x', 'y')} for p in poses])
    return f'''<!doctype html><html lang="en"><body><template>
<style>#{root}{{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:#251f18}}
#{root} img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transform-origin:50% 50%}}
#{root} img:first-child{{opacity:1}}</style>
<div id="{root}" data-composition-id="scene-{name}" data-width="1080" data-height="1920" data-duration="{duration:.3f}" data-layout-allow-overflow>{images}</div>
<script>(function(){{const poses={values},tl=gsap.timeline({{paused:true}});
poses.forEach((p,i)=>{{const id="#scene-{name}-shot-"+i;const until=i+1<poses.length?poses[i+1].at:{duration:.3f};
tl.fromTo(id,{{scale:p.scale,x:p.x,y:p.y}},{{scale:p.scale+.01,x:p.x+2,y:p.y-2,duration:Math.max(.1,until-p.at),ease:"sine.inOut",immediateRender:false}},p.at);
if(i){{tl.set("#scene-{name}-shot-"+(i-1),{{opacity:0}},p.at);tl.set(id,{{opacity:1}},p.at);}}}});
window.__timelines["scene-{name}"]=tl;}})();</script></template></body></html>'''


def captions_html(data, voices, starts, card_start, total):
    names = {'dad': 'DAD', 'retired_regular': 'MR. MILLER', 'daughter': 'DAUGHTER',
             'commuter_regular': 'REGULAR', 'neighbor_owner': 'NEIGHBOR'}
    core = html.escape(data['core_expression'])
    blocks = []
    for i, (line, voice) in enumerate(zip(data['dialogue'], voices), 1):
        en = html.escape(line['en']).replace(core, f'<em>{core}</em>')
        blocks.append(f'<div id="caption-{i:02d}" class="clip caption" data-start="{max(0,starts[i-1]-.05):.3f}" '
                      f'data-duration="{voice["duration"]+.22:.3f}" data-track-index="0"><div class="copy">'
                      f'<span class="speaker">{html.escape(names.get(line["speaker"],line["speaker"].upper()))}</span>'
                      f'<span class="english">{en}</span><span class="chinese">{html.escape(line["zh"])}</span></div></div>')
    card = data['learning_card']
    variant_at = card_start + card['variant_at']
    return f'''<!doctype html><html lang="en"><body><template>
<style>
#captions-root{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;color:#fff9ec;font-family:system-ui,-apple-system,sans-serif}}
#captions-root .shade{{position:absolute;left:0;right:0;bottom:0;height:690px;background:linear-gradient(to top,rgba(22,17,13,.91),rgba(22,17,13,.48) 58%,transparent)}}
#captions-root .clip{{position:absolute;inset:0}}#captions-root .caption{{display:flex;align-items:flex-end;justify-content:center;padding:0 76px 232px}}
#captions-root .copy{{max-width:928px;text-align:center;text-shadow:0 3px 0 #241b15,3px 0 #241b15,-3px 0 #241b15,0 8px 26px #000}}
#captions-root .speaker{{display:inline-block;margin-bottom:18px;padding:7px 15px;border-radius:8px;background:rgba(35,25,17,.83);color:#f3c581;font-size:24px;font-weight:800;letter-spacing:.1em}}
#captions-root .english{{display:block;font-size:51px;line-height:1.19;font-weight:800}}#captions-root .english em{{font-style:normal;color:#ffda93;text-decoration:underline;text-underline-offset:7px}}
#captions-root .chinese{{display:block;margin-top:13px;font-size:39px;line-height:1.22;font-weight:720;color:#f6dbad}}
#captions-root .phrase-card{{display:flex;align-items:flex-end;justify-content:center;padding:0 70px 335px}}
#captions-root .phrase-inner{{width:100%;border:2px solid rgba(243,197,129,.75);border-radius:30px;background:rgba(31,24,19,.93);padding:36px 30px 42px;text-align:center;box-shadow:0 20px 55px rgba(0,0,0,.35)}}
#captions-root .kicker{{display:block;color:#f3c581;font-size:28px;font-weight:780;letter-spacing:.14em;margin-bottom:18px}}
#captions-root .phrase-en{{display:block;font-size:65px;line-height:1.12;font-weight:850;letter-spacing:-.025em}}
#captions-root .phrase-zh{{display:block;margin-top:19px;color:#f3c581;font-size:46px;font-weight:750}}
#captions-root .follow{{display:block;margin-top:23px;color:#fff0d8;font-size:31px;font-weight:650}}
</style>
<div id="captions-root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="{total:.3f}"><div class="shade"></div>{''.join(blocks)}
<div id="phrase-card" class="clip phrase-card" data-start="{card_start:.3f}" data-duration="{variant_at-card_start:.3f}" data-track-index="0"><div class="phrase-inner"><span class="kicker">TODAY'S ENGLISH</span><span class="phrase-en">{core}</span><span class="phrase-zh">{html.escape(data['meaning'])}</span><span class="follow">{html.escape(card['repeat_prompt'])}</span></div></div>
<div id="variant-card" class="clip phrase-card" data-start="{variant_at:.3f}" data-duration="{total-variant_at:.3f}" data-track-index="0"><div class="phrase-inner"><span class="kicker">SAY IT YOUR WAY</span><span class="phrase-en">{html.escape(data['variant'])}</span><span class="phrase-zh">{html.escape(data['variant_meaning'])}</span><span class="follow">{html.escape(card['variant_prompt'])}</span></div></div>
</div><script>(function(){{const tl=gsap.timeline({{paused:true}});document.querySelectorAll('#captions-root .caption').forEach(c=>{{const t=Number(c.dataset.start);tl.fromTo(c.querySelector('.copy'),{{opacity:0,y:12}},{{opacity:1,y:0,duration:.2,ease:'power2.out',immediateRender:false}},t+.02);}});for(const id of ['phrase-card','variant-card']){{const c=document.getElementById(id);tl.fromTo(c.querySelector('.phrase-inner'),{{opacity:0,y:14}},{{opacity:1,y:0,duration:.27,ease:'power2.out',immediateRender:false}},Number(c.dataset.start)+.04);}}window.__timelines['captions']=tl;}})();</script></template></body></html>'''


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def build(story_id: str, project: Path) -> None:
    project = (ROOT / project).resolve()
    if ROOT not in project.parents or not project.is_dir():
        raise ValueError(f'Invalid local episode project: {project}')
    data, voices, lines, takes = read_inputs(story_id, project)
    starts, ends, card_start, total, voice_starts = timeline(data, voices)
    comps = project / 'compositions'
    comps.mkdir(exist_ok=True)
    specs = []
    for i, line in enumerate(data['dialogue']):
        start = 0 if i == 0 else starts[i]
        end = starts[i+1] if i + 1 < len(starts) else card_start
        reaction = line['listener_reaction']
        main_key = (line['shot'], line['speaker'], line['emotion'], line['action']['id'])
        react_key = (reaction['shot'], reaction['speaker'], reaction['emotion'], reaction['action'])
        main_take, react_take = takes[main_key], takes[react_key]
        main_src, react_src = local_take(project, main_take), local_take(project, react_take)
        reaction_at = min(end-start-.22, max(.55, ends[i]-start-.22))
        if reaction_at <= .1:
            raise ValueError(f'Line {i+1} leaves no room for a visible reaction')
        name = f'line-{i+1:02d}'
        scene_poses = [pose(main_take, main_src, 0), pose(react_take, react_src, reaction_at)]
        (comps / f'scene-{name}.html').write_text(scene_html(name, end-start, scene_poses), encoding='utf-8')
        specs.append({'id': name, 'start': round(start,3), 'duration': round(end-start,3),
                      'assets': [main_take['asset'], react_take['asset']], 'poses': scene_poses,
                      'shot': line['shot'], 'emotion': line['emotion'], 'action': line['action']['id'],
                      'listener_reaction': reaction})
    last = specs[-1]
    card_name = 'recall'
    card_pose = [pose(takes[(data['dialogue'][-1]['shot'],data['dialogue'][-1]['speaker'],data['dialogue'][-1]['emotion'],data['dialogue'][-1]['action']['id'])],last['poses'][0]['src'],0)]
    (comps / 'scene-recall.html').write_text(scene_html(card_name,total-card_start,card_pose),encoding='utf-8')
    specs.append({'id':card_name,'start':card_start,'duration':round(total-card_start,3),'assets':[last['assets'][0]],'poses':card_pose})
    (comps / 'captions.html').write_text(captions_html(data,voices,starts,card_start,total),encoding='utf-8')
    current_scenes = {f'scene-{spec["id"]}.html' for spec in specs}
    for old in comps.glob('scene-*.html'):
        if old.name not in current_scenes:
            old.unlink()
    used_takes = {item['src'].split('/')[-1] for spec in specs for item in spec['poses']}
    for old in (project / 'assets/takes').glob('*'):
        if old.is_file() and old.name not in used_takes:
            old.unlink()
    hosts=[]
    for track, spec in enumerate(specs):
        name=spec['id']
        hosts.append(f'<div id="scene-{name}" class="clip scene-host" data-composition-id="scene-{name}" data-composition-src="compositions/scene-{name}.html" data-start="{spec["start"]:.3f}" data-duration="{spec["duration"]:.3f}" data-track-index="{track}" data-track-kind="graphics" data-width="1080" data-height="1920"></div>')
    audio=[f'<audio id="music" src="assets/audio/music_box.wav" data-start="0" data-duration="{total:.3f}" data-track-index="30" data-volume="0.10"></audio>']
    for i, voice in enumerate(voices):
        audio.append(f'<audio id="voice-{voice["id"]}" src="{html.escape(voice["path"])}" data-audio-group="voiceover" data-start="{voice_starts[i]:.3f}" data-duration="{voice["duration"]:.3f}" data-track-index="31" data-volume="1"></audio>')
    project_name = project.name
    page=f'''<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>老爸的英语理发店 · {html.escape(data['title'])}</title><script src="assets/vendor/gsap.min.js"></script>
<style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#251f18}}#root{{position:relative;width:100%;height:100%;overflow:hidden;background:#251f18}}.clip{{position:absolute;inset:0}}.scene-host{{overflow:hidden}}.brand{{inset:112px auto auto 72px;height:auto;width:auto;padding:14px 20px;border-radius:14px;background:rgba(25,18,13,.91);color:#fff9ec;font-family:system-ui,-apple-system,sans-serif;font-size:31px;font-weight:800;letter-spacing:.05em;text-shadow:0 3px 12px #201810}}.brand span{{display:block;width:160px;height:4px;margin-top:13px;background:#f3c581;border-radius:2px}}</style></head>
<body><div id="root" data-composition-id="{project_name}" data-start="0" data-duration="{total:.3f}" data-width="1080" data-height="1920">{''.join(hosts)}<div id="brand" class="clip brand" data-start="0" data-duration="{card_start:.3f}" data-track-index="10">老爸的英语理发店<span></span></div><div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" data-track-index="20" data-track-kind="captions" data-width="1080" data-height="1920"></div>{''.join(audio)}</div><script>window.__timelines['{project_name}']=gsap.timeline({{paused:true}});</script></body></html>'''
    (project/'index.html').write_text(page,encoding='utf-8')
    subtitles=[]
    for i,(line,voice) in enumerate(zip(lines,voices),1):
        begin=max(0,voice_starts[i-1]-.05)
        end=min(total,voice_starts[i-1]+voice['duration']+.2)
        subtitles.append(f"{i}\n{srt_time(begin)} --> {srt_time(end)}\n{line['en']}\n{line['zh']}\n")
    (project/'subtitles_bilingual.srt').write_text('\n'.join(subtitles),encoding='utf-8')
    timing={'story_id':story_id,'scenes':specs,'dialogue_starts':starts,'dialogue_ends':ends,
            'voice_starts':voice_starts,'card_start':card_start,'duration':total}
    (project/'timing.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ep_id=f'ep{data["day"]:03d}_daily'
    episode_dir=ROOT/'episodes'/ep_id
    episode_dir.mkdir(parents=True,exist_ok=True)
    task={'id':ep_id,'series_id':'xiangwei','story_id':story_id,'title':data['title'],
          'publish_title':data['publish_title'],'intro':data['intro'],
          'language':'en-US','subtitle_languages':['en','zh-CN'],'source_project':project.relative_to(ROOT).as_posix(),
          'asset_catalogs':['series/xiangwei/assets/fixed.json','series/xiangwei/assets/shot_library.json'],
          'shots':[{'id':s['id'],'start':s['start'],'duration':s['duration'],
                    'asset':f'{project.relative_to(ROOT).as_posix()}/compositions/scene-{s["id"]}.html'} for s in specs]}
    (episode_dir/'episode.json').write_text(json.dumps(task,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Built {story_id} in {project.relative_to(ROOT)}: {len(data["dialogue"])} lines, {len(specs)} scenes, {total:.3f}s')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--story-id',required=True)
    parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args()
    build(args.story_id,args.project)


if __name__=='__main__':
    main()
