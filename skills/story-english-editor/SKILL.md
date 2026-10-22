---
name: story-english-editor
description: Edit spoken English and Chinese subtitles for Elevator Zero story episodes, keeping one useful expression teachable through the plot.
---

# 零号电梯 · 英语教学编辑

适用于英文对白、双语字幕与结尾跟读。先读全局 `stories.jsonl` 的本集记录，按角色年龄和场景检查美式口语自然度。岚能正常交流；蒂克语句短而机敏；孩子用符合年龄的短句。英语是角色真实要说的话，中文是简洁准确的字幕，不让角色在剧情里逐句翻译。

每集只有一个核心表达，剧情中至少两次以不同用途出现；结尾用同一句和一个可迁移变体，再给观众开口时间。短视频节奏由录音决定：修改对白后先重做本句英语声音，再按实际时长生成画面和字幕。第一句话要容易听清，长句拆开或留出动作停顿。

**正例：** “Hold the door!” 在赶电梯时喊一次，到妹妹家门口又请蒂克扶门；结尾再练 “Hold the elevator, please!”。

**反例：** 为凑教学点让乘客反复说同一句、中文含义比英文多出信息、字幕和 WAV 文本不同，或跟读卡刚读完就切走。

输出为：逐句 `en/zh` 修订建议、表达的自然用法与变体、预计学习负担、需要重新生成的声音编号。写回 JSONL 后运行 `python3 -m elevator.cli check`；如听不清或字幕过密，先缩短台词，再重录与重建，不单纯加快语速。
