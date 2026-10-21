"""Read-only local dashboard for the new story world."""
from __future__ import annotations
import json
import mimetypes
import re
import subprocess
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from . import stories

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'
MEDIA_ROOTS=[(ROOT/'series/elevator_zero/assets').resolve(),(ROOT/'outputs').resolve()]


def duration(path:Path):
    if not path.is_file():return None
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,timeout=10)
    try:return round(float(r.stdout),2) if r.returncode==0 else None
    except ValueError:return None


def dashboard_data(root:Path=ROOT):
    rows=stories.read_catalog(root)
    fixed=json.loads((root/stories.ASSETS).read_text(encoding='utf-8'))['shots']
    assets=[{'id':key,'label':value['label'],'url':'/media/'+value['path']} for key,value in fixed.items()]
    tasks=[]
    for row in rows:
        for ep in row.get('episode_ids',[]):
            out=root/'outputs'/ep
            final=out/'final.mp4'
            if not final.exists() and row['status']=='idea':continue
            tasks.append({'id':ep,'story_id':row['id'],'title':row['title'],'intro':row['intro'],
                          'publish_title':row['publish_title'],'status':'已完成' if final.is_file() else '制作中',
                          'duration_seconds':duration(final),'updated_at':datetime.fromtimestamp(final.stat().st_mtime).astimezone().isoformat(timespec='seconds') if final.is_file() else None,
                          'video_url':'/media/outputs/'+ep+'/final.mp4' if final.is_file() else None,
                          'cover_url':'/media/outputs/'+ep+'/cover.png' if (out/'cover.png').is_file() else None,
                          'subtitle_url':'/media/outputs/'+ep+'/subtitles.srt' if (out/'subtitles.srt').is_file() else None})
    return {'series':'零号电梯','tagline':'每扇门后都有一个故事，一句用得上的英语。','source':str(stories.CATALOG),
            'stories':rows,'tasks':tasks,'fixed_assets':assets,
            'summary':{'conceived_stories':len(rows),'produced_stories':sum(r['status']=='produced' for r in rows),
                       'completed_tasks':sum(t['status']=='已完成' for t in tasks),'fixed_assets':len(assets)}}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route=unquote(urlsplit(self.path).path)
        try:
            if route=='/api/dashboard':
                body=json.dumps(dashboard_data(),ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            static={'/':'index.html','/styles.css':'styles.css','/app.js':'app.js'}
            if route in static:self.send_file(WEB/static[route]);return
            if route.startswith('/media/'):
                rel=Path(route.removeprefix('/media/'))
                if rel.is_absolute() or '..' in rel.parts:self.send_error(400);return
                path=(ROOT/rel).resolve()
                if not any(base in path.parents for base in MEDIA_ROOTS) or path.suffix.lower() not in {'.png','.jpg','.jpeg','.mp4','.srt'}:self.send_error(403);return
                self.send_file(path);return
            self.send_error(404)
        except (OSError,stories.StoryError,subprocess.SubprocessError) as exc:self.send_error(500,str(exc))

    def send_file(self,path:Path):
        if not path.is_file():self.send_error(404);return
        size=path.stat().st_size;start=0;end=size-1
        req=self.headers.get('Range','')
        if req:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',req)
            if not m:self.send_error(416);return
            if m.group(1):start=int(m.group(1));end=int(m.group(2)) if m.group(2) else end
            elif m.group(2):start=max(0,size-int(m.group(2)))
            if start>end or start>=size:self.send_error(416);return
            end=min(end,size-1)
        self.send_response(206 if req else 200);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(end-start+1))
        if req:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as f:
            f.seek(start);remaining=end-start+1
            while remaining:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk:break
                try:self.wfile.write(chunk)
                except BrokenPipeError:break
                remaining-=len(chunk)


def serve(port:int=8765):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'零号电梯本地工作台：http://127.0.0.1:{port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':serve()
