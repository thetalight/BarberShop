"""Single-file JSONL story catalog for the 老爸的英语理发店 series."""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


CATALOG = Path("series/xiangwei/stories.jsonl")
COMMON_TEXT = ("id", "title", "intro", "premise", "event_key")
LEGACY_TEXT = ("guest", "hair_request", "reveal", "hair_action")
DAILY_TEXT = ("core_expression", "meaning", "variant", "hook", "payoff")
DAILY_CATEGORIES = {"service", "chat", "interaction"}
DAILY_SETTINGS = {"shop", "community"}
SHOT_LIBRARY = Path(__file__).resolve().parents[1] / "series/xiangwei/assets/shot_library.json"


class StoryError(ValueError):
    pass


def executable_takes() -> tuple[set[str], set[tuple[str, str, str, str]]]:
    try:
        library = json.loads(SHOT_LIBRARY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoryError(f"镜头库不可读：{SHOT_LIBRARY}: {exc}") from exc
    shots = library.get("shots")
    takes = library.get("takes")
    if not isinstance(shots, dict) or not isinstance(takes, list):
        raise StoryError("镜头库须包含 shots 和 takes")
    keys = set()
    for take in takes:
        if not isinstance(take, dict) or any(not isinstance(take.get(k), str) or not take[k] for k in ("shot", "speaker", "emotion", "action", "asset")):
            raise StoryError("镜头库 take 缺少 shot、speaker、emotion、action 或 asset")
        key = tuple(take[k] for k in ("shot", "speaker", "emotion", "action"))
        if key in keys or take["shot"] not in shots:
            raise StoryError(f"镜头库 take 重复或镜头 ID 无效：{key}")
        asset = (SHOT_LIBRARY.parents[3] / take["asset"]).resolve()
        if SHOT_LIBRARY.parents[3] not in asset.parents or not asset.is_file():
            raise StoryError(f"镜头资产不存在：{take['asset']}")
        keys.add(key)
    return set(shots), keys


def validate_daily_production(record: dict, dialogue: list[dict]) -> None:
    shots, takes = executable_takes()
    if record.get("language") != "en-US" or record.get("subtitle_languages") != ["en", "zh-CN"]:
        raise StoryError("已写剧本须使用英语配音和中英双语字幕")
    if not isinstance(record.get("variant_meaning"), str) or not record["variant_meaning"].strip():
        raise StoryError("已写剧本缺少 variant_meaning")
    for index, line in enumerate(dialogue, 1):
        for field in ("intent", "emotion", "shot"):
            if not isinstance(line.get(field), str) or not line[field].strip():
                raise StoryError(f"第 {index} 句缺少 {field}")
        pause = line.get("pause_after")
        if isinstance(pause, bool) or not isinstance(pause, (int, float)) or not 0.3 <= pause <= 3:
            raise StoryError(f"第 {index} 句 pause_after 须在 0.3～3 秒")
        action = line.get("action")
        if not isinstance(action, dict) or any(not isinstance(action.get(k), str) or not action[k].strip() for k in ("id", "description")):
            raise StoryError(f"第 {index} 句 action 须有 id 和 description")
        reaction = line.get("listener_reaction")
        if not isinstance(reaction, dict) or any(not isinstance(reaction.get(k), str) or not reaction[k].strip() for k in ("speaker", "shot", "emotion", "action", "description")):
            raise StoryError(f"第 {index} 句 listener_reaction 信息不完整")
        if line["shot"] not in shots or reaction["shot"] not in shots:
            raise StoryError(f"第 {index} 句使用不存在的镜头 ID")
        if (line["shot"], line["speaker"], line["emotion"], action["id"]) not in takes:
            raise StoryError(f"第 {index} 句在镜头库找不到说话镜头资产")
        if (reaction["shot"], reaction["speaker"], reaction["emotion"], reaction["action"]) not in takes:
            raise StoryError(f"第 {index} 句在镜头库找不到听者反应资产")
    plan = record.get("shot_plan")
    if not isinstance(plan, list) or not plan:
        raise StoryError("已写剧本缺少 shot_plan")
    covered = []
    for item in plan:
        if not isinstance(item, dict) or not isinstance(item.get("visual"), str) or not item["visual"].strip() or not isinstance(item.get("dialogue_lines"), list) or any(type(number) is not int for number in item["dialogue_lines"]):
            raise StoryError("shot_plan 须有 visual 和 dialogue_lines")
        covered.extend(item["dialogue_lines"])
    if sorted(covered) != list(range(1, len(dialogue) + 1)):
        raise StoryError("shot_plan 须恰好覆盖每句对话一次")
    card = record.get("learning_card")
    if not isinstance(card, dict) or any(k not in card for k in ("duration", "repeat_at", "variant_at", "repeat_prompt", "variant_prompt")):
        raise StoryError("已写剧本缺少完整 learning_card")
    if any(isinstance(card[k], bool) or not isinstance(card[k], (int, float)) for k in ("duration", "repeat_at", "variant_at")) or not 0 <= card["repeat_at"] < card["variant_at"] < card["duration"] or card["duration"] - card["variant_at"] < 2.5:
        raise StoryError("learning_card 时间无效或变体跟读留白不足")
    if any(not isinstance(card[k], str) or not card[k].strip() for k in ("repeat_prompt", "variant_prompt")):
        raise StoryError("learning_card 缺少跟读提示")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoryError(f"故事文件不可读：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StoryError(f"故事文件必须是 JSON 对象：{path}")
    return value


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in value if char.isalnum())


def ngrams(value: str, size: int = 2) -> set[str]:
    normalized = normalize(value)
    return ({normalized[index:index + size] for index in range(len(normalized) - size + 1)}
            if len(normalized) >= size else ({normalized} if normalized else set()))


def validate(record: dict) -> None:
    if record.get("schema_version") != 1 or record.get("series_id") != "xiangwei":
        raise StoryError("故事记录需使用 schema_version=1、series_id=xiangwei")
    if record.get("record_type") not in {"story", "reserved"}:
        raise StoryError("record_type 须为 story 或 reserved")
    story_format = record.get("format", "legacy_emotional")
    if story_format not in {"legacy_emotional", "daily_english", "series_intro"}:
        raise StoryError("format 须为 legacy_emotional、daily_english 或 series_intro")
    required = COMMON_TEXT + (DAILY_TEXT if story_format == "daily_english"
                              else ("core_expression", "meaning") if story_format == "series_intro"
                              else LEGACY_TEXT)
    for field in required:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise StoryError(f"故事记录缺少非空字段：{field}")
    intro_length = sum(char.isalnum() for char in record["intro"])
    if not 10 <= intro_length <= 20:
        raise StoryError(f"{record['id']} 的简介须为 10～20 字（不计标点和空格），当前 {intro_length} 字")
    if record["record_type"] == "story" and not re.fullmatch(r"ST\d{3,}", record["id"]):
        raise StoryError("正式故事 ID 须为 ST001 这样的格式")
    for field in (("event_key",) if story_format in {"daily_english", "series_intro"} else ("event_key", "hair_action")):
        if not re.fullmatch(r"[a-z0-9_]+", record[field]):
            raise StoryError(f"{field} 须使用小写英文、数字和下划线")
    if record.get("status") not in {"idea", "scripted", "produced", "reserved"}:
        raise StoryError("status 须为 idea、scripted、produced 或 reserved")
    if record["record_type"] == "story":
        if not isinstance(record.get("beats"), list) or len(record["beats"]) < 3 or any(not isinstance(item, str) or not item.strip() for item in record["beats"]):
            raise StoryError("正式故事的 beats 至少需要三个非空节点")
        if not isinstance(record.get("episode_ids", []), list) or any(not isinstance(item, str) for item in record.get("episode_ids", [])):
            raise StoryError("episode_ids 须为字符串列表")
        if "narration" in record and (not isinstance(record["narration"], dict) or any(not isinstance(item, str) or not item.strip() for item in record["narration"].values())):
            raise StoryError("narration 须为镜头 ID 到非空旁白的映射")
    if story_format == "daily_english":
        if record["record_type"] != "story" or record["status"] == "reserved":
            raise StoryError("日更英语选题须为正式故事，状态不能是 reserved")
        if record.get("category") not in DAILY_CATEGORIES or record.get("setting") not in DAILY_SETTINGS:
            raise StoryError("日更选题须填写有效的 category 和 setting")
        if not isinstance(record.get("day"), int) or record["day"] < 1:
            raise StoryError("日更选题的 day 须为正整数")
        if not isinstance(record.get("participants"), list) or not record["participants"] or any(not isinstance(item, str) or not item.strip() for item in record["participants"]):
            raise StoryError("日更选题须列出固定角色或顾客")
        for field in ("continuity_in", "continuity_out"):
            if not isinstance(record.get(field), list) or any(not isinstance(item, str) or not item.strip() for item in record[field]):
                raise StoryError(f"{field} 须为字符串列表")
        if record.get("status") in {"scripted", "produced"}:
            dialogue = record.get("dialogue")
            if not isinstance(dialogue, list) or not 6 <= len(dialogue) <= 10:
                raise StoryError("已写剧本的日更故事须有 6～10 句英语对话")
            if any(not isinstance(line, dict) or not all(isinstance(line.get(k), str) and line[k].strip() for k in ("speaker", "en", "zh")) for line in dialogue):
                raise StoryError("每句对话须包含 speaker、en 和 zh")
            expression = normalize(record["core_expression"])
            if sum(expression in normalize(line["en"]) for line in dialogue) < 2:
                raise StoryError("已写剧本的日更故事须在英语对话中自然使用两次核心表达")
            validate_daily_production(record, dialogue)
    if story_format == "series_intro":
        if record["record_type"] != "story" or record["status"] not in {"scripted", "produced"}:
            raise StoryError("系列开场须为已写旁白的正式故事")
        if record.get("day") != 0 or record.get("setting") != "shop":
            raise StoryError("系列开场须使用 day=0、setting=shop")
        voiceover = record.get("voiceover")
        if not isinstance(voiceover, list) or not 5 <= len(voiceover) <= 10 or any(
                not isinstance(line, str) or not line.strip() for line in voiceover):
            raise StoryError("系列开场须保存 5～10 段孩子旁白")
        translations = record.get("voiceover_zh")
        if not isinstance(translations, list) or len(translations) != len(voiceover) or any(
                not isinstance(line, str) or not line.strip() for line in translations):
            raise StoryError("系列开场须逐段保存对应中文字幕")
        if record.get("language") != "en-US" or record.get("subtitle_languages") != ["en", "zh-CN"]:
            raise StoryError("系列开场须为英语配音、中英双语字幕")
        if not isinstance(record.get("participants"), list) or not record["participants"]:
            raise StoryError("系列开场须列出出场人物")


def read_catalog(root: Path) -> list[dict]:
    path = root / CATALOG
    if not path.is_file():
        raise StoryError(f"全局故事 JSONL 不存在：{path}")
    records = []
    ids = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StoryError(f"{path}:{number} JSON 无效：{exc}") from exc
        if not isinstance(record, dict):
            raise StoryError(f"{path}:{number} 必须是 JSON 对象")
        validate(record)
        if record["id"] in ids:
            raise StoryError(f"{path}:{number} 故事 ID 重复：{record['id']}")
        ids.add(record["id"])
        records.append(record)
    return records


def write_catalog(root: Path, records: list[dict]) -> None:
    path = root / CATALOG
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")
    temporary.replace(path)


def get_story(root: Path, story_id: str) -> dict:
    for record in read_catalog(root):
        if record["id"] == story_id and record["record_type"] == "story":
            return record
    raise StoryError(f"未登记故事：{story_id}")


def duplicate_reasons(candidate: dict, other: dict) -> list[str]:
    reasons = []
    if candidate.get("id") == other.get("id"):
        reasons.append("故事 ID 相同")
    if normalize(candidate.get("title", "")) == normalize(other.get("title", "")):
        reasons.append("标题相同")
    if candidate.get("event_key") == other.get("event_key"):
        reasons.append("核心事件相同")
    if (candidate.get("format") == other.get("format") == "daily_english"
            and normalize(candidate.get("core_expression", "")) == normalize(other.get("core_expression", ""))):
        reasons.append("核心英语表达相同")
    reveal_a, reveal_b = normalize(candidate.get("reveal", "")), normalize(other.get("reveal", ""))
    if min(len(reveal_a), len(reveal_b)) >= 4 and SequenceMatcher(None, reveal_a, reveal_b).ratio() >= 0.83:
        reasons.append("剧情揭示高度相似")
    premise_a, premise_b = ngrams(candidate.get("premise", "")), ngrams(other.get("premise", ""))
    if premise_a and premise_b and 2 * len(premise_a & premise_b) / (len(premise_a) + len(premise_b)) >= 0.68:
        reasons.append("故事梗概高度相似")
    return reasons


def check_candidate(root: Path, candidate: dict, exclude_id: str | None = None) -> list[str]:
    validate(candidate)
    findings = []
    for existing in read_catalog(root):
        if existing["id"] == exclude_id:
            continue
        reasons = duplicate_reasons(candidate, existing)
        if reasons:
            findings.append(f"{existing['id']}《{existing['title']}》：{'、'.join(reasons)}")
    return findings


def audit(root: Path) -> list[str]:
    records = read_catalog(root)
    findings = []
    for index, record in enumerate(records):
        for previous in records[:index]:
            reasons = duplicate_reasons(record, previous)
            if reasons:
                findings.append(f"{record['id']} 与 {previous['id']}：{'、'.join(reasons)}")
    return findings


def register(root: Path, draft: Path, update: bool = False) -> None:
    record = load(draft)
    if record.get("record_type") != "story":
        raise StoryError("只能登记或更新正式故事；保留选题由全局档案维护")
    records = read_catalog(root)
    exists = any(item["id"] == record.get("id") for item in records)
    if exists != update:
        raise StoryError("故事已存在，请用 update" if exists else "故事尚未登记，请用 register")
    findings = check_candidate(root, record, exclude_id=record["id"] if update else None)
    if findings:
        raise StoryError("发现重复或高度相似故事：\n- " + "\n- ".join(findings))
    if update:
        records = [record if item["id"] == record["id"] else item for item in records]
    else:
        records.append(record)
    write_catalog(root, records)
