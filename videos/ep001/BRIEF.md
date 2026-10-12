---
workflow: general-video
flow: automation
storyboard: no
message: "米勒爷爷想邀请结婚四十年的太太共进晚餐，在爸爸鼓励下终于打电话，女儿等着听结果。"
destination: short-video
aspect: 1080x1920
language: en-US speech, en+zh subtitles
audience: 想跟着日常情景剧学英语的中文观众
length: 34.97s
---

## Source

唯一剧本来源：`../../series/xiangwei/stories.jsonl` 中的 `ST001`。对白、中文字幕、镜头安排和连续线索均从该记录读取，不在本目录另存一份故事文本。

## Continuity

复用系列固定的爸爸、女儿、米勒爷爷和店内场景参考图；配音配置统一来自 `../../series/xiangwei/voices.json`。人物外貌不随镜头变化。全片无中文口播，无错误镜像，店铺没有英文店名。

## 2026-10-11 concept revision

用户反馈当前版本的构思不满意，希望以故事对话吸引观众。全局故事库的 `ST001` 已改为“约会还没约成”：米勒爷爷想邀请结婚四十年的太太共进晚餐，在店里打电话，爸爸和女儿等他得到答复。核心表达为 `How about dinner tonight?`。根据实际配音剪为 29.46 秒，英语对白、中英字幕，情节由人物说的话推进。

## 2026-10-11 limited-animation film pass

用户看过米勒爷爷拿起手机的动作测试后，要求直接设计整片。沿用 `ST001` 的对白、配音和总时长；在进店、坦白、拿起手机、电话后的围布动作补关键姿势。所有姿势都从本集固定人物和店铺画面编辑得来，保持同一人物和场景。整片是有动作姿势切换的有限动画，不使用口型同步。用户确认最终 Studio 预览后，正式 MP4 已导出至 `renders/ep001-animated-final.mp4`，并登记到 `outputs/ep001_daily/final.mp4`。

## 2026-10-11 daughter spatial continuity

女儿从开场就在街窗旁、画面左侧的低矮玩具架处玩红色玩具车。电话响起后，她在同一位置抬头、从架旁探出问话；爸爸展开围布时，她仍在玩具架旁看着。她可以因近景裁切暂时不入画，但不能在玩具角入画的宽镜头里凭空消失。已为全部相关关键姿势制作连续性画面，保持原英语对白、双语字幕和时长。

修订版导出到 `renders/ep001-daughter-continuity.mp4`，历史任务的交付文件更新为 `../../outputs/ep001_daily/final.mp4`。

## 2026-10-12 dialogue and learning pass

保留约会故事，开头缩为“我今晚有个约会”，追问改成更自然的 `Who's it with?`。根据实际英文配音时长重建镜头、字幕和停顿，总时长 34.967 秒。追问、坦白、惊讶和鼓励使用说话人近景与听者反应；通话固定右手拿电话，女儿在玩具角探头。结尾爸爸指向椅子，米勒爷爷准备入座。口语卡先跟读 `How about dinner tonight?`，再换词练习 `How about coffee tomorrow?`。

`generate_voice.py` 可复用未改动的配音；`build_composition.py` 从 JSONL 和 WAV 时长重建全部七段有限动画，不再覆盖成单图推拉。`timing.json`、字幕与教学卡也同步生成。导出文件以 `../../outputs/ep001_daily/final.mp4` 为准。

## 2026-10-12 executable shot-library pass

第一集与第二集改用同一套 `../daily_voice.py`、`../daily_composition.py`。每句 `shot`、`emotion`、`action.id` 与 `listener_reaction` 必须在全局镜头库命中具体素材；第一集现为十句对白镜头加一段学习卡，时长 34.967 秒。补爸爸惊讶、米勒右手持手机时的犹豫与释然画面；原先左手手机图不再使用。任务页镜头时间由构建脚本同步更新。
