"""The one JSONL archive for Elevator Zero."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path('series/elevator_zero/stories.jsonl')
ASSETS = Path('series/elevator_zero/assets/fixed.json')


class StoryError(ValueError):
    pass


def normalize(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def shots(root: Path = ROOT) -> dict:
    return json.loads((root / ASSETS).read_text(encoding='utf-8'))['shots']


def validate(record: dict, shot_ids: set[str]) -> None:
    if record.get('schema_version') != 2 or record.get('series_id') != 'elevator_zero':
        raise StoryError('Story schema or series ID is invalid')
    if not re.fullmatch(r'EZ\d{3}', record.get('id', '')):
        raise StoryError('Story ID must be EZ001 style')
    if record.get('record_type') != 'story' or record.get('status') not in {'idea', 'scripted', 'produced'}:
        raise StoryError(f"{record['id']}: invalid type/status")
    for key in ('title', 'intro', 'publish_title', 'event_key', 'core_expression', 'meaning',
                'variant', 'variant_meaning', 'hook', 'premise', 'payoff'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise StoryError(f"{record['id']}: missing {key}")
    if not 10 <= sum(c.isalnum() for c in record['intro']) <= 20:
        raise StoryError(f"{record['id']}: intro must contain 10-20 characters")
    if not 8 <= len(record['publish_title']) <= 50 or '\n' in record['publish_title']:
        raise StoryError(f"{record['id']}: publish title must be 8-50 characters")
    if not isinstance(record.get('beats'), list) or len(record['beats']) < 3:
        raise StoryError(f"{record['id']}: at least three story beats are required")
    if record.get('status') in {'scripted', 'produced'}:
        lines = record.get('dialogue')
        if not isinstance(lines, list) or not 6 <= len(lines) <= 12:
            raise StoryError(f"{record['id']}: scripted story needs 6-12 lines")
        if sum(normalize(record['core_expression']) in normalize(line.get('en', '')) for line in lines) < 2:
            raise StoryError(f"{record['id']}: core phrase needs two uses in story")
        for i, line in enumerate(lines, 1):
            if any(not isinstance(line.get(k), str) or not line[k].strip() for k in ('speaker','en','zh','shot','emotion','action')):
                raise StoryError(f"{record['id']}: line {i} incomplete")
            if line['speaker'] not in record['participants'] or line['shot'] not in shot_ids:
                raise StoryError(f"{record['id']}: line {i} has unknown speaker or shot")
            if not isinstance(line.get('pause_after'), (int, float)) or not .25 <= line['pause_after'] <= 2:
                raise StoryError(f"{record['id']}: line {i} has invalid pause")
        card = record.get('learning_card', {})
        if not 0 <= card.get('repeat_at', -1) < card.get('variant_at', -1) < card.get('duration', -1):
            raise StoryError(f"{record['id']}: invalid learning card")


def validate_catalog(entries: list[dict], shot_ids: set[str]) -> list[dict]:
    ids, events, phrases, titles = set(), set(), set(), set()
    for record in entries:
        validate(record, shot_ids)
        distinct = (('ID', record['id'], ids), ('event', record['event_key'], events),
                    ('phrase', normalize(record['core_expression']), phrases),
                    ('publish title', normalize(record['publish_title']), titles))
        for label, value, seen in distinct:
            if value in seen:
                raise StoryError(f'Duplicate {label}: {value}')
            seen.add(value)
    return entries


def read_catalog(root: Path = ROOT) -> list[dict]:
    path = root / CATALOG
    if not path.is_file():
        raise StoryError(f'Missing story archive: {path}')
    entries = []
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise StoryError(f'Invalid JSON on line {n}: {exc}') from exc
    return validate_catalog(entries, set(shots(root)))


def get_story(story_id: str, root: Path = ROOT) -> dict:
    for row in read_catalog(root):
        if row['id'] == story_id:
            return row
    raise StoryError(f'Unknown story: {story_id}')


def update_story(record: dict, root: Path = ROOT) -> None:
    entries = read_catalog(root)
    if not any(row['id'] == record['id'] for row in entries):
        raise StoryError('Cannot update an unregistered story')
    updated = [record if row['id'] == record['id'] else row for row in entries]
    validate_catalog(updated, set(shots(root)))
    temp = root / CATALOG.with_suffix('.jsonl.tmp')
    try:
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in updated), encoding='utf-8')
        temp.replace(root / CATALOG)
    finally:
        temp.unlink(missing_ok=True)
