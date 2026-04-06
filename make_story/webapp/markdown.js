export function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function slugifyHeading(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^\u4e00-\u9fa5a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "section";
}

function formatInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

export function renderMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  const headingIdCounts = new Map();
  let paragraph = [];
  let listItems = [];
  let quoteLines = [];
  let codeLines = [];
  let inCode = false;

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push(`<p>${formatInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.map(item => `<li>${formatInlineMarkdown(item)}</li>`).join("")}</ul>`);
    listItems = [];
  }

  function flushCode() {
    if (!codeLines.length) return;
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  }

  function flushQuote() {
    if (!quoteLines.length) return;
    html.push(`<blockquote>${quoteLines.map(line => formatInlineMarkdown(line)).join("<br>")}</blockquote>`);
    quoteLines = [];
  }

  function getHeadingId(text) {
    const baseId = slugifyHeading(text);
    const count = headingIdCounts.get(baseId) || 0;
    headingIdCounts.set(baseId, count + 1);
    return count === 0 ? baseId : `${baseId}-${count + 1}`;
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.startsWith("```")) {
      flushParagraph();
      flushList();
      flushQuote();
      if (inCode) {
        flushCode();
      }
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      codeLines.push(rawLine);
      continue;
    }
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }
    if (trimmed.startsWith("### ")) {
      flushParagraph();
      flushList();
      flushQuote();
      html.push(`<h3 id="${escapeHtml(getHeadingId(trimmed.slice(4)))}">${formatInlineMarkdown(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushParagraph();
      flushList();
      flushQuote();
      html.push(`<h2 id="${escapeHtml(getHeadingId(trimmed.slice(3)))}">${formatInlineMarkdown(trimmed.slice(3))}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushParagraph();
      flushList();
      flushQuote();
      html.push(`<h1 id="${escapeHtml(getHeadingId(trimmed.slice(2)))}">${formatInlineMarkdown(trimmed.slice(2))}</h1>`);
      continue;
    }
    if (trimmed.startsWith("- ")) {
      flushParagraph();
      flushQuote();
      listItems.push(trimmed.slice(2));
      continue;
    }
    if (trimmed.startsWith("> ")) {
      flushParagraph();
      flushList();
      quoteLines.push(trimmed.slice(2));
      continue;
    }
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushQuote();
  flushCode();
  return html.join("");
}

export function buildMarkdownToc(markdown) {
  const seen = new Map();
  return String(markdown || "")
    .split("\n")
    .map(line => line.trim())
    .filter(line => /^#{1,3}\s+/.test(line))
    .map(line => {
      const label = line.replace(/^#{1,3}\s+/, "");
      const baseId = slugifyHeading(label);
      const count = seen.get(baseId) || 0;
      seen.set(baseId, count + 1);
      return {
        label,
        id: count === 0 ? baseId : `${baseId}-${count + 1}`,
      };
    });
}

function getDisplayTitle(story, draft = {}) {
  return draft.title || story.title || story.result?.selected_idea?.title || "未命名剧本";
}

function getDisplayNotes(story, draft = {}) {
  return draft.notes ?? story.notes ?? "";
}

export function buildStoryStaticMarkdown(story, draft = {}) {
  const data = story.result || {};
  const bible = data.story_bible || {};
  const plans = Array.isArray(data.episode_plans) ? data.episode_plans : [];
  const title = getDisplayTitle(story, draft);
  const notes = getDisplayNotes(story, draft);
  const planLines = plans.map(item => (
    `- 第${item.episode_number || "?"}集《${item.title || "未命名"}》：${item.goal || ""}；钩子：${item.hook || ""}`
  ));
  const characterLines = String(data.characters || "")
    .split("\n")
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.startsWith("- ") ? line : `- ${line}`);
  const bibleLines = [
    `- 世界观：${bible.world || ""}`,
    `- 核心冲突：${bible.core_conflict || ""}`,
    `- 主题：${bible.theme || ""}`,
    `- 调性：${bible.tone || ""}`,
    ...(Array.isArray(bible.main_characters) ? bible.main_characters.map(item => `- ${item}`) : []),
  ];

  return [
    `# ${title}`,
    "",
    `> 主题：${story.topic || ""}`,
    `> 创建时间：${formatDate(story.created_at || "")}`,
    `> 选择理由：${data.selection_reason || ""}`,
    ...(notes ? ["", "## 备注", "", notes] : []),
    "",
    "## 故事 Bible",
    "",
    ...bibleLines,
    "",
    "## 大纲",
    "",
    data.outline || "暂无大纲",
    "",
    "## 人物小传",
    "",
    ...(characterLines.length ? characterLines : ["- 暂无人物信息"]),
    "",
    "## 分集规划",
    "",
    ...(planLines.length ? planLines : ["- 暂无分集规划"]),
  ].join("\n");
}

export function buildCurrentEpisodeMarkdown(story, episodeIndex = 0, draft = {}) {
  const data = story.result || {};
  const plans = Array.isArray(data.episode_plans) ? data.episode_plans : [];
  const episodes = Array.isArray(data.episodes) ? data.episodes : [];
  const title = getDisplayTitle(story, draft);
  const activePlan = plans[episodeIndex] || {};
  const activeEpisode = episodes[episodeIndex] || "暂无剧本文本";
  return [
    `# ${title}`,
    "",
    `## 第${episodeIndex + 1}集${activePlan.title ? `《${activePlan.title}》` : ""}`,
    "",
    activePlan.goal ? `- 本集目标：${activePlan.goal}` : "",
    activePlan.hook ? `- 本集钩子：${activePlan.hook}` : "",
    "",
    "```text",
    activeEpisode,
    "```",
  ].filter(Boolean).join("\n");
}

export function buildStoryMarkdown(story, episodeIndex = 0, draft = {}) {
  const staticMarkdown = buildStoryStaticMarkdown(story, draft);
  const currentEpisodeMarkdown = buildCurrentEpisodeMarkdown(story, episodeIndex, draft)
    .replace(/^# .+\n\n/, "");
  return `${staticMarkdown}\n\n${currentEpisodeMarkdown}`;
}
