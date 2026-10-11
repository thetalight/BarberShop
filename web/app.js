let dashboard = null;
let activeFilter = "all";
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]);
const statusLabel = {produced:"已制作",scripted:"已写对话",idea:"待写对话",reserved:"保留选题"};
const categoryLabel = {intro:"系列开场",service:"接待与服务",chat:"日常闲聊",interaction:"父女与邻里"};
const participantLabel = {dad:"爸爸",daughter:"女儿",commuter_regular:"上班族熟客",retired_regular:"退休熟客",neighbor_owner:"邻店老板",new_customer:"新顾客"};
const jobLabel = {selected:"已选用",ready:"已完成",needs_review:"待审核",failed:"失败",running:"生成中",benchmark_ready:"测试完成"};

function dateLabel(value) {
  if (!value) return "时间未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).format(date);
}

function renderStats() {
  const summary = dashboard.summary;
  $("#storyCount").textContent = summary.daily_ideas;
  $("#producedCount").textContent = summary.produced_stories;
  $("#taskCount").textContent = summary.completed_tasks;
  $("#assetCount").textContent = summary.fixed_assets;
  $("#sourcePath").textContent = dashboard.source;
  const barber = dashboard.fixed_assets.find((item) => item.id === "human_barber_v1");
  if (barber) $("#heroBarber").src = barber.url;
}

function renderStories() {
  const query = $("#storySearch").value.trim().toLocaleLowerCase();
  const category = $("#categoryFilter").value;
  const items = dashboard.stories.filter((story) => {
    const status = activeFilter === "all" ||
      (activeFilter === "daily" && story.format === "daily_english") ||
      (activeFilter === "intro" && story.format === "series_intro") ||
      story.status === activeFilter;
    const haystack = [story.id,story.title,story.intro,story.guest,story.premise,story.reveal,story.event_key,story.hair_request,story.core_expression,story.meaning,story.category,categoryLabel[story.category],...(story.voiceover || []),...(story.dialogue || []).flatMap((line) => [line.en,line.zh]),...(story.participants || []).map((id) => participantLabel[id] || id)].join(" ").toLocaleLowerCase();
    return status && (category === "all" || story.category === category || (category === "intro" && story.format === "series_intro")) && (!query || haystack.includes(query));
  });
  $("#storyResult").textContent = `${items.length} / ${dashboard.stories.length}`;
  $("#storyGrid").innerHTML = items.length ? items.map((story) => `
    <article class="story-card">
      <div class="story-top"><span class="story-id">${story.format === "series_intro" ? "序章 · " : story.format === "daily_english" ? `DAY ${String(story.day).padStart(2,"0")} · ` : ""}${escapeHtml(story.id)}</span><span class="badge ${escapeHtml(story.status)}">${escapeHtml(statusLabel[story.status] || story.status)}</span></div>
      <h3>${escapeHtml(story.title)}</h3>
      <p class="story-intro">${escapeHtml(story.intro)}</p>
      ${["daily_english","series_intro"].includes(story.format) ? `<p class="expression">${escapeHtml(story.core_expression)}</p><p class="expression-meaning">${escapeHtml(story.meaning)}</p>` : ""}
      <p>${escapeHtml(story.premise)}</p>
      <div class="story-meta">${story.format === "series_intro" ? '<span>系列开场</span><span>父女介绍</span>' : story.format === "daily_english" ? `<span>${escapeHtml(categoryLabel[story.category] || story.category)}</span><span>${story.setting === "shop" ? "理发店内" : "社区场景"}</span>` : `<span>顾客 · ${escapeHtml(story.guest)}</span><span>发型 · ${escapeHtml(story.hair_request)}</span>`}</div>
      <button class="card-action" data-story="${escapeHtml(story.id)}">查看故事全文 →</button>
    </article>`).join("") : '<div class="empty">没有符合条件的故事。</div>';
}

