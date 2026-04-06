import { getElements } from "./dom.js";
import { createApi, isHttpStatus } from "./api.js";
import {
  buildCurrentEpisodeMarkdown,
  buildMarkdownToc,
  buildStoryMarkdown,
  buildStoryStaticMarkdown,
  escapeHtml,
  formatDate,
  renderMarkdown,
} from "./markdown.js";

const bootstrap = window.__STORYROOM_BOOTSTRAP__ || {};
const topicPresets = Array.isArray(bootstrap.topicPresets) ? bootstrap.topicPresets : [];
const runtimeConfig = bootstrap.runtimeConfig || {};
const api = createApi(bootstrap.sessionToken || "");
const els = getElements(document);

const DEFAULT_RESULT_EMPTY = "这里会展示最佳创意、故事 Bible、分集规划和剧本文本。";
const DEFAULT_PROGRESS_EMPTY = "生成开始后，这里会显示每个环节的实时状态。";
const DEFAULT_PREVIEW_EMPTY = "生成开始后，这里会逐步显示创意候选、选题结果、审稿意见和分集卡。";
const DEFAULT_DIAGNOSTICS_EMPTY = "先点击“测试模型连接”，这里会显示响应延迟、模型名和返回摘要。";

const state = {
  history: {
    page: 1,
    totalPages: 1,
    total: 0,
    query: "",
    sort: "created_desc",
    items: [],
  },
  story: {
    activeId: null,
    current: null,
    activeEpisodeIndex: 0,
    shellKey: "",
    draft: { title: "", notes: "" },
    markdownCache: new Map(),
    pendingGeneratedStoryId: null,
    pendingGeneratedStory: null,
  },
  job: {
    id: null,
    timer: null,
    lockedPayload: null,
    lastProgressKey: "",
    lastPreviewKey: "",
  },
  undo: {
    story: null,
    timer: null,
    wasCurrent: false,
  },
  inflight: new Set(),
  ui: {
    statusText: "",
    statusError: false,
    statusAction: null,
    debugEnabled: window.localStorage.getItem("storyroom:debug") === "true",
    debugLines: [],
  },
};

function debugLog(label, context = {}) {
  if (!state.ui.debugEnabled) {
    return;
  }
  const payload = Object.keys(context).length ? ` ${JSON.stringify(context)}` : "";
  state.ui.debugLines.unshift(`${new Date().toLocaleTimeString("zh-CN", { hour12: false })} ${label}${payload}`);
  state.ui.debugLines = state.ui.debugLines.slice(0, 10);
  renderDebugStatus();
}

function setStatus(text, { error = false, action = null } = {}) {
  state.ui.statusText = text;
  state.ui.statusError = error;
  state.ui.statusAction = action;
  renderStatus();
}

function renderStatus() {
  els.status.textContent = state.ui.statusText;
  els.status.style.color = state.ui.statusError ? "#9f2d1e" : "var(--muted)";
  if (!state.ui.statusAction) {
    els.statusActions.innerHTML = "";
    return;
  }
  els.statusActions.innerHTML = `<button class="secondary" data-status-action="${escapeHtml(state.ui.statusAction.type)}">${escapeHtml(state.ui.statusAction.label)}</button>`;
}

function renderDebugStatus() {
  els.debugStatus.hidden = !state.ui.debugEnabled;
  els.debugStatus.textContent = state.ui.debugLines.join("\n");
}

function renderJobSnapshot() {
  if (!state.job.lockedPayload) {
    els.jobSnapshot.textContent = "";
    return;
  }
  const payload = state.job.lockedPayload;
  els.jobSnapshot.textContent = `当前任务参数已锁定：${payload.topic || "未命名主题"} · ${payload.num_episodes} 集 · ${payload.max_iterations} 轮审稿。你现在改表单，只会影响下一次生成。`;
}

function setBusy(key, active) {
  if (active) {
    state.inflight.add(key);
  } else {
    state.inflight.delete(key);
  }
  renderButtonStates();
}

async function runBusy(key, task) {
  if (state.inflight.has(key)) {
    return;
  }
  setBusy(key, true);
  try {
    return await task();
  } finally {
    setBusy(key, false);
  }
}

function renderButtonStates() {
  els.saveConfigBtn.disabled = state.inflight.has("save-config");
  els.testModelBtn.disabled = state.inflight.has("test-model");
  els.generateBtn.disabled = state.inflight.has("generate");
  els.refreshHistoryBtn.disabled = state.inflight.has("load-history");
  els.searchHistoryBtn.disabled = state.inflight.has("load-history");
  els.clearHistorySearchBtn.disabled = state.inflight.has("load-history");
  els.prevHistoryBtn.disabled = state.inflight.has("load-history") || state.history.page <= 1;
  els.nextHistoryBtn.disabled = state.inflight.has("load-history") || state.history.page >= state.history.totalPages;

  for (const button of els.result.querySelectorAll("button[data-action]")) {
    const action = button.dataset.action;
    button.disabled = (
      (action === "save-meta" && state.inflight.has("save-meta")) ||
      (action === "delete-story" && state.inflight.has("delete-story")) ||
      (action === "reload-story" && state.inflight.has("load-story")) ||
      (action === "copy-current-md" && state.inflight.has("copy-md"))
    );
  }
}

