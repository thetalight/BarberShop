---
name: elevator-video-qa
description: Review an Elevator Zero HyperFrames episode and exported MP4 for story continuity, bilingual captions, voice timing and usable daily rebuilds.
---

# 零号电梯 · 成片检查

适用于单集重建、审核和导出。先核对全局 JSONL、固定图、声音清单和工程是否对应。按 `videos/<episode>/AGENTS.md` 执行；视频本身遵循可用 HyperFrames 技能。只让通过身份、人数、道具手别与空间检查的 LTX 片段进入正式工程；候选片的漂亮单帧不等于整段可用。

检查顺序：

1. `python3 -m elevator.cli check`；声音清单的英文、中文和说话人与 JSONL 一致，画面起止由实际 WAV 时长生成。
2. HyperFrames `check`：先消除错误，再检查字幕安全区、对比度、布局采样和时间轴。视觉溢出若是作者有意的取景，应明确声明。
3. 在故事钩子、情节转折、情绪结果、学习卡各抽帧；审视固定角色面貌、位置、道具手别、说话人和字幕。移动镜头还要看首中末三帧。
4. 验证导出 MP4 的视频与音频流、实际时长、首尾帧，以及本地故事工作台中的成片链接。若未实际听音频，不评价发音和音色情绪。

**正例：** LTX 候选末段让男孩消失，就只取前两秒身份稳定的部分；下一镜仍能解释他如何进门。

**反例：** 只看生成成功信息就使用整段；画面里男孩已在电梯内，后续镜头又让他在桥上奔跑；只做源码检查而不查看最终 MP4。

输出简短 QA 记录：检查对象与版本、通过证据、具体时间的缺陷、修复与复查结果、未能确认的事项。发现错误先修故事或资产引用，再重建并复查受影响的镜头和最终 MP4。