function showStory(id) {
  const story = dashboard.stories.find((item) => item.id === id);
  if (!story) return;
  const beats = (story.beats || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const narration = Object.entries(story.narration || {}).map(([shot,text]) => `<div class="narration-line"><strong>${escapeHtml(shot)}</strong>${escapeHtml(text)}</div>`).join("");
  const dialogue = (story.dialogue || []).map((line) => `<div class="narration-line"><strong>${escapeHtml(participantLabel[line.speaker] || line.speaker)} · ${escapeHtml(line.en)}</strong><span>${escapeHtml(line.zh)}</span></div>`).join("");
  const shots = (story.shot_plan || []).map((shot) => `<li><strong>${escapeHtml(shot.seconds)} 秒：</strong>${escapeHtml(shot.visual)}</li>`).join("");
  const daily = story.format === "daily_english";
  const intro = story.format === "series_intro";
  $("#storyDetail").innerHTML = `
    <p class="eyebrow">${intro ? "序章 · " : daily ? `DAY ${String(story.day).padStart(2,"0")} · ` : ""}${escapeHtml(story.id)} · ${escapeHtml(statusLabel[story.status] || story.status)}</p>
    <h2>${escapeHtml(story.title)}</h2>
    <p class="detail-intro">${escapeHtml(story.intro)}</p>
    <div class="detail-meta">${intro || daily ? `${intro ? "系列开场" : escapeHtml(categoryLabel[story.category] || story.category)}　/　${story.setting === "shop" ? "理发店内" : "社区场景"}　/　角色：${escapeHtml((story.participants || []).map((id) => participantLabel[id] || id).join("、"))}` : `顾客：${escapeHtml(story.guest)}　/　发型：${escapeHtml(story.hair_request)}`}</div>
    ${intro || daily ? `<h3>本集核心表达</h3><p class="detail-expression">${escapeHtml(story.core_expression)} <span>${escapeHtml(story.meaning)}</span></p>${daily ? `<p>简单变体：${escapeHtml(story.variant)}</p>` : ""}` : ""}
    <h3>故事梗概</h3><p>${escapeHtml(story.premise)}</p>
    ${!daily && !intro && story.reveal ? `<h3>剧情揭示</h3><p>${escapeHtml(story.reveal)}</p>` : ""}
    ${beats ? `<h3>故事节点</h3><ol>${beats}</ol>` : ""}
    ${intro ? `<h3>女儿英文旁白 · 中文字幕</h3>${(story.voiceover || []).map((line, index) => `<div class="narration-line"><strong>${escapeHtml(line)}</strong><span>${escapeHtml(story.voiceover_zh?.[index] || "")}</span></div>`).join("")}` : ""}
    ${dialogue ? `<h3>英语对话 · 中英双语字幕</h3>${dialogue}` : ""}
    ${shots ? `<h3>镜头安排（暂定）</h3><ol>${shots}</ol>` : ""}
    ${story.production_notes?.length ? `<h3>制作要点</h3><ul>${story.production_notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>` : ""}
    ${daily && (story.continuity_in?.length || story.continuity_out?.length) ? `<h3>连续线索</h3>${story.continuity_in?.length ? `<p>承接：${escapeHtml(story.continuity_in.join("；"))}</p>` : ""}${story.continuity_out?.length ? `<p>留下：${escapeHtml(story.continuity_out.join("；"))}</p>` : ""}` : ""}
    ${narration ? `<h3>镜头旁白</h3>${narration}` : ""}
    ${story.notes ? `<h3>备注</h3><p>${escapeHtml(story.notes)}</p>` : ""}
    ${story.source ? `<p class="detail-meta">来源：${escapeHtml(story.source)}</p>` : ""}`;
  $("#storyDialog").showModal();
}

function renderTasks() {
  $("#taskResult").textContent = String(dashboard.tasks.length);
  $("#taskList").innerHTML = dashboard.tasks.length ? dashboard.tasks.map((task) => {
    const jobs = task.jobs.map((job) => `<li><code>${escapeHtml(job.id)}</code><span>${escapeHtml(jobLabel[job.status] || job.status)}${job.elapsed_seconds ? ` · ${Number(job.elapsed_seconds).toFixed(1)} 秒` : ""}</span></li>`).join("");
    return `<article class="task-card">
      ${task.cover_url ? `<img class="task-cover" src="${escapeHtml(task.cover_url)}" alt="${escapeHtml(task.title)}封面">` : '<div class="task-cover"></div>'}
      <div class="task-body">
        <div class="task-top"><span class="task-id">${escapeHtml(task.id)}</span><span class="task-kind">${escapeHtml(task.kind)}</span><span class="badge">${escapeHtml(task.status)}</span></div>
        <h3>${escapeHtml(task.title)}</h3>
        ${task.intro ? `<p class="task-intro">${escapeHtml(task.intro)}</p>` : ""}
        <div class="task-facts"><span>${task.duration_seconds ? `${task.duration_seconds} 秒` : "时长待定"}</span><span>${task.selected_count} / ${task.shot_count} 镜已选</span><span>${dateLabel(task.updated_at)}</span></div>
        <div class="task-actions">${task.video_url ? `<button class="primary-button" data-play="${escapeHtml(task.id)}">播放成片</button>` : ""}${task.subtitle_url ? `<a class="ghost-button" href="${escapeHtml(task.subtitle_url)}" download>下载字幕</a>` : ""}</div>
        <details class="task-details"><summary>查看 ${task.job_count} 条生成任务记录</summary><ul class="job-list">${jobs || "<li>尚无生成记录</li>"}</ul></details>
      </div>
    </article>`;
  }).join("") : '<div class="empty">当前还没有视频任务。</div>';
}

function renderAssets() {
  $("#assetGrid").innerHTML = dashboard.fixed_assets.map((asset) => `<figure class="asset-card"><img loading="lazy" src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.label)}"><figcaption>${escapeHtml(asset.label)}<small>${escapeHtml(asset.id)}</small></figcaption></figure>`).join("");
}

document.addEventListener("click", (event) => {
  const filter = event.target.closest("[data-filter]");
  if (filter) {
    activeFilter = filter.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((button) => button.classList.toggle("active", button === filter));
    renderStories();
  }
  const story = event.target.closest("[data-story]");
  if (story) showStory(story.dataset.story);
  const play = event.target.closest("[data-play]");
  if (play) {
    const task = dashboard.tasks.find((item) => item.id === play.dataset.play);
    if (task?.video_url) {
      $("#videoTitle").textContent = task.title;
      $("#videoPlayer").src = task.video_url;
      $("#videoDialog").showModal();
    }
  }
  if (event.target.matches("[data-close]")) event.target.closest("dialog").close();
});
document.querySelectorAll("dialog").forEach((dialog) => dialog.addEventListener("close", () => {
  if (dialog.id === "videoDialog") { $("#videoPlayer").pause(); $("#videoPlayer").removeAttribute("src"); $("#videoPlayer").load(); }
}));
$("#storySearch").addEventListener("input", () => dashboard && renderStories());
$("#categoryFilter").addEventListener("change", () => dashboard && renderStories());

fetch("/api/dashboard", {cache:"no-store"}).then((response) => {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}).then((data) => {
  dashboard = data;
  renderStats(); renderStories(); renderTasks(); renderAssets();
}).catch((error) => {
  $("#storyGrid").innerHTML = `<div class="empty">读取本地资料失败：${escapeHtml(error.message)}</div>`;
  $("#taskList").innerHTML = '<div class="empty">请确认本地服务仍在运行。</div>';
});
