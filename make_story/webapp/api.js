export class RequestError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "RequestError";
    this.kind = options.kind || "unknown";
    this.status = options.status || 0;
    this.action = options.action || "request";
    this.payload = options.payload;
    this.cause = options.cause;
  }
}

function buildHeaders(url, baseHeaders, sessionToken) {
  const headers = new Headers(baseHeaders || {});
  if (url.startsWith("/api/stories")) {
    headers.set("X-Storyroom-Session", sessionToken);
  }
  return headers;
}

async function parseJsonOrThrow(resp, action) {
  const text = await resp.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new RequestError("服务端返回了不可解析的 JSON", {
      kind: "parse",
      status: resp.status,
      action,
      cause: error,
    });
  }
}

async function requestJson(url, options = {}, sessionToken) {
  const action = options.action || url;
  const fetchOptions = {
    method: options.method || "GET",
    headers: buildHeaders(url, options.headers, sessionToken),
  };
  if (options.body !== undefined) {
    fetchOptions.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
    if (!fetchOptions.headers.has("Content-Type")) {
      fetchOptions.headers.set("Content-Type", "application/json");
    }
  }

  let resp;
  try {
    resp = await fetch(url, fetchOptions);
  } catch (error) {
    throw new RequestError("网络请求失败，请检查本地服务是否仍在运行", {
      kind: "network",
      action,
      cause: error,
    });
  }

  const payload = await parseJsonOrThrow(resp, action);
  if (!resp.ok) {
    throw new RequestError(payload.error || "请求失败", {
      kind: "http",
      status: resp.status,
      action,
      payload,
    });
  }
  return payload;
}

export function isHttpStatus(error, status) {
  return error instanceof RequestError && error.kind === "http" && error.status === status;
}

export function createApi(sessionToken) {
  return {
    getConfig() {
      return requestJson("/api/config", { action: "get-config" }, sessionToken);
    },
    listStories(params) {
      const search = new URLSearchParams({
        page: String(params.page || 1),
        page_size: String(params.pageSize || 6),
        sort: params.sort || "created_desc",
      });
      if (params.query) {
        search.set("q", params.query);
      }
      return requestJson(`/api/stories?${search.toString()}`, { action: "list-stories" }, sessionToken);
    },
    getStory(storyId) {
      return requestJson(`/api/stories/${storyId}`, { action: "get-story" }, sessionToken);
    },
    saveStoryMeta(storyId, payload) {
      return requestJson(`/api/stories/${storyId}/meta`, {
        method: "POST",
        body: payload,
        action: "save-story-meta",
      }, sessionToken);
    },
    deleteStory(storyId) {
      return requestJson(`/api/stories/${storyId}`, {
        method: "DELETE",
        action: "delete-story",
      }, sessionToken);
    },
    restoreStory(storyId) {
      return requestJson(`/api/stories/${storyId}/restore`, {
        method: "POST",
        body: {},
        action: "restore-story",
      }, sessionToken);
    },
    saveConfig(payload) {
      return requestJson("/api/save-config", {
        method: "POST",
        body: payload,
        action: "save-config",
      }, sessionToken);
    },
    testModel(payload) {
      return requestJson("/api/test-model", {
        method: "POST",
        body: payload,
        action: "test-model",
      }, sessionToken);
    },
    generate(payload) {
      return requestJson("/api/generate", {
        method: "POST",
        body: payload,
        action: "generate-story",
      }, sessionToken);
    },
    getJob(jobId) {
      return requestJson(`/api/jobs/${jobId}`, { action: "get-job" }, sessionToken);
    },
  };
}
