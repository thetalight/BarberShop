# 固定镜头状态图提示词记录

本次使用内置 imagegen，以 `assets/shots/` 现有人物、店铺和道具基底图片做编辑；新图保存在同目录并由 `shot_library.json` 的 `takes` 引用。生成时采用以下提示词要点（英语提交），保留原始人物身份和暖色电影化 3D 风格：

- **爸爸惊讶**：Same Chinese father barber, same cream shirt and brown apron in the same neighborhood barbershop; clear raised eyebrows and open mouth of genuine surprise, medium close shot; warm cinematic stylized 3D; no text or logo, no incorrect mirror reflection.
- **米勒右手持手机，犹豫与释然**：Same silver-haired retired regular in his green plaid shirt, right hand holding the black smartphone (viewer left), left hand by his neck when nervous; preserve father, daughter and shop layout; then a relieved expression with the phone lowered in the same right hand; vertical 9:16, no logos or false reflections.
- **米勒湿帽与玩具鱼**：Same retired regular in the fixed shop, carrying a damp olive fishing hat; separate state clearly showing a small orange-and-blue plastic toy fish brought back by Milo; preserve clothing, face, shop and lighting.
- **女儿接鱼**：Edit the fixed four-year-old daughter in the window-side toy corner, preserving face, green flower hair clip, green sweater and tan corduroy overalls. Replace the red toy car in her hands with the orange-and-blue plastic fish from the Miller reference. She looks down at it and speaks playfully. No car in her hands, natural fingers, no text, no mirror.

`dad_encourages_miller_v1.jpg`、`dad_points_chair_v1.jpg`、`daughter_peeks_toy_shelf_v1.jpg`、`retired_regular_calls_right_v1.jpg` 是从第一集已制作的固定画面复制到全局镜头库。所有这些图片都是系列共用资产，单集构建脚本按内容哈希复制到本地 `assets/takes/`。