function collectFormPayload() {
  return {
    topic: els.topicInput.value.trim(),
    constraints: els.constraintsInput.value.trim(),
    api_key: els.apiKeyInput.value,
    model_name: els.modelNameInput.value.trim(),
    base_url: els.baseUrlInput.value.trim(),
    num_episodes: Number(els.numEpisodesInput.value || 6),
    max_iterations: Number(els.maxIterationsInput.value || 2),
    mock: els.useMockInput.checked,
  };
}

function readDraftMeta() {
  const titleInput = document.getElementById("detailTitleInput");
  const notesInput = document.getElementById("detailNotesInput");
  state.story.draft = {
    title: titleInput ? titleInput.value.trim() : (state.story.current?.title || ""),
    notes: notesInput ? notesInput.value.trim() : (state.story.current?.notes || ""),
  };
  return state.story.draft;
}

function getStoryKey(story, draft = state.story.draft) {
  return [
    story.id || "inline",
    story.created_at || "",
    draft.title || story.title || "",
    draft.notes || story.notes || "",
  ].join("|");
}

function getEpisodePayload(story, episodeIndex, draft = state.story.draft) {
  const storyKey = getStoryKey(story, draft);
  let cacheEntry = state.story.markdownCache.get(storyKey);
  if (!cacheEntry) {
    const staticMarkdown = buildStoryStaticMarkdown(story, draft);
    cacheEntry = {
      staticMarkdown,
      episodes: new Map(),
    };
    state.story.markdownCache.clear();
    state.story.markdownCache.set(storyKey, cacheEntry);
    debugLog("markdown-cache-miss", { storyKey });
  }

  if (!cacheEntry.episodes.has(episodeIndex)) {
    const fullMarkdown = buildStoryMarkdown(story, episodeIndex, draft);
    cacheEntry.episodes.set(episodeIndex, {
      fullMarkdown,
      html: renderMarkdown(fullMarkdown),
      toc: buildMarkdownToc(fullMarkdown),
      episodeMarkdown: buildCurrentEpisodeMarkdown(story, episodeIndex, draft),
    });
    debugLog("episode-render-miss", { storyKey, episodeIndex });
  } else {
    debugLog("episode-render-hit", { storyKey, episodeIndex });
  }

  return cacheEntry.episodes.get(episodeIndex);
}

function showResultEmpty(text = DEFAULT_RESULT_EMPTY) {
  state.story.current = null;
  state.story.activeId = null;
  state.story.shellKey = "";
  els.result.innerHTML = `<div class="empty">${escapeHtml(text)}</div>`;
}

function renderTopicPresets() {
  els.topicList.innerHTML = topicPresets.map(item => `
    <div class="topic-card" data-preset-id="${escapeHtml(item.id)}">
      <strong>${escapeHtml(item.label)}</strong>
      <span>${escapeHtml(item.topic)}</span>
      <span>${escapeHtml(item.constraints)}</span>
    </div>
  `).join("");
}

function applyPreset(presetId) {
  const preset = topicPresets.find(item => item.id === presetId);
  if (!preset) return;
  els.topicInput.value = preset.topic;
  els.constraintsInput.value = preset.constraints;
  for (const node of els.topicList.querySelectorAll(".topic-card")) {
    node.classList.toggle("active", node.dataset.presetId === preset.id);
  }
}

function renderDiagnostics(result) {
  if (!result) {
    els.diagnostics.innerHTML = `<div class="empty">${DEFAULT_DIAGNOSTICS_EMPTY}</div>`;
    return;
  }
  els.diagnostics.innerHTML = `
    <div class="diagnostic-card">
      <strong>${escapeHtml(result.message || "测试完成")}</strong>
      <div class="diag-grid">
        <div class="diag-chip"><b>模型</b><br>${escapeHtml(result.model_name || "")}</div>
        <div class="diag-chip"><b>延迟</b><br>${escapeHtml(String(result.latency_ms || 0))} ms</div>
        <div class="diag-chip"><b>Base URL</b><br>${escapeHtml(result.base_url || "默认")}</div>
        <div class="diag-chip"><b>返回摘要</b><br>${escapeHtml(result.response_preview || "")}</div>
      </div>
    </div>
  `;
}

