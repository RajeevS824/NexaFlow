// ─────────────────────────────────────────────────────────────
// config/businessMapApi.js
// ─────────────────────────────────────────────────────────────
// Single source of truth for Business Map backend calls.
// Ported from the standalone project's src/api.js, retargeted the way
// Document Parser's config/api.js is:
//   - Absolute base URL (VITE_BUSINESS_MAP_API_BASE_URL, default
//     http://127.0.0.1:8020) — NOT Vite's "/api" proxy, which already
//     routes to the NexaFlow backend (:8001).
//   - Every request carries the NexaFlow JWT as a Bearer header via
//     authFetch() (orchestrator's require_user dependency demands it).
//   - Orchestrator routes have no "/api" prefix (/run, /status/{id}, ...).
// ─────────────────────────────────────────────────────────────

function resolveBaseUrl(raw, fallback = "/bm") {
  if (!raw || /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(raw)) {
    return fallback;
  }
  return raw;
}

export const API_BASE_URL = resolveBaseUrl(
  import.meta.env.VITE_BUSINESS_MAP_API_BASE_URL,
  "/bm"
);

const AUTH_STORAGE_KEY = "nexaflow_auth";

/** Read the current NexaFlow JWT (issued at login) from sessionStorage. */
function getAuthToken() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.token || null;
  } catch {
    return null;
  }
}

/**
 * Drop-in replacement for `fetch()` that also attaches the logged-in user's
 * Bearer token (required by the orchestrator's require_user dependency).
 * Behaves exactly like fetch() otherwise.
 */
