"""Strict, local-only production runner. No synthetic media is accepted as output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import stories as story_catalog

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/project.json"
MIN_BYTES = {"image": 1024, "audio": 2048, "video": 4096}


class PipelineError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fingerprint(*items: object) -> str:
    data = json.dumps(items, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def references_match(recorded: list[dict] | None, current: list[dict]) -> bool:
    """Accept a relocated reference only when the recorded source still has identical bytes."""
    if not isinstance(recorded, list) or len(recorded) != len(current):
        return False
    for old, new in zip(recorded, current):
        if old.get("sha256") != new.get("sha256"):
            return False
        try:
            source = project_file(old["path"])
        except (KeyError, PipelineError):
            return False
        if not source.is_file() or sha256(source) != old["sha256"]:
            return False
    return True


def episode_files(ep_id: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"ep\d{3}_human", ep_id):
        raise PipelineError("人物系列集数必须是 ep001_human 这样的 ID")
    folder = ROOT / "episodes" / ep_id
    plan = folder / "episode.json"
    if not plan.is_file():
        raise PipelineError(f"未找到剧本：{plan}")
    return folder, ROOT / "outputs" / ep_id, plan


def project_file(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise PipelineError(f"项目路径无效：{relative}")
    resolved = (ROOT / path).resolve()
    if ROOT.resolve() not in resolved.parents:
        raise PipelineError(f"项目路径越界：{relative}")
    return resolved


def episode_plan(ep_id: str) -> dict:
    _, _, plan_file = episode_files(ep_id)
    plan = read_json(plan_file)
    if plan.get("id") != ep_id:
        raise PipelineError(f"剧本集数不匹配：{plan_file}")
    if not plan.get("story_id"):
        raise PipelineError("人物版集数必须关联全局故事 ID")
    if plan.get("series_id") != "xiangwei":
        raise PipelineError("人物版集数必须关联老爸的英语理发店系列")
    story = story_catalog.get_story(ROOT, plan["story_id"])
    if ep_id not in story.get("episode_ids", []):
        raise PipelineError("全局故事与集数的关联不匹配")
    narration = story.get("narration", {})
    if set(narration) != {shot["id"] for shot in plan["shots"]}:
        raise PipelineError("全局故事旁白须与全部镜头一一对应")
    if any("narration" in shot for shot in plan["shots"]):
        raise PipelineError("人物版旁白只能保存在全局故事文件")
    expected_fixed = "series/xiangwei/assets/fixed.json"
    if not plan.get("asset_catalogs") or plan["asset_catalogs"][0] != expected_fixed:
        raise PipelineError("人物版必须首先引用系列公共固定素材")
    plan["title"] = story["title"]
    plan["publish_title"] = story.get("publish_title", "")
    plan["intro"] = story["intro"]
    for shot in plan["shots"]:
        shot["narration"] = narration[shot["id"]]
    return plan


def config() -> dict:
    value = read_json(CONFIG)
    if value.get("schema_version") != 1 or value.get("execution", {}).get("local_only") is not True:
        raise PipelineError("配置必须使用 schema_version=1 且 local_only=true")
    if value["execution"].get("gpu_concurrency") != 1 or value["execution"].get("auto_publish") is not False:
        raise PipelineError("首版只允许 GPU 并发 1，且禁止自动发布")
    return value


def run_command(argv: list[str], log: Path, timeout: int = 3600, env: dict[str, str] | None = None) -> float:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        out.write("COMMAND: " + json.dumps(argv, ensure_ascii=False) + "\n")
        out.flush()
        try:
            process = subprocess.run(argv, stdout=out, stderr=subprocess.STDOUT, timeout=timeout, check=False, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            out.write(f"\nERROR: {exc}\n")
            raise PipelineError(f"后端调用失败，详见 {log}: {exc}") from exc
    if process.returncode != 0:
        raise PipelineError(f"后端退出码 {process.returncode}，详见 {log}")
    return round(time.monotonic() - started, 3)


def probe(path: Path, kind: str) -> dict:
    if not path.is_file() or path.stat().st_size < MIN_BYTES[kind]:
        raise PipelineError(f"{kind} 文件缺失或过小：{path}")
    if kind == "image":
        # sips is installed on macOS; its exit code catches corrupt PNG/JPEG files.
        result = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], capture_output=True, text=True)
        if result.returncode != 0 or "pixelWidth" not in result.stdout:
            raise PipelineError(f"图片不可读：{path}")
        return {"bytes": path.stat().st_size, "sha256": sha256(path)}
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise PipelineError(f"媒体不可读：{path}: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", 0))
    streams = info.get("streams", [])
    required = "audio" if kind == "audio" else "video"
    if duration <= 0 or not any(s.get("codec_type") == required for s in streams):
        raise PipelineError(f"媒体时长或{required}流无效：{path}")
    return {"bytes": path.stat().st_size, "sha256": sha256(path), "duration": duration, "streams": streams}


def load_state(folder: Path, ep_id: str) -> dict:
    path = folder / "reports/generation_manifest.json"
    return read_json(path) if path.exists() else {"episode": ep_id, "schema_version": 1, "jobs": {}, "selected": {}, "updated_at": now()}


def save_state(folder: Path, state: dict) -> None:
    state["updated_at"] = now()
    write_json(folder / "reports/generation_manifest.json", state)


def doctor(_: argparse.Namespace) -> None:
    cfg = config()
    hardware = subprocess.run(["system_profiler", "SPHardwareDataType"], capture_output=True, text=True).stdout
    chip = next((line.split(":", 1)[1].strip() for line in hardware.splitlines() if line.strip().startswith("Chip:")), "unavailable")
    memory = next((line.split(":", 1)[1].strip() for line in hardware.splitlines() if line.strip().startswith("Memory:")), "unavailable")
    disk = shutil.disk_usage(ROOT)
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    tools["draw-things-cli"] = shutil.which("draw-things-cli")
    tools["image_provider"] = shutil.which(cfg["image"]["executable"])
    tools["image_edit_provider"] = shutil.which(cfg["image"].get("edit_executable", ""))
    tools["ltx-2-mlx"] = shutil.which(cfg["video"]["executable"])
    audio_exe = Path(cfg["audio"]["executable"])
    audio_model = Path(cfg["audio"]["model"])
    q8_cache = Path.home() / ".cache/huggingface/hub/models--dgrauet--ltx-2.3-mlx-q8"
    video_model = Path(cfg["video"]["model"])
    required_video_files = ["transformer-distilled.safetensors", "connector.safetensors", "spatial_upscaler_x2_v1_1.safetensors", "vae_encoder.safetensors", "vae_decoder.safetensors", "config.json"]
    video_model_ready = all((video_model / name).is_file() for name in required_video_files)
    image_model_dir = Path(cfg["image"]["model"])
    if cfg["image"]["provider"] == "mflux":
        image_model_files = ["transformer/diffusion_pytorch_model.safetensors", "text_encoder/model-00001-of-00002.safetensors", "text_encoder/model-00002-of-00002.safetensors", "vae/diffusion_pytorch_model.safetensors", "tokenizer/tokenizer.json"]
        image_model_ready = all((image_model_dir / name).is_file() for name in image_model_files)
    else:
        image_model_files = [cfg["image"]["model"], "qwen_3_4b_q8p.ckpt", "flux_2_vae_f16.ckpt"]
        image_model_ready = bool(cfg["image"]["model"]) and all((Path(cfg["image"]["models_dir"]) / name).is_file() for name in image_model_files)
    report = {
        "checked_at": now(), "chip": chip, "memory": memory,
        "macos": platform.mac_ver()[0], "python": platform.python_version(),
        "disk_free_gib": round(disk.free / 1024**3, 2), "tools": tools,
        "audio_executable": str(audio_exe) if audio_exe.exists() else None,
        "audio_model_exists": (audio_model / "model.safetensors").exists(),
        "ltx_q8_cached_gib": round(sum(p.stat().st_size for p in (q8_cache / "blobs").glob("*") if p.is_file()) / 1024**3, 2) if q8_cache.exists() else 0,
        "ltx_q8_project_gib": round(sum((video_model / name).stat().st_size for name in required_video_files if (video_model / name).is_file()) / 1024**3, 2),
        "image_model_ready": image_model_ready,
        "video_model_ready": video_model_ready,
        "capabilities": {
            "tts": audio_exe.exists() and (audio_model / "model.safetensors").exists(),
            "image_generation": bool(tools["image_provider"] and image_model_ready),
            "reference_edit": bool(tools["image_edit_provider"] and image_model_ready and cfg["image"]["reference_edit_verified"]),
            "i2v": bool(tools["ltx-2-mlx"] and video_model_ready),
            "ffmpeg_render": bool(tools["ffmpeg"] and tools["ffprobe"]),
        },
    }
    write_json(ROOT / "reports/environment.json", report)
    lines = ["# 本机环境报告", "", f"检查时间：{report['checked_at']}", "", f"芯片：{chip}；内存：{memory}；macOS：{report['macos']}", f"剩余磁盘：{report['disk_free_gib']} GiB", "", "## 能力", ""]
    lines.extend(f"- {key}: {'可调用，仍需实测' if value else '未就绪'}" for key, value in report["capabilities"].items())
    lines += ["", "当前报告只验证文件和可执行入口存在，不代表生成质量或接口兼容性已通过。", ""]
    (ROOT / "reports/environment.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def speech(ep_id: str, only: str | None = None) -> None:
    cfg = config()
    folder, _, plan_file = episode_files(ep_id)
    plan = episode_plan(ep_id)
    state = load_state(folder, ep_id)
    audio = cfg["audio"]
    if not Path(audio["executable"]).exists() or not Path(audio["model"]).exists():
        raise PipelineError("本地 MLX TTS 程序或模型缺失；不会回退云端语音")
    for shot in plan["shots"]:
        if only and shot["id"] != only:
            continue
        shot_id = shot["id"]
        output = folder / "audio" / f"{shot_id}.wav"
        key = fingerprint("speech-v1", shot["narration"], audio["model"], audio["voice"], audio["language"])
        previous = state["jobs"].get(f"speech:{shot_id}", {})
        if previous.get("key") == key and previous.get("status") == "ready" and output.exists():
            try:
                if previous["sha256"] == sha256(output):
                    print(f"{shot_id}: 复用已验证旁白")
                    continue
            except KeyError:
                pass
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        argv = [audio["executable"], "--model", audio["model"], "--text", shot["narration"], "--voice", audio["voice"], "--lang_code", audio["language"], "--output_path", str(output.parent), "--file_prefix", shot_id, "--audio_format", "wav", "--join_audio"]
        job = {"key": key, "status": "running", "started_at": now(), "command": argv, "model": audio["model"], "voice": audio["voice"]}
        state["jobs"][f"speech:{shot_id}"] = job
        save_state(folder, state)
        try:
            job["elapsed_seconds"] = run_command(argv, folder / "reports" / f"speech_{shot_id}.log", timeout=600)
            media = probe(output, "audio")
            job.update(media)
            job["status"] = "ready"
            job["output"] = str(output.relative_to(ROOT))
            print(f"{shot_id}: {media['duration']:.2f}s，生成耗时 {job['elapsed_seconds']:.1f}s")
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            raise
        finally:
            save_state(folder, state)


def keyframe_path(folder: Path, shot_id: str) -> Path:
    return folder / "keyframes" / f"{shot_id}.png"


def validated_keyframe(ep_id: str, shot_id: str) -> tuple[Path, dict]:
    folder, _, plan_file = episode_files(ep_id)
    plan = episode_plan(ep_id)
    shot = next((item for item in plan["shots"] if item["id"] == shot_id), None)
    if not shot:
        raise PipelineError(f"未知镜头 {shot_id}")
    path = keyframe_path(folder, shot_id)
    media = probe(path, "image")
    state = load_state(folder, ep_id)
    selected = state.get("selected_keyframes", {}).get(shot_id)
    if not selected or selected.get("sha256") != media["sha256"]:
        raise PipelineError(f"{shot_id} 关键帧尚未审核选择或已更改")
    job = state["jobs"].get(f"keyframe:{shot_id}:{selected['candidate']}", {})
    definitions = episode_assets(plan)
    refs = shot_reference_files(ep_id, shot, definitions)
    expected_refs = [{"path": str(ref.relative_to(ROOT)), "sha256": sha256(ref)} for ref in refs]
    if (job.get("sha256") != media["sha256"] or job.get("prompt") != plan["visual_style"] + " " + shot["prompt"]
            or job.get("image_config") != image_input_config() or not references_match(job.get("references"), expected_refs)):
        raise PipelineError(f"{shot_id} 关键帧输入已变更，须重新生成")
    return path, media


def frame_count(seconds: float, fps: int) -> int:
    # LTX 2.3 uses 8k+1 frames. Choose the first grid point covering target time.
    frames = max(9, int(seconds * fps + 0.9999))
    return ((frames - 2) // 8 + 1) * 8 + 1


def required_video_frames(shot: dict, audio_path: Path, fps: int) -> int:
    duration = probe(audio_path, "audio")["duration"]
    return frame_count(max(shot["target_seconds"], duration + 0.35), fps)


def video_prompt(plan: dict, shot: dict) -> str:
    return shot.get("video_style", plan.get("video_style", plan["visual_style"])) + " " + shot.get("motion_prompt", shot["prompt"])


def video_visual_key(plan: dict, shot: dict, image_sha: str, video: dict, seed: int, frames: int) -> str:
    """Narration and editorial trim do not change the generated image sequence."""
    return fingerprint("ltx-i2v-visual-v2", video_prompt(plan, shot), image_sha, video, seed, frames)


def valid_video_job(job: dict, plan: dict, shot: dict, image_sha: str, video_cfg: dict, minimum_frames: int) -> bool:
    if not job or not job.get("output") or job.get("input_sha256") != image_sha:
        return False
    frames = job.get("frames_requested", 0)
    if frames < minimum_frames or not isinstance(job.get("seed"), int):
        return False
    key = video_visual_key(plan, shot, image_sha, video_cfg, job["seed"], frames)
    if job.get("visual_key") != key:
        return False
    output = ROOT / job["output"]
    return output.is_file() and sha256(output) == job.get("sha256")


def generate_video(ep_id: str, shot_id: str, benchmark: bool = False) -> Path:
    cfg = config()
    folder, _, plan_file = episode_files(ep_id)
    plan = episode_plan(ep_id)
    shot = next((x for x in plan["shots"] if x["id"] == shot_id), None)
    if not shot:
        raise PipelineError(f"未知镜头 {shot_id}")
    ref, image_meta = validated_keyframe(ep_id, shot_id)
    state = load_state(folder, ep_id)
    video = cfg["video"]
    exe = shutil.which(video["executable"])
    if not exe:
        raise PipelineError("ltx-2-mlx 未安装，I2V 未运行；不会生成占位视频")
    if video["mode"] != "distilled":
        raise PipelineError("当前只实现经过文档核查的 LTX distilled I2V 调用")
    prefix = f"video:{shot_id}"
    index = 1 if benchmark else 1 + max((int(name.rsplit(":", 1)[1]) for name in state["jobs"] if name.startswith(prefix + ":")), default=0)
    if index > cfg["execution"]["max_candidates_per_shot"] and not benchmark:
        raise PipelineError(f"{shot_id} 已达到候选上限")
    narration = folder / "audio" / f"{shot_id}.wav"
    fps = video["fps"]
    frames = 25 if benchmark else required_video_frames(shot, narration, fps)
    candidate_dir = folder / ("benchmark" if benchmark else "candidates") / shot_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    output = candidate_dir / f"candidate_{index:02d}.mp4"
    if output.exists():
        raise PipelineError(f"候选文件已存在，拒绝覆盖：{output}")
    seed = 1000 + int(shot_id[1:]) * 10 + index
    argv = [exe, "generate", "--prompt", video_prompt(plan, shot), "--image", str(ref), "--distilled", "--model", video["model"], "-H", str(video["preview_height"]), "-W", str(video["preview_width"]), "-f", str(frames), "--frame-rate", str(fps), "--seed", str(seed), "--low-ram", "--no-audio", "-o", str(output)]
    key = fingerprint("ltx-i2v-v1", shot, video_prompt(plan, shot), image_meta["sha256"], video, seed, frames)
    visual_key = video_visual_key(plan, shot, image_meta["sha256"], video, seed, frames)
    job_id = f"benchmark:{shot_id}" if benchmark else f"{prefix}:{index}"
    job = {"job_id": job_id, "shot_id": shot_id, "candidate": index, "key": key, "visual_key": visual_key, "status": "running", "started_at": now(), "input_sha256": image_meta["sha256"], "model": video["model"], "model_revision": video["model_revision"], "source_revision": video["source_revision"], "seed": seed, "frames_requested": frames, "command": argv}
    state["jobs"][job_id] = job
    save_state(folder, state)
    try:
        job["elapsed_seconds"] = run_command(argv, folder / "reports" / f"video_{shot_id}_{index:02d}.log", timeout=7200)
        media = probe(output, "video")
        job.update(media)
        job["status"] = "benchmark_ready" if benchmark else "needs_review"
        job["output"] = str(output.relative_to(ROOT))
        if benchmark:
            write_json(folder / "reports/benchmark.json", {"checked_at": now(), "shot_id": shot_id, "provider": "ltx_mlx", "model": video["model"], "model_revision": video["model_revision"], "source_revision": video["source_revision"], "frames_requested": frames, "elapsed_seconds": job["elapsed_seconds"], "media": media, "status": "real_output_needs_visual_review"})
        print(f"{shot_id} {'冒烟测试' if benchmark else f'候选 {index}'}: {media['duration']:.2f}s，待人工观看")
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        raise
    finally:
        save_state(folder, state)
    return output


def select_candidate(ep_id: str, shot_id: str, candidate: int) -> None:
    folder, _, _ = episode_files(ep_id)
    state = load_state(folder, ep_id)
    job = state["jobs"].get(f"video:{shot_id}:{candidate}")
    if not job or job.get("status") not in {"needs_review", "selected"}:
        raise PipelineError("候选不存在或生成失败")
    output = ROOT / job["output"]
    if sha256(output) != job["sha256"]:
        raise PipelineError("候选内容已变更，拒绝选择")
    old = state["selected"].get(shot_id)
    if old and old != candidate:
        state["jobs"][f"video:{shot_id}:{old}"]["status"] = "needs_review"
    state["selected"][shot_id] = candidate
    job["status"] = "selected"
    save_state(folder, state)
    print(f"{shot_id} 已选候选 {candidate}")


def srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def export(ep_id: str) -> None:
    cfg = config()
    folder, out_dir, plan_file = episode_files(ep_id)
    plan = episode_plan(ep_id)
    state = load_state(folder, ep_id)
    selected: list[tuple[dict, Path, Path, float, float]] = []
    for shot in plan["shots"]:
        shot_id = shot["id"]
        candidate = state["selected"].get(shot_id)
        if not candidate:
            raise PipelineError(f"{shot_id} 无已审核候选，拒绝导出")
        job = state["jobs"].get(f"video:{shot_id}:{candidate}", {})
        video = ROOT / job["output"]
        sound = folder / "audio" / f"{shot_id}.wav"
        ref, ref_meta = validated_keyframe(ep_id, shot_id)
        expected_frames = required_video_frames(shot, sound, cfg["video"]["fps"])
        if not valid_video_job(job, plan, shot, ref_meta["sha256"], cfg["video"], expected_frames):
            raise PipelineError(f"{shot_id} 视频输入已变更，须重新生成和审核")
        audio_cfg = cfg["audio"]
        speech_job = state["jobs"].get(f"speech:{shot_id}", {})
        speech_key = fingerprint("speech-v1", shot["narration"], audio_cfg["model"], audio_cfg["voice"], audio_cfg["language"])
        if speech_job.get("key") != speech_key or speech_job.get("status") != "ready" or not sound.exists() or speech_job.get("sha256") != sha256(sound):
            raise PipelineError(f"{shot_id} 旁白输入已变更或生成未完成")
        if sha256(video) != job.get("sha256"):
            raise PipelineError(f"{shot_id} 候选哈希不匹配")
        vduration = probe(video, "video")["duration"]
        aduration = probe(sound, "audio")["duration"]
        duration = max(aduration + 0.35, shot["target_seconds"])
        if vduration + 0.05 < duration:
            raise PipelineError(f"{shot_id} 视频 {vduration:.2f}s，旁白/目标需要 {duration:.2f}s；请补生成或改剧本，不循环/冻结凑时长")
        selected.append((shot, video, sound, duration, vduration))
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / ".render"
    work.mkdir(exist_ok=True)
    subtitle_lines = []
    cursor = 0.0
    segment_paths = []
    for idx, (shot, video, sound, duration, _) in enumerate(selected, 1):
        segment = work / f"{shot['id']}.mp4"
        argv = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(sound), "-filter_complex", f"[0:v]fps={cfg['video']['fps']},scale={cfg['video']['final_width']}:{cfg['video']['final_height']}:force_original_aspect_ratio=decrease,pad={cfg['video']['final_width']}:{cfg['video']['final_height']}:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v];[1:a]apad=pad_dur={duration}[a]", "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-c:a", "aac", "-b:a", "160k", str(segment)]
        run_command(argv, folder / "reports" / f"render_{shot['id']}.log", timeout=600)
        probe(segment, "video")
        segment_paths.append(segment)
        aduration = probe(sound, "audio")["duration"]
        caption = shot["narration"].replace("。", "。\n", 1).strip()
        subtitle_lines += [str(idx), f"{srt_time(cursor)} --> {srt_time(cursor + aduration)}", caption, ""]
        cursor += duration
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{str(p).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in segment_paths), encoding="utf-8")
    clean = work / "clean.mp4"
    run_command(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(clean)], folder / "reports/render_concat.log", timeout=600)
    meta = probe(clean, "video")
    low, high = plan.get("duration_range_seconds", [40, 50])
    if not low <= meta["duration"] <= high:
        raise PipelineError(f"完整视频 {meta['duration']:.2f}s，不在 {low}-{high}s 目标内；保留预览供检查")
    subtitles = out_dir / "subtitles.srt"
    subtitles.write_text("\n".join(subtitle_lines), encoding="utf-8")
    preview = out_dir / "preview.mp4"
    style = "FontName=Heiti SC,FontSize=9,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=25"
    font_cache = ROOT / ".cache"
    font_cache.mkdir(exist_ok=True)
    render_env = os.environ.copy()
    render_env["XDG_CACHE_HOME"] = str(font_cache)
    run_command(["ffmpeg", "-y", "-v", "error", "-i", str(clean), "-vf", f"subtitles={subtitles}:force_style='{style}'", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-c:a", "copy", str(preview)], folder / "reports/render_subtitles.log", timeout=1200, env=render_env)
    probe(preview, "video")
    shutil.copy2(preview, out_dir / "final.mp4")
    cover = out_dir / "cover.png"
    title_file = work / "cover_title.txt"
    title_file.write_text(plan["title"], encoding="utf-8")
    cover_font = Path("/System/Library/Fonts/STHeiti Medium.ttc")
    if not cover_font.is_file():
        raise PipelineError(f"封面中文字字体缺失：{cover_font}")
    title_filter = f"drawtext=fontfile='{cover_font}':textfile={title_file}:fontsize=104:fontcolor=white:shadowx=3:shadowy=3:shadowcolor=black@0.75:x=(w-text_w)/2:y=160"
    run_command(["ffmpeg", "-y", "-v", "error", "-ss", "2.5", "-i", str(work / "S005.mp4"), "-vf", title_filter, "-frames:v", "1", "-update", "1", str(cover)], folder / "reports/render_cover.log")
    probe(cover, "image")
    make_contact_sheet(folder, selected)
    write_json(out_dir / "generation_manifest.json", state)
    qa = [f"# {plan['title']}（{ep_id}）质量检查", "", f"总时长：{meta['duration']:.2f}s；{len(plan['shots'])} 镜；24fps；1080×1920。", "", "自动检查：媒体可读、候选和关键帧均已选、输入 SHA256 与配置仍匹配、旁白实测、SRT 有序、没有循环或冻结补帧。", "", "已选候选：" + "、".join(f"{shot['id']} #{state['selected'][shot['id']]}" for shot in plan["shots"]) + "。", "", "源视频为 384×704；最终 1080×1920 是封装缩放，不代表原生 1080P 细节。", ""]
    notes_file = folder / "reports/manual_qa.json"
    if notes_file.is_file():
        notes = read_json(notes_file)
        qa += ["## 视觉和播放检查", "", notes["method"], ""]
        qa += [f"- {finding}" for finding in notes["findings"]]
        qa += ["", "## 待复核", ""]
        qa += [f"- {finding}" for finding in notes["remaining"]]
        qa += [""]
    else:
        qa += ["待人工检查：角色、空间、动作、毛发、旁白发音和字幕排版。", ""]
    (folder / "reports/qa_report.md").write_text("\n".join(qa), encoding="utf-8")
    print(f"导出 {preview} ({meta['duration']:.2f}s)")


def make_contact_sheet(folder: Path, selected: list[tuple[dict, Path, Path, float, float]]) -> None:
    frames_dir = folder / "reports/contact_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for shot, video, _, duration, _ in selected:
        for idx, point in enumerate((0.05, duration / 2, max(0.1, duration - 0.1))):
            image = frames_dir / f"{shot['id']}_{idx}.png"
            run_command(["ffmpeg", "-y", "-v", "error", "-ss", f"{point:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=216:384:force_original_aspect_ratio=decrease,pad=216:384:(ow-iw)/2:(oh-ih)/2", str(image)], folder / "reports" / f"contact_{shot['id']}_{idx}.log")
            probe(image, "image")
    sheet = folder / "reports/contact_sheet.png"
    run_command(["ffmpeg", "-y", "-v", "error", "-pattern_type", "glob", "-framerate", "1", "-i", str(frames_dir / "*.png"), "-vf", "tile=3x6:margin=8:padding=6", "-frames:v", "1", str(sheet)], folder / "reports/contact_sheet.log")
    probe(sheet, "image")


def assets(args: argparse.Namespace) -> None:
    cfg = config()
    definitions = (episode_assets(episode_plan(args.episode)) if args.episode
                   else read_json(ROOT / "series/xiangwei/assets/fixed.json"))
    required = list(definitions["assets"])
    missing = []
    for name in required:
        try:
            selected_asset_file(name, definitions)
        except PipelineError:
            missing.append(name)
    report = {"checked_at": now(), "required": required, "missing": missing, "image_provider": cfg["image"], "reference_edit_ready": bool(cfg["image"]["reference_edit_verified"] and shutil.which(cfg["image"]["executable"]) and cfg["image"]["model"])}
    report_name = f"assets_{args.episode or 'series'}.json"
    write_json(ROOT / "reports" / report_name, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing:
        raise PipelineError("固定资产未完成或输入已变更；请生成并审核缺失资产")


def image_command(prompt: str, references: list[Path], output: Path, seed: int, strength: float = 0.4) -> tuple[list[str], dict]:
    cfg = config()["image"]
    executable = cfg.get("edit_executable") if references and cfg["provider"] == "mflux" else cfg["executable"]
    exe = shutil.which(executable)
    if not exe or not cfg["model"]:
        raise PipelineError("本地图片后端或模型未就绪")
    if references and not cfg["reference_edit_verified"]:
        raise PipelineError("当前图片模型的本地参考编辑尚未通过实测；拒绝无参考替代")
    reference_meta = [probe(ref, "image") for ref in references]
    if cfg["provider"] == "mflux":
        argv = [exe, "--model", cfg["model"], "--base-model", cfg["base_model"], "--quantize", str(cfg["quantize"]), "--steps", str(cfg["steps"]), "--seed", str(seed), "--width", "576", "--height", "1024", "--prompt", prompt, "--output", str(output), "--low-ram"]
        if references:
            argv += ["--image-paths", *map(str, references)]
    elif cfg["provider"] == "draw_things_cli":
        argv = [exe, "generate", "--local", "--offline", "--no-download-missing", "--models-dir", cfg["models_dir"], "--model", cfg["model"], "--prompt", prompt, "--width", "576", "--height", "1024", "--seed", str(seed), "--output", str(output)]
        for ref in references:
            argv += ["--image", str(ref)]
        if references:
            argv += ["--strength", str(strength)]
    else:
        raise PipelineError(f"未实现图片后端：{cfg['provider']}")
    return argv, {"references": [{"path": str(ref.relative_to(ROOT)), "sha256": meta["sha256"]} for ref, meta in zip(references, reference_meta)]}


def image_input_config() -> dict:
    """The verification switch is an operational gate, not a generation parameter."""
    return {key: value for key, value in config()["image"].items() if key != "reference_edit_verified"}


def asset_file(asset_id: str, definitions: dict) -> Path:
    spec = definitions["assets"].get(asset_id)
    if spec is None:
        raise PipelineError(f"未知资产 {asset_id}")
    if spec.get("path"):
        return project_file(spec["path"])
    return ROOT / "assets" / spec["folder"] / f"{asset_id}.png"


def selected_asset_file(asset_id: str, definitions: dict) -> Path:
    path = asset_file(asset_id, definitions)
    manifest_file = ROOT / "reports/assets_manifest.json"
    manifest = read_json(manifest_file) if manifest_file.exists() else {}
    selected = manifest.get("selected", {}).get(asset_id)
    if not selected or not path.exists() or sha256(path) != selected.get("sha256"):
        raise PipelineError(f"资产 {asset_id} 未审核选择，或内容已变更")
    entry = manifest.get("candidates", {}).get(asset_id, {}).get(str(selected["candidate"]))
    spec = definitions["assets"][asset_id]
    if not entry or entry.get("sha256") != selected["sha256"]:
        raise PipelineError(f"资产 {asset_id} 的候选记录不完整")
    if entry.get("provider") == "imagegen" and selected.get("provider") == "imagegen":
        if entry.get("prompt") != spec["prompt"]:
            raise PipelineError(f"资产 {asset_id} 的固定设定已变更，须重新审核")
        return path
    if entry.get("prompt") != definitions["style"] + " " + spec["prompt"] or entry.get("image_config") != image_input_config():
        raise PipelineError(f"资产 {asset_id} 的提示词或图片后端已变更，须重新生成")
    parents = [selected_asset_file(parent, definitions) for parent in spec["parents"]]
    expected_refs = [{"path": str(ref.relative_to(ROOT)), "sha256": sha256(ref)} for ref in parents]
    if not references_match(entry.get("references"), expected_refs):
        raise PipelineError(f"资产 {asset_id} 的参考图已变更，须重新生成")
    return path


def asset_definitions_for(asset_id: str) -> dict:
    files = [ROOT / "series/xiangwei/assets/fixed.json"]
    files.extend(sorted((ROOT / "series/xiangwei/stories").glob("ST*/guest_assets.json")))
    for file in files:
        if file.exists():
            definitions = read_json(file)
            if asset_id in definitions["assets"]:
                return definitions
    raise PipelineError(f"未知资产 {asset_id}")


def episode_assets(plan: dict) -> dict:
    catalogs = plan.get("asset_catalogs", [])
    if not catalogs or catalogs[0] != "series/xiangwei/assets/fixed.json":
        raise PipelineError("每集必须引用系列公共固定素材")
    merged: dict = {"assets": {}}
    for relative in catalogs:
        path = project_file(relative)
        if not path.is_file():
            raise PipelineError(f"资产目录不存在：{path}")
        definitions = read_json(path)
        if "style" in merged and merged["style"] != definitions["style"]:
            raise PipelineError("同一集的资产目录美术风格不一致")
        merged["style"] = definitions["style"]
        for asset_id, spec in definitions["assets"].items():
            if asset_id in merged["assets"]:
                raise PipelineError(f"资产 ID 重复：{asset_id}")
            merged["assets"][asset_id] = spec
    return merged


def build_asset(asset_id: str) -> None:
    definitions = asset_definitions_for(asset_id)
    spec = definitions["assets"].get(asset_id)
    if not spec:
        raise PipelineError(f"未知资产 {asset_id}")
    references = [selected_asset_file(parent, definitions) for parent in spec["parents"]]
    folder = project_file(spec["candidate_dir"]) if spec.get("candidate_dir") else ROOT / "assets/candidates" / asset_id
    folder.mkdir(parents=True, exist_ok=True)
    manifest_file = ROOT / "reports/assets_manifest.json"
    manifest = read_json(manifest_file) if manifest_file.exists() else {"schema_version": 1, "candidates": {}, "selected": {}}
    prior = [int(item) for item in manifest.get("candidates", {}).get(asset_id, {})]
    prior += [int(p.stem.rsplit("_", 1)[1]) for p in folder.glob("candidate_*.png")]
    index = 1 + max(prior, default=0)
    if index > config()["execution"]["max_candidates_per_shot"]:
        raise PipelineError(f"{asset_id} 达到候选上限")
    output = folder / f"candidate_{index:02d}.png"
    prompt = definitions["style"] + " " + spec["prompt"]
    argv, inputs = image_command(prompt, references, output, 3000 + index, spec.get("strength", 0.4))
    entry = {"created_at": now(), "status": "running", "output": str(output.relative_to(ROOT)), "model": config()["image"]["model"], "image_config": image_input_config(), "prompt": prompt, "seed": 3000 + index, "command": argv, **inputs}
    manifest["candidates"].setdefault(asset_id, {})[str(index)] = entry
    write_json(manifest_file, manifest)
    try:
        entry["elapsed_seconds"] = run_command(argv, ROOT / "reports/assets" / f"{asset_id}_{index:02d}.log", timeout=3600)
        entry.update(probe(output, "image"))
        entry["status"] = "needs_review"
    except Exception as exc:
        entry["status"] = "failed"
        entry["error"] = str(exc)
        raise
    finally:
        write_json(manifest_file, manifest)
    print(f"{asset_id} 候选 {index} 待审核：{output}")


def select_asset(asset_id: str, candidate: int) -> None:
    definitions = asset_definitions_for(asset_id)
    target = asset_file(asset_id, definitions)
    manifest_file = ROOT / "reports/assets_manifest.json"
    if not manifest_file.exists():
        raise PipelineError("没有资产候选记录")
    manifest = read_json(manifest_file)
    entry = manifest.get("candidates", {}).get(asset_id, {}).get(str(candidate))
    if not entry or entry.get("status") not in {"needs_review", "selected"}:
        raise PipelineError("候选不存在或未成功生成")
    source = ROOT / entry["output"]
    if sha256(source) != entry["sha256"]:
        raise PipelineError("候选哈希不匹配")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest["selected"][asset_id] = {"candidate": candidate, "sha256": sha256(target), "selected_at": now()}
    entry["status"] = "selected"
    write_json(manifest_file, manifest)
    print(f"已选固定资产：{target}")


def shot_references(shot: dict) -> list[str]:
    refs = shot.get("reference_assets")
    if not isinstance(refs, list) or not refs:
        raise PipelineError(f"{shot['id']} 缺少参考资产")
    return refs


def shot_reference_files(ep_id: str, shot: dict, definitions: dict) -> list[Path]:
    folder, _, _ = episode_files(ep_id)
    # A selected frame from the same episode is the strongest identity anchor.
    refs = []
    for source_id in shot.get("reference_keyframes", []):
        if source_id == shot["id"]:
            raise PipelineError("关键帧不能引用自身")
        source = keyframe_path(folder, source_id)
        state = load_state(folder, ep_id)
        selected = state.get("selected_keyframes", {}).get(source_id, {})
        if not source.is_file() or sha256(source) != selected.get("sha256"):
            raise PipelineError(f"参考关键帧 {source_id} 未审核或内容已变更")
        refs.append(source)
    refs.extend(selected_asset_file(asset_id, definitions) for asset_id in shot_references(shot))
    return refs


def build_keyframe(ep_id: str, shot_id: str) -> None:
    folder, _, plan_file = episode_files(ep_id)
    plan = episode_plan(ep_id)
    shot = next((item for item in plan["shots"] if item["id"] == shot_id), None)
    if not shot:
        raise PipelineError(f"未知镜头 {shot_id}")
    definitions = episode_assets(plan)
    refs = shot_reference_files(ep_id, shot, definitions)
    state = load_state(folder, ep_id)
    index = 1 + max((int(name.rsplit(":", 1)[1]) for name in state["jobs"] if name.startswith(f"keyframe:{shot_id}:")), default=0)
    if index > config()["execution"]["max_candidates_per_shot"]:
        raise PipelineError(f"{shot_id} 关键帧达到候选上限")
    output = folder / "keyframes/candidates" / shot_id / f"candidate_{index:02d}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    prompt = plan["visual_style"] + " " + shot["prompt"]
    argv, inputs = image_command(prompt, refs, output, 4000 + int(shot_id[1:]) * 10 + index, 0.4)
    job_id = f"keyframe:{shot_id}:{index}"
    job = {"job_id": job_id, "status": "running", "prompt": prompt, "model": config()["image"]["model"], "image_config": image_input_config(), "command": argv, **inputs}
    state["jobs"][job_id] = job
    save_state(folder, state)
    try:
        job["elapsed_seconds"] = run_command(argv, folder / "reports" / f"keyframe_{shot_id}_{index:02d}.log")
        job.update(probe(output, "image"))
        job["output"] = str(output.relative_to(ROOT))
        job["status"] = "needs_review"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        raise
    finally:
        save_state(folder, state)
    print(f"{shot_id} 关键帧候选 {index} 待审核：{output}")


def select_keyframe(ep_id: str, shot_id: str, candidate: int) -> None:
    folder, _, _ = episode_files(ep_id)
    state = load_state(folder, ep_id)
    job = state["jobs"].get(f"keyframe:{shot_id}:{candidate}")
    if not job or job.get("status") not in {"needs_review", "selected"}:
        raise PipelineError("关键帧候选不存在或生成失败")
    source = ROOT / job["output"]
    if sha256(source) != job["sha256"]:
        raise PipelineError("关键帧候选哈希不匹配")
    target = keyframe_path(folder, shot_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    job["status"] = "selected"
    state.setdefault("selected_keyframes", {})[shot_id] = {"candidate": candidate, "sha256": sha256(target)}
    save_state(folder, state)
    print(f"{shot_id} 已选关键帧：{target}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="barber", description="老爸的英语理发店本地制作命令行")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检测本机环境和已就绪能力")
    assets_cmd = sub.add_parser("assets", help="核查、生成和选择固定资产")
    assets_cmd.add_argument("action", nargs="?", choices=["build", "select"])
    assets_cmd.add_argument("--id")
    assets_cmd.add_argument("--candidate", type=int)
    assets_cmd.add_argument("--episode", help="核查指定集数引用的公共及顾客资产；省略时核查系列固定资产")
    keyframe_cmd = sub.add_parser("keyframe", help="生成或选择分镜关键帧")
    keyframe_cmd.add_argument("action", choices=["build", "select"])
    keyframe_cmd.add_argument("episode")
    keyframe_cmd.add_argument("--shot", required=True)
    keyframe_cmd.add_argument("--candidate", type=int)
    speech_cmd = sub.add_parser("speech", help="逐镜生成真实中文旁白")
    speech_cmd.add_argument("episode")
    speech_cmd.add_argument("--shot")
    benchmark_cmd = sub.add_parser("benchmark", help="单镜 1 秒 I2V 冒烟测试")
    benchmark_cmd.add_argument("--episode", default="ep001_human")
    benchmark_cmd.add_argument("--shot", default="S001")
    run_cmd = sub.add_parser("run", help="生成旁白及待审核视频候选")
    run_cmd.add_argument("episode")
    run_cmd.add_argument("--preview", action="store_true")
    retry_cmd = sub.add_parser("retry", help="单镜重做新候选，不覆盖已有候选")
    retry_cmd.add_argument("episode")
    retry_cmd.add_argument("--shot", required=True)
    select_cmd = sub.add_parser("select", help="人工审核后选择候选")
    select_cmd.add_argument("episode")
    select_cmd.add_argument("--shot", required=True)
    select_cmd.add_argument("--candidate", type=int, required=True)
    export_cmd = sub.add_parser("export", help="只从完整已选素材导出")
    export_cmd.add_argument("episode")
    story_cmd = sub.add_parser("story", help="查看、查重、登记或更新全局 JSONL 故事")
    story_cmd.add_argument("action", choices=["list", "check", "register", "update"])
    story_cmd.add_argument("--file", type=Path, help="待检查或登记的单条 JSON 草稿")
    args = parser.parse_args()
    try:
        if args.command == "doctor": doctor(args)
        elif args.command == "assets":
            if args.action is None: assets(args)
            elif not args.id: raise PipelineError("assets build/select 需要 --id")
            elif args.action == "build": build_asset(args.id)
            elif args.candidate is None: raise PipelineError("assets select 需要 --candidate")
            else: select_asset(args.id, args.candidate)
        elif args.command == "keyframe":
            if args.action == "build": build_keyframe(args.episode, args.shot)
            elif args.candidate is None: raise PipelineError("keyframe select 需要 --candidate")
            else: select_keyframe(args.episode, args.shot, args.candidate)
        elif args.command == "speech": speech(args.episode, args.shot)
        elif args.command == "benchmark": generate_video(args.episode, args.shot, True)
        elif args.command == "retry": generate_video(args.episode, args.shot)
        elif args.command == "select": select_candidate(args.episode, args.shot, args.candidate)
        elif args.command == "export": export(args.episode)
        elif args.command == "story":
            if args.action == "list":
                for item in story_catalog.read_catalog(ROOT):
                    print(f"{item['id']}\t{item['status']}\t{item['title']}\t{item.get('publish_title', '')}\t{item['event_key']}\t{item['premise']}")
            elif args.action == "check":
                findings = (story_catalog.check_candidate(ROOT, story_catalog.load(args.file)) if args.file
                            else story_catalog.audit(ROOT))
                if findings:
                    raise PipelineError("发现重复或高度相似故事：\n- " + "\n- ".join(findings))
                print("故事查重通过")
            else:
                if not args.file:
                    raise PipelineError("story register/update 需要 --file")
                story_catalog.register(ROOT, args.file, update=args.action == "update")
                print(f"故事已写入 {story_catalog.CATALOG}")
        elif args.command == "run":
            speech(args.episode)
            folder, _, plan_file = episode_files(args.episode)
            plan = episode_plan(args.episode)
            for shot in plan["shots"]:
                shot_id = shot["id"]
                state = load_state(folder, args.episode)
                selected_id = state["selected"].get(shot_id)
                if selected_id:
                    job = state["jobs"].get(f"video:{shot_id}:{selected_id}", {})
                    _, ref_meta = validated_keyframe(args.episode, shot_id)
                    expected_frames = required_video_frames(shot, folder / "audio" / f"{shot_id}.wav", config()["video"]["fps"])
                    if valid_video_job(job, plan, shot, ref_meta["sha256"], config()["video"], expected_frames):
                        print(f"{shot_id}: 复用已选候选")
                        continue
                    raise PipelineError(f"{shot_id} 已选候选的输入变更，请审核后 retry")
                _, ref_meta = validated_keyframe(args.episode, shot_id)
                expected_frames = required_video_frames(shot, folder / "audio" / f"{shot_id}.wav", config()["video"]["fps"])
                if any(k.startswith(f"video:{shot_id}:") and v.get("status") == "needs_review"
                       and valid_video_job(v, plan, shot, ref_meta["sha256"], config()["video"], expected_frames)
                       for k, v in state["jobs"].items()):
                    print(f"{shot_id}: 已有待审核候选，跳过生成")
                    continue
                generate_video(args.episode, shot_id)
            if args.preview:
                export(args.episode)
    except (PipelineError, story_catalog.StoryError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