function statusText(status) {
  if (status === "pending") return "等待中";
  if (status === "running") return "进行中";
  if (status === "done") return "已完成";
  if (status === "failed") return "失败";
  return status;
}

function renderProgress(job) {
  if (!job || !Array.isArray(job.stages) || job.stages.length === 0) {
    els.progress.innerHTML = `<div class="empty">${DEFAULT_PROGRESS_EMPTY}</div>`;
    return;
  }
  els.progress.innerHTML = job.stages.map(stage => `
    <div class="progress-item">
      <div class="progress-label">${escapeHtml(stage.label)}</div>
      <div><span class="pill ${escapeHtml(stage.status)}">${statusText(stage.status)}</span></div>
      <div>${escapeHtml(stage.message || "")}</div>
    </div>
  `).join("");
}

function renderPreview(job) {
  const preview = job?.preview || null;
  if (!preview || Object.keys(preview).length === 0) {
    els.preview.innerHTML = `<div class="empty">${DEFAULT_PREVIEW_EMPTY}</div>`;
    return;
  }
  const cards = [];

  if (Array.isArray(preview.ideation?.ideas) && preview.ideation.ideas.length > 0) {
    cards.push(`
      <div class="preview-card">
        <h4>创意池候选</h4>
        <div class="preview-list">
          ${preview.ideation.ideas.map(idea => `
            <div class="preview-item">
              <b>${escapeHtml(idea.title || "")}</b><br>
              ${escapeHtml(idea.agent_name || "")}<br>
              ${escapeHtml(idea.logline || "")}
            </div>
          `).join("")}
        </div>
      </div>
    `);
  }

  if (preview.selection?.selected_idea) {
    cards.push(`
      <div class="preview-card">
        <h4>已选方向</h4>
        <div class="preview-item">
          <b>${escapeHtml(preview.selection.selected_idea.title || "")}</b><br>
          ${escapeHtml(preview.selection.selection_reason || "")}
        </div>
      </div>
    `);
  }

  if (preview.outline?.outline || preview.outline?.characters) {
    cards.push(`
      <div class="preview-card">
        <h4>大纲与人物</h4>
        <div class="preview-item"><b>大纲</b><br>${escapeHtml((preview.outline.outline || "").slice(0, 240) || "暂无")}</div>
        <div class="preview-item"><b>人物</b><br>${escapeHtml((preview.outline.characters || "").slice(0, 240) || "暂无")}</div>
      </div>
    `);
  }

  if (preview.review?.review) {
    const review = preview.review.review;
    cards.push(`
      <div class="preview-card">
        <h4>审稿状态</h4>
        <div class="preview-item">
          <b>第 ${escapeHtml(String(preview.review.iteration || 0))} 轮</b><br>
          ${review.approved ? "审稿通过" : "需要继续修改"}<br>
          ${escapeHtml(review.issues || (review.strengths || []).join("；") || "暂无详细说明")}
        </div>
      </div>
    `);
  }

  if (Array.isArray(preview.planning?.episode_plans) && preview.planning.episode_plans.length > 0) {
    cards.push(`
      <div class="preview-card">
        <h4>分集规划</h4>
        <div class="preview-list">
          ${preview.planning.episode_plans.slice(0, 4).map(item => `
            <div class="preview-item">
              <b>第${escapeHtml(String(item.episode_number || ""))}集 · ${escapeHtml(item.title || "")}</b><br>
              ${escapeHtml(item.goal || "")}<br>
              钩子：${escapeHtml(item.hook || "")}
            </div>
          `).join("")}
        </div>
      </div>
    `);
  }

  if (Array.isArray(preview.writing?.episodes) && preview.writing.episodes.length > 0) {
    cards.push(`
      <div class="preview-card">
        <h4>分集写作进度</h4>
        <div class="preview-item">
          已完成 ${escapeHtml(String(preview.writing.episodes_completed || 0))} / ${escapeHtml(String(preview.writing.num_episodes || 0))} 集
        </div>
        <div class="preview-item"><b>最近产出</b><br>${escapeHtml((preview.writing.episodes[preview.writing.episodes.length - 1] || "").slice(0, 260))}</div>
      </div>
    `);
  }

  els.preview.innerHTML = cards.join("") || '<div class="empty">当前阶段还没有可预览的中间产物。</div>';
}

