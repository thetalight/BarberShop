# 老爸的英语理发店 · 日更英语情景剧

**一家理发店，每天一段生活英语。** 中国爸爸在美国社区经营理发店，四岁的女儿放学后常来。上班族熟客、退休熟客和邻店老板持续出现，每天由一件小事带出一个生活英语表达。故事主要发生在店内；视频全部使用英语旁白与对话，字幕同时显示英文原文和中文翻译。

## 本地工作台

```bash
python3 -m barber.web --port 8765
```

打开 <http://127.0.0.1:8765/> 查看系列开场、30 条日更选题、核心表达、连续线索、固定人物与已完成任务。服务只监听 `127.0.0.1`，页面只读。旧样片已删除。

## 单一故事档案

所有活动故事文字都保存在 **`series/xiangwei/stories.jsonl`**，每行一条 JSON。`ST000` 是已制作的英文旁白系列开场，含逐段英文和中文字幕；`ST001`、`ST002` 是已制作的日更对话视频；`ST003`～`ST030` 是待写对话的日更选题。每条日更记录包含：

- `intro`：10～20 字对外简介，不计标点和空格。
- `category`：`service`（接待与服务）、`chat`（顾客闲聊）或 `interaction`（父女与邻里）。
- `setting`：`shop` 或 `community`；每 10 条有 9 条在店内。
- `core_expression`、`meaning`、`variant`：本集核心句、中文意思和一个简单变体。
- `participants`、`hook`、`beats`、`payoff`：角色与小事件。
- `continuity_in`、`continuity_out`：从旧集承接和留给后续的小线索。

选题推进到 `scripted` 或 `produced` 时，必须补 6～10 句 `dialogue`，每句包含 `speaker`、`en`、`zh`、镜头、情绪、动作、听者反应和停顿，并补全 `shot_plan` 与 `learning_card`。镜头动作必须在全局镜头库中命中具体资产。同一条核心表达在对话中自然出现两次。添加新故事前执行：

```bash
python3 -m barber.cli story list
python3 -m barber.cli story check
python3 -m barber.cli story check --file /tmp/new_story.json
python3 -m barber.cli story register --file /tmp/new_story.json
```

修改已有记录使用 `story update --file /tmp/new_story.json`。查重会检查 ID、标题、核心事件、核心英语表达和高度相似的梗概。故事库是唯一文案来源，避免把每天的剧本散放到单集目录。

## 固定素材与视频制作

人物和店铺设定见 [系列设定](series/xiangwei/series.md)。`series/xiangwei/assets/fixed.json` 管理爸爸、女儿、三位常驻配角和美国社区店铺的参考图；`series/xiangwei/voices.json` 保存女儿的固定英文配音音色。固定人物、场景与女儿音色在后续视频中复用，偶尔出现的新顾客才按集新增。可以检查或生成固定资产：

```bash
python3 -m barber.cli assets
```

视频前 3 秒进入问题，用 6～10 句英语对话完成一件小事，最后保留原句与变体各自的跟读时间。时长由实际配音决定，目前第一、二集约 35 秒、26 秒。系列开场项目在 `videos/intro/`，日更项目在 `videos/ep001/`、`videos/ep002/`；两集共用 `videos/daily_voice.py` 和 `videos/daily_composition.py`。制作顺序：

```bash
python3 -m unittest discover -s tests
python3 videos/ep002/generate_voice.py
python3 videos/ep002/build_composition.py
cd videos/ep002 && npm run check && npm run render -- --output renders/ep002-daily.mp4
```

生成的成片位于本地 `outputs/` 或项目的 `renders/`，不纳入代码仓库。
