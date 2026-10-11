"""Read-only local dashboard for stories, shared assets and production history."""

from __future__ import annotations

import argparse
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


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
FIXED = ROOT / "series/xiangwei/assets"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def media_duration(path: Path) -> float | None:
    if not path.is_file():
        return None
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, timeout=10)
    try:
        return round(float(result.stdout.strip()), 2) if result.returncode == 0 else None
    except ValueError:
        return None


def task_data(root: Path, story_records: list[dict]) -> list[dict]:
    output_root = root / "outputs"
    episode_root = root / "episodes"
    names = set()
    for folder in (output_root, episode_root):
        if folder.is_dir():
            names.update(item.name for item in folder.iterdir() if item.is_dir() and re.fullmatch(r"ep\d{3}_daily", item.name))
    tasks = []
    for ep_id in sorted(names, reverse=True):
        episode = episode_root / ep_id
        output = output_root / ep_id
        plan = read_json(episode / "episode.json")
        manifest = read_json(episode / "reports/generation_manifest.json") or read_json(output / "generation_manifest.json")
        story = next((item for item in story_records if ep_id in item.get("episode_ids", [])), None)
        title = (story or {}).get("title") or plan.get("title") or ep_id
        final = output / "final.mp4"
        cover = output / "cover.png"
        srt = output / "subtitles.srt"
        selected = manifest.get("selected", {})
        jobs = []
        for job_id, job in manifest.get("jobs", {}).items():
            jobs.append({"id": job_id, "status": job.get("status", "unknown"), "started_at": job.get("started_at"), "elapsed_seconds": job.get("elapsed_seconds")})
        jobs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        updated = manifest.get("updated_at")
        if not updated and final.exists():
            updated = datetime.fromtimestamp(final.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        tasks.append({
            "id": ep_id,
            "title": title,
            "intro": (story or {}).get("intro", ""),
            "story_id": (story or {}).get("id"),
            "kind": "系列开场" if (story or {}).get("format") == "series_intro" else "英语情景剧",
            "status": "已完成" if final.is_file() else ("制作中" if jobs else "待开始"),
            "updated_at": updated,
            "duration_seconds": media_duration(final),
            "shot_count": len(plan.get("shots", [])) or len(selected),
            "selected_count": len(selected),
            "job_count": len(jobs),
            "jobs": jobs,
            "video_url": f"/media/outputs/{ep_id}/final.mp4" if final.is_file() else None,
            "cover_url": f"/media/outputs/{ep_id}/cover.png" if cover.is_file() else None,
            "subtitle_url": f"/media/outputs/{ep_id}/subtitles.srt" if srt.is_file() else None,
        })
    return tasks


def dashboard_data(root: Path = ROOT) -> dict:
    records = [item for item in stories.read_catalog(root) if item.get("format") in {"daily_english", "series_intro"}]
    fixed = read_json(root / "series/xiangwei/assets/fixed.json").get("assets", {})
    labels = {
        "human_barber_v1": "爸爸 · 理发师", "daughter_v1": "四岁女儿",
        "commuter_regular_v1": "上班族熟客", "retired_regular_v1": "退休熟客",
        "neighbor_owner_v1": "邻店老板", "US_INT_WIDE": "美国社区店内",
        "US_EXT_FRONT": "美国社区店外", "US_TOY_CORNER": "店内玩具角",
        "US_CHAIR_FRONT": "理发椅正面", "US_CHAIR_SIDE": "理发椅侧面",
    }
    assets = [{"id": key, "label": labels.get(key, key), "url": "/media/" + value["path"], "scope": "daily"} for key, value in fixed.items() if (root / value["path"]).is_file()]
    tasks = task_data(root, records)
    return {
        "series": "老爸的英语理发店",
        "source": str(stories.CATALOG),
        "stories": records,
        "tasks": tasks,
        "fixed_assets": assets,
        "summary": {
            "produced_stories": sum(item["record_type"] == "story" and item["status"] == "produced" for item in records),
            "conceived_stories": len(records),
            "daily_ideas": sum(item.get("format") == "daily_english" for item in records),
            "completed_tasks": sum(item["status"] == "已完成" for item in tasks),
            "fixed_assets": len(assets),
        },
    }


class Handler(BaseHTTPRequestHandler):
    project_root = ROOT

    def do_GET(self) -> None:
        route = unquote(urlsplit(self.path).path)
        try:
            if route == "/api/dashboard":
                payload = json.dumps(dashboard_data(self.project_root), ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            static = {"/": "index.html", "/styles.css": "styles.css", "/app.js": "app.js"}
            if route in static:
                self.send_file(WEB / static[route])
                return
            if route.startswith("/media/"):
                relative = Path(route.removeprefix("/media/"))
                if relative.is_absolute() or ".." in relative.parts:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
                path = (self.project_root / relative).resolve()
                outputs = (self.project_root / "outputs").resolve()
                fixed = (self.project_root / "series/xiangwei/assets").resolve()
                if not (outputs in path.parents or fixed in path.parents) or path.suffix.lower() not in {".mp4", ".png", ".srt"}:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                self.send_file(path)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (OSError, stories.StoryError) as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range", "")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            elif match.group(2):
                start = max(0, size - int(match.group(2)))
            if start > end or start >= size:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            end = min(end, size - 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(end - start + 1))
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as file:
            file.seek(start)
            remaining = end - start + 1
            while remaining:
                block = file.read(min(1024 * 1024, remaining))
                if not block:
                    break
                try:
                    self.wfile.write(block)
                except BrokenPipeError:
                    break
                remaining -= len(block)


def main() -> None:
    parser = argparse.ArgumentParser(description="老爸的英语理发店本地故事与任务看板")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"老爸的英语理发店本地看板：http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