function renderHistory() {
  const { items, page, totalPages, total, query, sort } = state.history;
  els.historySearchInput.value = query;
  els.historySortSelect.value = sort;
  els.historySummary.textContent = query ? `搜索“${query}”共 ${total} 部剧本` : `共 ${total} 部剧本`;
  els.historyPageInfo.textContent = `第 ${page} / ${totalPages} 页`;

  if (!items.length) {
    els.historyList.innerHTML = `<div class="empty">${query ? "没有匹配的剧本标题。" : "还没有历史剧本。"}</div>`;
    renderButtonStates();
    return;
  }

  els.historyList.innerHTML = items.map(item => `
    <div class="history-item ${item.id === state.story.activeId ? "active" : ""}" data-story-id="${item.id}">
      <strong>${escapeHtml(item.title || "")}</strong>
      <div class="history-meta">
        ${escapeHtml(item.topic || "")}<br>
        ${escapeHtml(formatDate(item.created_at || ""))} · ${escapeHtml(String(item.num_episodes || 0))} 集
        ${item.notes ? `<br>备注：${escapeHtml(item.notes.slice(0, 48))}` : ""}
      </div>
    </div>
  `).join("");
  renderButtonStates();
}

function renderUndoBanner() {
  if (!state.undo.story) {
    els.undoBanner.innerHTML = "";
    return;
  }
  els.undoBanner.innerHTML = `
    <div class="undo-banner">
      <span>《${escapeHtml(state.undo.story.title || "未命名剧本")}》已移入删除缓冲区，可立即撤销。</span>
      <button class="secondary" data-action="undo-delete">撤销删除</button>
    </div>
  `;
}

function ensureStoryShell(story) {
  const shellKey = story.id ? `story:${story.id}` : `inline:${story.result?.selected_idea?.title || "draft"}`;
  if (state.story.shellKey === shellKey && els.result.querySelector("[data-story-shell='true']")) {
    return;
  }
  state.story.shellKey = shellKey;
  els.result.innerHTML = `
    <div data-story-shell="true">
      <div class="result-card" data-result-card="meta">
        <div id="storyMetaCard"></div>
      </div>
      <div class="result-card" data-result-card="markdown">
        <h3>Markdown 阅读视图</h3>
        <div id="storyToc" class="toc"></div>
        <div id="storyEpisodeTabs" class="episode-tabs"></div>
        <div id="storyMarkdownShell" class="markdown-shell">
          <div id="storyMarkdownBody" class="markdown"></div>
        </div>
      </div>
    </div>
  `;
}

function renderStoryMeta(story) {
  const draft = readDraftMeta();
  const data = story.result || {};
  const selected = data.selected_idea || {};
  const isDirty = (draft.title || "") !== (story.title || "") || (draft.notes || "") !== (story.notes || "");
  document.getElementById("storyMetaCard").innerHTML = `
    <h3 id="storyDisplayTitle">${escapeHtml(draft.title || story.title || selected.title || "未命名剧本")}</h3>
    <div class="result-meta">
      <div><strong>主题</strong><br>${escapeHtml(story.topic || "")}</div>
      <div><strong>创建时间</strong><br>${escapeHtml(formatDate(story.created_at || ""))}</div>
      <div><strong>来源 Agent</strong><br>${escapeHtml(selected.agent_name || "")}</div>
      <div><strong>选择理由</strong><br>${escapeHtml(data.selection_reason || "")}</div>
    </div>
    ${story.id ? `
      <div class="story-form">
        <div>
          <label for="detailTitleInput">剧本标题</label>
          <input id="detailTitleInput" value="${escapeHtml(draft.title || story.title || "")}">
        </div>
        <div>
          <label for="detailNotesInput">备注</label>
          <textarea id="detailNotesInput" placeholder="补充平台定位、剪辑建议、后续改写方向">${escapeHtml(draft.notes || story.notes || "")}</textarea>
        </div>
      </div>
      <div id="storyDraftHint" class="microcopy">${isDirty ? "存在未保存草稿。导出和复制会优先使用当前输入内容。" : "标题和备注按纯文本保存，不支持自定义 HTML 或 Markdown 直通。"}</div>
      <div class="history-actions result-toolbar">
        <button class="secondary" data-action="save-meta" data-story-id="${story.id}">保存标题与备注</button>
        <button class="ghost" data-action="reload-story" data-story-id="${story.id}">重新载入到表单</button>
        <button class="ghost" data-action="copy-current-md">复制当前分集 MD</button>
        <button class="ghost" data-action="export-md">导出 MD</button>
        <button class="ghost" data-action="export-txt">导出 TXT</button>
        <button class="ghost" data-action="export-json">导出 JSON</button>
        <button class="danger" data-action="delete-story" data-story-id="${story.id}">删除这部剧本</button>
      </div>
    ` : `
      <div class="microcopy">当前结果尚未进入历史库，导出内容仍然可以直接使用。</div>
    `}
  `;
}

