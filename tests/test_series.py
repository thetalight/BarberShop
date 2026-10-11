"""Checks that the daily English queue stays usable and distinct."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from barber import cli, stories, web


class SeriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="barber-series-test-"))
        self.records = stories.read_catalog(cli.ROOT)
        self.daily = [item for item in self.records if item["format"] == "daily_english"]
        stories.write_catalog(self.root, self.records)
        self.first = next(item for item in self.daily if item["status"] == "idea")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.root)

    def test_30_day_rotation_and_store_ratio(self) -> None:
        self.assertEqual(len(self.daily), 30)
        self.assertEqual([item["id"] for item in self.daily], [f"ST{n:03d}" for n in range(1, 31)])
        for start in (0, 10, 20):
            group = self.daily[start:start + 10]
            self.assertEqual({kind: sum(item["category"] == kind for item in group)
                              for kind in stories.DAILY_CATEGORIES},
                             {"service": 3, "chat": 4, "interaction": 3})
            self.assertEqual(sum(item["setting"] == "shop" for item in group), 9)

    def test_daily_ideas_have_short_intro_and_single_core_phrase(self) -> None:
        self.assertEqual(len({stories.normalize(item["core_expression"]) for item in self.daily}), 30)
        self.assertEqual(next(item for item in self.daily if item["id"] == "ST001")["status"], "produced")
        self.assertEqual(sum(item["status"] == "idea" for item in self.daily), 29)
        for record in self.daily:
            self.assertEqual(record["format"], "daily_english")
            self.assertIn(record["status"], {"idea", "scripted", "produced"})
            self.assertTrue(10 <= sum(char.isalnum() for char in record["intro"]) <= 20)
        draft = copy.deepcopy(self.first)
        draft["intro"] = "太短"
        with self.assertRaises(stories.StoryError):
            stories.validate(draft)

    def test_duplicate_expression_is_rejected(self) -> None:
        draft = copy.deepcopy(self.first)
        draft.update(id="ST031", day=31, title="另一种欢迎", event_key="different_event",
                     premise="另一位顾客进入店铺，爸爸说出同一句话。")
        findings = stories.check_candidate(self.root, draft)
        self.assertTrue(any("核心英语表达相同" in item for item in findings))

    def test_new_daily_story_can_be_registered_once(self) -> None:
        draft = copy.deepcopy(self.first)
        draft.update(id="ST031", day=31, title="寻找雨伞", intro="顾客的雨伞不见了，父女一起帮忙找。",
                     event_key="missing_umbrella", core_expression="Where did I put my umbrella?",
                     meaning="我把雨伞放哪了？", variant="Where did I put my keys?",
                     hook="顾客发现雨伞不见了。", premise="顾客在店里找不到雨伞，爸爸和女儿帮他寻找。",
                     payoff="雨伞在门后的伞桶里。", beats=["顾客找伞", "父女帮忙", "门后找到"],
                     continuity_in=[], continuity_out=[])
        path = self.root / "draft.json"
        path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        stories.register(self.root, path)
        self.assertEqual(stories.get_story(self.root, "ST031")["title"], "寻找雨伞")
        with self.assertRaises(stories.StoryError):
            stories.register(self.root, path)

    def test_scripted_status_requires_dialogue_and_repetition(self) -> None:
        draft = copy.deepcopy(self.first)
        draft["status"] = "scripted"
        with self.assertRaises(stories.StoryError):
            stories.validate(draft)
        draft["dialogue"] = [{"speaker": "dad", "en": "Good morning.", "zh": "早上好。"} for _ in range(6)]
        with self.assertRaises(stories.StoryError):
            stories.validate(draft)
        draft["dialogue"][0]["en"] = draft["core_expression"]
        draft["dialogue"][3]["en"] = draft["core_expression"]
        stories.validate(draft)

    def test_dashboard_shows_intro_and_daily_queue(self) -> None:
        data = web.dashboard_data()
        self.assertEqual(data["summary"]["daily_ideas"], 30)
        self.assertEqual(len(data["stories"]), 31)
        self.assertEqual(data["stories"][0]["id"], "ST000")
        self.assertEqual(data["stories"][0]["language"], "en-US")
        self.assertEqual(len(data["fixed_assets"]), 10)
        self.assertEqual([item["id"] for item in data["tasks"]], ["ep001_daily", "ep000_daily"])
        self.assertEqual(data["tasks"][0]["kind"], "英语情景剧")
        self.assertEqual(data["tasks"][1]["kind"], "系列开场")

    def test_history_recognizes_daily_episode_only(self) -> None:
        daily = self.root / "episodes/ep001_daily"
        legacy = self.root / "episodes/ep002_human"
        daily.mkdir(parents=True)
        legacy.mkdir(parents=True)
        (daily / "episode.json").write_text(json.dumps({"title": "新日更", "shots": []}, ensure_ascii=False), encoding="utf-8")
        tasks = web.task_data(self.root, self.records)
        self.assertEqual([item["id"] for item in tasks], ["ep001_daily"])
        self.assertEqual(tasks[0]["kind"], "英语情景剧")

    def test_video_visual_identity_ignores_editorial_timing(self) -> None:
        plan = {"visual_style": "Warm stylized film", "video_style": "One continuous shot"}
        shot = {"prompt": "Father at work", "motion_prompt": "He turns to the customer",
                "narration": "Old line", "target_seconds": 6}
        video = cli.config()["video"]
        original = cli.video_visual_key(plan, shot, "frame-sha", video, 1011, 145)
        shot["narration"] = "New line"
        shot["target_seconds"] = 3
        self.assertEqual(original, cli.video_visual_key(plan, shot, "frame-sha", video, 1011, 145))
        shot["motion_prompt"] = "A different action"
        self.assertNotEqual(original, cli.video_visual_key(plan, shot, "frame-sha", video, 1011, 145))


if __name__ == "__main__":
    unittest.main()
