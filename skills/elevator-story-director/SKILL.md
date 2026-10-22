---
name: elevator-story-director
description: Design or revise an Elevator Zero episode's character action, English dialogue beats, reactions and shots before video production.
---

# 零号电梯 · 故事导演

适用于构思或修改《零号电梯》单集。先读 `series/elevator_zero/stories.jsonl` 与 `series/elevator_zero/series.md`，检查核心事件、英语表达和连续线索是否已出现。岚与蒂克是常驻；新乘客要有一个可见的具体需求，电梯门后的世界可以变化。

让前几秒出现行动或悬念。每句英文推动人物的选择、回应或关系；核心表达至少在两个真实情境中出现，结尾有可见的结果。剧本中的每句记录 `speaker/en/zh/shot/emotion/action/pause_after`，`shot` 必须存在于 `assets/fixed.json` 或先补相应资产。镜头在说话人与听者反应间切换；道具手别、人物位置和门外世界要连续。

**正例：** 诺亚喊 “Hold the door!” 后继续跑，岚撑门，蒂克倒数；抵达时诺亚再请蒂克扶门，随后递出灯。英语直接改变了故事动作。

**反例：** 乘客平静地逐句说英语、岚逐句翻译，人物没有目标；或同一盏灯一会儿换手、人物尚在电梯内又突然回到桥上。

输出给制作方：一句悬念、三段情节推进、逐句结构化对白及每句对应镜头/反应、结束动作、抖音标题和 10–20 字简介。修改失败时先重写缺少行动的情节，再调整台词和镜头；写入全局 JSONL 后运行 `python3 -m elevator.cli check`，查重失败必须换事件或表达。