function renderStoryMarkdownSection(story, { resetScroll = false } = {}) {
  const episodes = Array.isArray(story.result?.episodes) ? story.result.episodes : [];
  if (state.story.activeEpisodeIndex >= episodes.length) {
    state.story.activeEpisodeIndex = 0;
    debugLog("episode-index-reset", { storyId: story.id || "inline" });
  }
  let rendered;
  try {
    rendered = getEpisodePayload(story, state.story.activeEpisodeIndex, readDraftMeta());
  } catch (error) {
    debugLog("markdown-render-failed", { message: error.message });
    document.getElementById("storyToc").innerHTML = "";
    document.getElementById("storyEpisodeTabs").innerHTML = "";
    document.getElementById("storyMarkdownBody").innerHTML = `<pre class="mono">${escapeHtml(buildStoryMarkdown(story, state.story.activeEpisodeIndex, readDraftMeta()))}</pre>`;
    return;
  }

  document.getElementById("storyToc").innerHTML = rendered.toc.map(item => (
    `<a href="#${escapeHtml(item.id)}">${escapeHtml(item.label)}</a>`
  )).join("");
  document.getElementById("storyEpisodeTabs").innerHTML = episodes.map((_, index) => `
    <button
      class="episode-tab ${index === state.story.activeEpisodeIndex ? "active" : ""}"
      data-action="select-episode"
      data-episode-index="${index}"
    >
      第${index + 1}集
    </button>
  `).join("");
  document.getElementById("storyMarkdownBody").innerHTML = rendered.html;
  if (resetScroll) {
    document.getElementById("storyMarkdownShell").scrollTop = 0;
  }
}

function renderStory(story, { resetEpisode = false, resetScroll = false } = {}) {
  if (!story || !story.result) {
    showResultEmpty();
    return;
  }
  if (resetEpisode) {
    state.story.activeEpisodeIndex = 0;
  }
  state.story.current = story;
  state.story.activeId = story.id || null;
  state.story.draft = {
    title: story.title || story.result?.selected_idea?.title || "",
    notes: story.notes || "",
  };
  ensureStoryShell(story);
  renderStoryMeta(story);
  renderStoryMarkdownSection(story, { resetScroll });
  renderHistory();
  renderButtonStates();
}

function patchHistoryItem(updatedStory) {
  state.history.items = state.history.items.map(item => item.id === updatedStory.id ? { ...item, ...updatedStory } : item);
  renderHistory();
}

function downloadFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function currentStoryDraft() {
  if (!state.story.current) {
    return { title: "", notes: "" };
  }
  return readDraftMeta();
}

