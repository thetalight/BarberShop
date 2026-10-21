# 零号电梯 · 奇想英语情景剧

每扇门后都有一个故事，一句用得上的英语。岚与会说话的黄铜小钟蒂克守着一部通往奇想世界的电梯；每天一位乘客带着一件小事上来。英文对白推动故事，画面同时显示英文原句和中文字幕，结尾给观众原句与变体的跟读时间。

## 本地故事工作台

```bash
python3 -m elevator.cli serve --port 8799
```

打开 <http://127.0.0.1:8799/>，查看历史任务、所有构思、抖音标题、10–20 字简介、核心英语表达与固定镜头。服务只监听 `127.0.0.1`，页面只读。

## 故事档案与查重

系列唯一故事文字档案：[series/elevator_zero/stories.jsonl](series/elevator_zero/stories.jsonl)。目前收录 30 个各不相同的事件和核心表达。每条记录包含人物、情节钩子、结果、连续性线索、抖音标题和简介；进入剧本阶段后，逐句记录英文、中文、说话人、镜头、动作、情绪和停顿。

```bash
python3 -m elevator.cli check
python3 -m elevator.cli list
```

校验会拒绝重复的事件、核心表达与发布标题，也会检查 10–20 字简介、剧本所用镜头和每集至少两次有情境的核心句。固定角色与场景见 [系列设定](series/elevator_zero/series.md)，固定镜头登记在 [fixed.json](series/elevator_zero/assets/fixed.json)。

## 第一集制作

第一集工程位于 [videos/zero-ep001](videos/zero-ep001)。从全局档案读取对白后，先用本地 Kokoro 生成英语声音，再按实际 WAV 时长排画面与双语字幕：

```bash
PYTHONPATH=. python3 videos/zero-ep001/generate_voice.py
PYTHONPATH=. python3 videos/zero-ep001/build_composition.py
cd videos/zero-ep001
npm run check
npm run render -- --output ../../outputs/zero-ep001/final.mp4 --fps 24
```

可选的 LTX 镜头使用本机 `/Users/product/sex` 的模型。候选镜头须先检查人物身份、月亮灯手别与空间连贯；只有审核通过并命名为 `assets/ltx/door_rush_approved.mp4` 时，重建脚本才把它放进开头。候选结果不会自动进入成片。

每条视频先有一个可见的行动和悬念，再用角色英语对话推进；字幕提供理解帮助，结尾练习提供开口机会。每天写下一集前运行故事档案查重。