export async function authFetch(input, init = {}) {
  const token = getAuthToken();
  const headers = new Headers(init.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

/**
 * Build an authenticated URL for resources that can't send headers
 * (e.g. report downloads via <a href>). Not currently required by the
 * orchestrator's /files static mount, but kept for parity/forward-compat.
 */
export function withAuthToken(url) {
  const token = getAuthToken();
  if (!token) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(token)}`;
}

const LLM_CLIENT_ID_KEY = "suppi_llm_client_id";
const LLM_MAX_INT = 2147483647;

/**
 * Stable per-browser numeric id used to scope LLM settings/usage. Returns
 * null if localStorage is unavailable (callers fall back to the shared
 * default settings row).
 */
function getLlmClientId() {
  try {
    const existing = localStorage.getItem(LLM_CLIENT_ID_KEY);
    if (existing) {
      const parsed = Number(existing);
      if (Number.isInteger(parsed) && parsed > 0) return parsed;
    }
    const arr = new Uint32Array(1);
    (window.crypto || window.msCrypto).getRandomValues(arr);
    const id = (arr[0] % LLM_MAX_INT) + 1;
    localStorage.setItem(LLM_CLIENT_ID_KEY, String(id));
    return id;
  } catch {
    return null;
  }
}

/** Upload a video (and optionally separate audio) and let the backend decide
 * the audio source (the ONLY place audio detection happens — ffprobe, after
 * upload). Resolves with:
 *   { status: "QUEUED", job_id, job_name }              → processing started
 *   { status: "NEEDS_AUDIO_CONFIRMATION", job_id, ... } → show No Audio popup
 */
export function uploadAndStart(file, onProgress, audioFile, username, email) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("video", file);
    if (audioFile) formData.append("audio", audioFile);
    if (username) formData.append("username", username);
    if (email) formData.append("email", email);

    const llmUserId = getLlmClientId();
    if (llmUserId) formData.append("llmUserId", String(llmUserId));

    const token = getAuthToken();
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 40));
      }
    });

    xhr.addEventListener("load", () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if ((xhr.status === 202 || xhr.status === 200) && data.job_id) {
          resolve(data);
        } else {
          reject(data);
        }
      } catch {
        reject({ error: "Invalid response from server" });
      }
    });

    xhr.addEventListener("error", () =>
      reject({ error: "Network error – is the backend running?" })
    );
    xhr.addEventListener("timeout", () => reject({ error: "Upload timed out" }));

    xhr.timeout = 120_000;
    xhr.open("POST", `${API_BASE_URL}/run`);
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.send(formData);
  });
}

/** Resolve a job paused in NEEDS_AUDIO_CONFIRMATION after the user responds. */
export async function confirmAudio(jobId, proceed) {
  const formData = new FormData();
  formData.append("proceed", proceed ? "true" : "false");

  const res = await authFetch(`${API_BASE_URL}/confirm-audio/${jobId}`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Poll /status/{job_id} every 3s until a terminal state, or until it pauses
 * awaiting user confirmation (returns immediately in that case).
 */
export async function pollJobStatus(jobId, onProgress) {
  while (true) {
    await new Promise((r) => setTimeout(r, 3000));

    let res, data;
    try {
      res = await authFetch(`${API_BASE_URL}/status/${jobId}`);
      data = await res.json();
    } catch {
      throw { error: "Network error while polling job status" };
    }

    if (!res.ok) throw data;

    if (data.status === "QUEUED" || data.status === "RUNNING") {
      if (onProgress) {
        const pct = typeof data.progress === "number" ? data.progress : 50;
        onProgress(Math.min(pct, 95), data.phase);
      }
      continue;
    }

    // USER_CONFIRMATION_REQUIRED / SUCCESS / PARTIAL / FAILED / CANCELLED
    return data;
  }
}

/** Convenience: upload, then poll to completion (or pause for confirmation). */
export async function runPipeline(file, onProgress, audioFile, username, email) {
  const started = await uploadAndStart(file, onProgress, audioFile, username, email);

  if (started.status === "NEEDS_AUDIO_CONFIRMATION") {
    return started;
  }

  return pollJobStatus(started.job_id, onProgress);
}

/** Cancel a queued/running/paused job. */
export async function cancelJob(jobId) {
  const res = await authFetch(`${API_BASE_URL}/cancel/${jobId}`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Cancel every active (queued / running / awaiting-confirmation) job that
 * belongs to the logged-in user. Used by Logout. The backend identifies the
 * user from the Bearer token, so only this user's jobs are ever affected.
 * Resolves with { cancelled: [], already_finished: [], failed: [] }.
 */
export async function cancelActiveJobs() {
  const res = await authFetch(`${API_BASE_URL}/cancel-active`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Fire-and-forget cancellation for a beforeunload/pagehide handler. Plain
 * sendBeacon() can't attach the Bearer header, so we use a keepalive fetch
 * (which can) — the orchestrator /cancel requires the token.
 */
export function cancelJobBeacon(jobId) {
  try {
    authFetch(`${API_BASE_URL}/cancel/${jobId}`, {
      method: "POST",
      keepalive: true,
      body: new Blob([], { type: "text/plain" }),
    });
  } catch {
    // best-effort only — nothing more we can do once the page is unloading
  }
}

/** Fetch aggregated statistics: total_uploaded, processing, completed, failed, etc. */
export async function getStats() {
  const res = await authFetch(`${API_BASE_URL}/stats`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Fetch all recent jobs for the logged-in user. */
export async function getJobs() {
  const res = await authFetch(`${API_BASE_URL}/jobs`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Check orchestrator health. */
export async function checkHealth() {
  const res = await authFetch(`${API_BASE_URL}/health`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Build a download URL for a backend-returned server file path. */
export function getDownloadUrl(serverPath) {
  if (!serverPath) return null;
  const relativePath = serverPath.replace(/^output[/\\]/, "");
  return withAuthToken(`${API_BASE_URL}/files/${relativePath}`);
}

/** Fetch current log config for the logged-in user. */
export async function getLogConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/log-config`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Save log config for the logged-in user.
 * POST /settings/log-config  body: { level, folder_path, enabled, max_size_mb }
 * The page passes { level, folderPath, enabled, maxSizeMb }; they are mapped to
 * the backend's snake_case names here. max_size_mb is sent as an integer.
 */
export async function saveLogConfig(config) {
  const body = {
    level: config.level,
    folder_path: config.folderPath,
    enabled: config.enabled,
    max_size_mb: Math.trunc(Number(config.maxSizeMb)),
  };
  const res = await authFetch(`${API_BASE_URL}/settings/log-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Reset log config to defaults. POST /settings/log-config/reset */
export async function resetLogConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/log-config/reset`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Fetch current upload config for the logged-in user. */
export async function getUploadConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/upload-config`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Save upload config for the logged-in user.
 * POST /settings/upload-config
 * body: { max_upload_size_mb: <int>, max_audio_upload_size_mb: <int> }
 * Takes the two values the Settings page passes (video MB, audio MB).
 */
export async function saveUploadConfig(maxUploadMb, maxAudioUploadMb) {
  const body = {
    max_upload_size_mb: Math.trunc(Number(maxUploadMb)),
    max_audio_upload_size_mb: Math.trunc(Number(maxAudioUploadMb)),
  };
  const res = await authFetch(`${API_BASE_URL}/settings/upload-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Reset upload config to defaults. POST /settings/upload-config/reset */
export async function resetUploadConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/upload-config/reset`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/** Fetch current LLM config for the logged-in user. */
export async function getLlmConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/llm-config`);
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Save LLM config for the logged-in user.
 * POST /settings/llm-config  body: { mode, primary_api_key? }
 * `primary_api_key` is only included when the caller passes `primaryApiKey`
 * (a key the user typed). When it is not passed, the field is omitted so the
 * backend keeps the stored key. (The page's "Delete key" action passes an
 * explicit "" which the backend treats as "clear the stored key".)
 */
export async function saveLlmConfig(config) {
  const body = { mode: config.mode };
  if (config.provider !== undefined) body.provider = config.provider;
  if (config.model !== undefined) body.model = config.model;
  if (config.primaryApiKey !== undefined) {
    body.primary_api_key = config.primaryApiKey;
  }
  const res = await authFetch(`${API_BASE_URL}/settings/llm-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}

/**
 * Load the available models for a provider.
 * POST /settings/llm-config/models  body: { provider, api_key? }
 * If apiKey is blank the backend uses the user's already-saved key.
 */
export async function refreshLlmModels({ provider, apiKey }) {
  const body = { provider };
  if (apiKey && apiKey.trim() !== "") body.api_key = apiKey.trim();
  const res = await authFetch(`${API_BASE_URL}/settings/llm-config/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data.models || [];
}

/** Reset LLM config to defaults. POST /settings/llm-config/reset */
export async function resetLlmConfig() {
  const res = await authFetch(`${API_BASE_URL}/settings/llm-config/reset`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
}