function exportStory(format) {
  if (!state.story.current) return;
  const draft = currentStoryDraft();
  const baseName = (draft.title || state.story.current.title || "story").replace(/[\\/:*?"<>|]+/g, "_");
  if (format === "md") {
    downloadFile(`${baseName}.md`, buildStoryMarkdown(state.story.current, state.story.activeEpisodeIndex, draft), "text/markdown;charset=utf-8");
    setStatus("已导出 Markdown");
    return;
  }
  if (format === "txt") {
    downloadFile(`${baseName}.txt`, buildStoryMarkdown(state.story.current, state.story.activeEpisodeIndex, draft).replace(/^#+\s?/gm, ""), "text/plain;charset=utf-8");
    setStatus("已导出 TXT");
    return;
  }
  downloadFile(`${baseName}.json`, JSON.stringify({ ...state.story.current, title: draft.title, notes: draft.notes }, null, 2), "application/json;charset=utf-8");
  setStatus("已导出 JSON");
}

async function copyCurrentEpisodeMarkdown() {
  if (!state.story.current) return;
  const content = buildCurrentEpisodeMarkdown(state.story.current, state.story.activeEpisodeIndex, currentStoryDraft());
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(content);
  } else {
    const textarea = document.createElement("textarea");
    textarea.value = content;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  setStatus("当前分集 Markdown 已复制");
}

function reloadStoryToForm(story) {
  els.topicInput.value = story.topic || story.title || "";
  els.constraintsInput.value = story.constraints || "";
  els.numEpisodesInput.value = Number(story.num_episodes || 6);
  els.maxIterationsInput.value = Number(story.max_iterations || 2);
  window.scrollTo({ top: 0, behavior: "smooth" });
  setStatus(`已把《${story.title || "未命名剧本"}》重新载入到生成表单`);
}

async function loadHistory({ page = state.history.page, query = state.history.query, sort = state.history.sort } = {}) {
  const payload = await api.listStories({ page, query, sort, pageSize: 6 });
  state.history.page = payload.page || 1;
  state.history.totalPages = payload.total_pages || 1;
  state.history.total = payload.total || 0;
  state.history.query = typeof payload.query === "string" ? payload.query : query;
  state.history.sort = payload.sort || sort;
  state.history.items = Array.isArray(payload.items) ? payload.items : [];
  renderHistory();
  return payload;
}

async function loadStoryDetail(storyId, options = {}) {
  const payload = await api.getStory(storyId);
  renderStory(payload.story, { resetEpisode: true, resetScroll: options.resetScroll !== false });
  return payload.story;
}

function clearUndoTimer() {
  if (state.undo.timer) {
    clearTimeout(state.undo.timer);
    state.undo.timer = null;
  }
}

function scheduleUndoExpiry() {
  clearUndoTimer();
  state.undo.timer = window.setTimeout(() => {
    state.undo.story = null;
    state.undo.wasCurrent = false;
    renderUndoBanner();
  }, 12000);
}

function clearPolling({ resetJob = true } = {}) {
  if (state.job.timer) {
    clearInterval(state.job.timer);
    state.job.timer = null;
  }
  if (resetJob) {
    state.job.id = null;
  }
  state.job.lastProgressKey = "";
  state.job.lastPreviewKey = "";
}

async function handleExpiredJob() {
  debugLog("job-expired", { jobId: state.job.id, activeStoryId: state.story.activeId });
  clearPolling();
  setStatus("任务状态已过期，正在尝试从历史记录恢复...", { error: true });
  const history = await loadHistory({ page: 1, query: state.history.query, sort: state.history.sort });
  const latest = history.items?.[0];
  if (latest) {
    setStatus("任务状态已过期，但最新历史剧本仍可查看。", {
      error: true,
      action: { type: "open-latest-history", label: "查看最新历史" },
    });
  }
}

function maybeRenderProgress(job) {
  const key = JSON.stringify(job?.stages || []);
  if (key === state.job.lastProgressKey) {
    debugLog("progress-skip");
    return;
  }
  state.job.lastProgressKey = key;
  renderProgress(job);
}

function maybeRenderPreview(job) {
  const key = JSON.stringify(job?.preview || {});
  if (key === state.job.lastPreviewKey) {
    debugLog("preview-skip");
    return;
  }
  state.job.lastPreviewKey = key;
  renderPreview(job);
}

async function handleJobCompleted(data) {
  clearPolling();
  state.job.lockedPayload = null;
  renderJobSnapshot();
  await loadHistory({ page: 1, query: state.history.query, sort: state.history.sort });

  if (data.result?.story_id) {
    state.story.pendingGeneratedStoryId = data.result.story_id;
    if (!state.story.current) {
      await loadStoryDetail(data.result.story_id);
      setStatus("生成完成");
      return;
    }
    setStatus("新剧本已生成，当前阅读不受打断。", {
      action: { type: "open-generated-story", label: "查看新剧本" },
    });
    return;
  }

  const inlineStory = {
    title: data.result?.selected_idea?.title || "",
    notes: "",
    result: data.result || {},
  };
  state.story.pendingGeneratedStory = inlineStory;
  if (!state.story.current) {
    renderStory(inlineStory, { resetEpisode: true, resetScroll: true });
    setStatus("生成完成");
    return;
  }
  setStatus("新结果已生成，当前阅读不受打断。", {
    action: { type: "open-generated-inline", label: "查看新结果" },
  });
}

async function pollJob() {
  if (!state.job.id) {
    return;
  }
  try {
    const data = await api.getJob(state.job.id);
    maybeRenderProgress(data);
    maybeRenderPreview(data);
    if (data.status === "completed") {
      await handleJobCompleted(data);
      return;
    }
    if (data.status === "failed") {
      clearPolling();
      state.job.lockedPayload = null;
      renderJobSnapshot();
      if (!state.story.current) {
        showResultEmpty("生成失败，请检查配置后重试。");
      }
      setStatus(data.error || "生成失败", { error: true });
    }
  } catch (error) {
    if (isHttpStatus(error, 404)) {
      await handleExpiredJob();
      return;
    }
    clearPolling();
    state.job.lockedPayload = null;
    renderJobSnapshot();
    setStatus(error.message, { error: true });
    debugLog("poll-job-failed", { message: error.message, kind: error.kind, status: error.status });
  }
}

function startPolling() {
  clearPolling({ resetJob: false });
  pollJob();
  state.job.timer = window.setInterval(() => {
    pollJob();
  }, 1200);
}

async function onSaveConfig() {
  await runBusy("save-config", async () => {
    setStatus("正在保存配置...");
    await api.saveConfig({
      api_key: els.apiKeyInput.value,
      model_name: els.modelNameInput.value.trim(),
      base_url: els.baseUrlInput.value.trim(),
    });
    setStatus("配置已保存到 .env");
  });
}

async function onTestModel() {
  await runBusy("test-model", async () => {
    setStatus("正在测试模型连接...");
    const data = await api.testModel(collectFormPayload());
    renderDiagnostics(data.result);
    setStatus("模型连接正常");
  });
}

async function onGenerateStory() {
  await runBusy("generate", async () => {
    clearPolling();
    state.job.lockedPayload = collectFormPayload();
    renderJobSnapshot();
    setStatus("任务已提交，正在进入生成队列...");
    renderProgress(null);
    renderPreview(null);
    if (!state.story.current) {
      showResultEmpty("生成中，等待多 Agent 返回结果...");
    }
    const data = await api.generate(state.job.lockedPayload);
    state.job.id = data.job_id;
    setStatus("任务已启动，正在获取实时进展...");
    startPolling();
  });
}

async function onHistorySearch() {
  await runBusy("load-history", async () => {
    state.history.query = els.historySearchInput.value.trim();
    await loadHistory({ page: 1, query: state.history.query, sort: state.history.sort });
  });
}

async function onHistoryClear() {
  await runBusy("load-history", async () => {
    state.history.query = "";
    els.historySearchInput.value = "";
    await loadHistory({ page: 1, query: "", sort: state.history.sort });
  });
}

async function onHistoryRefresh() {
  await runBusy("load-history", async () => {
    await loadHistory();
  });
}

async function onHistoryPage(nextPage) {
  if (nextPage < 1 || nextPage > state.history.totalPages) {
    return;
  }
  await runBusy("load-history", async () => {
    await loadHistory({ page: nextPage });
  });
}

async function onSelectHistoryStory(storyId) {
  await runBusy("load-story", async () => {
    const story = await loadStoryDetail(storyId, { resetScroll: true });
    setStatus(`已载入《${story.title || "未命名剧本"}》`);
  });
}

async function onSaveStoryMeta(storyId) {
  await runBusy("save-meta", async () => {
    const draft = currentStoryDraft();
    if (!draft.title) {
      throw new Error("标题不能为空");
    }
    const data = await api.saveStoryMeta(storyId, draft);
    state.story.draft = { title: data.story.title || "", notes: data.story.notes || "" };
    renderStory(data.story, { resetEpisode: false, resetScroll: false });
    patchHistoryItem(data.story);
    setStatus("标题与备注已保存");
  });
}

async function onDeleteStory(storyId) {
  await runBusy("delete-story", async () => {
    const story = state.story.current;
    if (!storyId || !story) {
      return;
    }
    if (!window.confirm(`确认删除《${story.title || "未命名剧本"}》吗？删除后可在短时间内撤销。`)) {
      return;
    }
    const data = await api.deleteStory(storyId);
    state.undo.story = data.story || story;
    state.undo.wasCurrent = state.story.activeId === storyId;
    renderUndoBanner();
    scheduleUndoExpiry();

    if (state.story.activeId === storyId) {
      showResultEmpty();
    }
    const nextPage = state.history.page > 1 && state.history.items.length === 1 ? state.history.page - 1 : state.history.page;
    await loadHistory({ page: nextPage });
    setStatus("历史剧本已删除，可在 12 秒内撤销");
  });
}

async function onRestoreDeletedStory() {
  if (!state.undo.story?.id) {
    return;
  }
  await runBusy("restore-story", async () => {
    const storyId = state.undo.story.id;
    await api.restoreStory(storyId);
    const shouldRestoreDetail = state.undo.wasCurrent;
    state.undo.story = null;
    state.undo.wasCurrent = false;
    clearUndoTimer();
    renderUndoBanner();
    await loadHistory({ page: state.history.page, query: state.history.query, sort: state.history.sort });
    if (shouldRestoreDetail) {
      await loadStoryDetail(storyId, { resetScroll: false });
    }
    setStatus("已撤销删除");
  });
}

async function openStatusAction() {
  const action = state.ui.statusAction;
  if (!action) return;
  if (action.type === "open-generated-story" && state.story.pendingGeneratedStoryId) {
    const storyId = state.story.pendingGeneratedStoryId;
    state.story.pendingGeneratedStoryId = null;
    await onSelectHistoryStory(storyId);
    return;
  }
  if (action.type === "open-generated-inline" && state.story.pendingGeneratedStory) {
    renderStory(state.story.pendingGeneratedStory, { resetEpisode: true, resetScroll: true });
    state.story.pendingGeneratedStory = null;
    setStatus("已切换到新结果");
    return;
  }
  if (action.type === "open-latest-history" && state.history.items[0]?.id) {
    onSelectHistoryStory(state.history.items[0].id);
  }
}

function bindEvents() {
  els.topicList.addEventListener("click", event => {
    const card = event.target.closest("[data-preset-id]");
    if (card) {
      applyPreset(card.dataset.presetId);
    }
  });

  els.result.addEventListener("input", event => {
    if (event.target.id === "detailTitleInput" || event.target.id === "detailNotesInput") {
      readDraftMeta();
      const titleEl = document.getElementById("storyDisplayTitle");
      const hintEl = document.getElementById("storyDraftHint");
      if (titleEl) {
        titleEl.textContent = state.story.draft.title || state.story.current?.title || state.story.current?.result?.selected_idea?.title || "未命名剧本";
      }
      if (hintEl) {
        const isDirty = (state.story.draft.title || "") !== (state.story.current?.title || "") ||
          (state.story.draft.notes || "") !== (state.story.current?.notes || "");
        hintEl.textContent = isDirty
          ? "存在未保存草稿。导出和复制会优先使用当前输入内容。"
          : "标题和备注按纯文本保存，不支持自定义 HTML 或 Markdown 直通。";
      }
      renderButtonStates();
    }
  });

  els.result.addEventListener("click", event => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "select-episode") {
      state.story.activeEpisodeIndex = Number(button.dataset.episodeIndex || 0);
      renderStoryMarkdownSection(state.story.current, { resetScroll: true });
      renderButtonStates();
      return;
    }
    if (action === "reload-story" && state.story.current) {
      reloadStoryToForm(state.story.current);
      return;
    }
    if (action === "save-meta" && state.story.current?.id) {
      onSaveStoryMeta(state.story.current.id).catch(handleUiError);
      return;
    }
    if (action === "copy-current-md") {
      runBusy("copy-md", copyCurrentEpisodeMarkdown).catch(handleUiError);
      return;
    }
    if (action === "export-md") {
      exportStory("md");
      return;
    }
    if (action === "export-txt") {
      exportStory("txt");
      return;
    }
    if (action === "export-json") {
      exportStory("json");
      return;
    }
    if (action === "delete-story" && state.story.current?.id) {
      onDeleteStory(state.story.current.id).catch(handleUiError);
      return;
    }
  });

  els.historyList.addEventListener("click", event => {
    const item = event.target.closest("[data-story-id]");
    if (!item) return;
    onSelectHistoryStory(Number(item.dataset.storyId || 0)).catch(handleUiError);
  });

  els.undoBanner.addEventListener("click", event => {
    const button = event.target.closest("[data-action='undo-delete']");
    if (button) {
      onRestoreDeletedStory().catch(handleUiError);
    }
  });

  els.statusActions.addEventListener("click", event => {
    const button = event.target.closest("[data-status-action]");
    if (button) {
      openStatusAction().catch(handleUiError);
    }
  });

  els.saveConfigBtn.addEventListener("click", () => onSaveConfig().catch(handleUiError));
  els.testModelBtn.addEventListener("click", () => onTestModel().catch(handleUiError));
  els.generateBtn.addEventListener("click", () => onGenerateStory().catch(handleUiError));
  els.refreshHistoryBtn.addEventListener("click", () => onHistoryRefresh().catch(handleUiError));
  els.searchHistoryBtn.addEventListener("click", () => onHistorySearch().catch(handleUiError));
  els.clearHistorySearchBtn.addEventListener("click", () => onHistoryClear().catch(handleUiError));
  els.prevHistoryBtn.addEventListener("click", () => onHistoryPage(state.history.page - 1).catch(handleUiError));
  els.nextHistoryBtn.addEventListener("click", () => onHistoryPage(state.history.page + 1).catch(handleUiError));
  els.historySortSelect.addEventListener("change", () => {
    state.history.sort = els.historySortSelect.value || "created_desc";
    onHistoryPage(1).catch(handleUiError);
  });
  els.historySearchInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      onHistorySearch().catch(handleUiError);
    }
  });
}

function handleUiError(error) {
  debugLog("ui-error", { message: error.message, kind: error.kind, status: error.status, action: error.action });
  setStatus(error.message || "操作失败", { error: true });
}

function applyRuntimeConfig() {
  els.apiKeyInput.value = "";
  els.modelNameInput.value = runtimeConfig.model_name || "gpt-4o-mini";
  els.baseUrlInput.value = runtimeConfig.base_url || "";
  if (runtimeConfig.has_api_key === "true" && runtimeConfig.api_key_hint) {
    els.apiKeyHint.textContent = `已保存密钥：${runtimeConfig.api_key_hint}。留空时会沿用该配置。`;
  }
}

async function init() {
  applyRuntimeConfig();
  renderTopicPresets();
  if (topicPresets[0]) {
    applyPreset(topicPresets[0].id);
  }
  renderDiagnostics(null);
  renderProgress(null);
  renderPreview(null);
  showResultEmpty();
  renderUndoBanner();
  renderStatus();
  renderDebugStatus();
  bindEvents();
  try {
    await runBusy("load-history", async () => {
      await loadHistory({ page: 1 });
    });
  } catch (error) {
    els.historySummary.textContent = "历史记录加载失败";
    handleUiError(error);
  }
}

init();
