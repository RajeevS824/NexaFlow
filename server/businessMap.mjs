import express from "express";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import multer from "multer";
import { requireUser } from "./auth.mjs";
import { getBmPool } from "./db.mjs";
import { store, generateUuid } from "./store.mjs";

export const BM_OUTPUT_ROOT = path.join(os.tmpdir(), "nexaflow-bm-output");
fs.mkdirSync(BM_OUTPUT_ROOT, { recursive: true });

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 500 * 1024 * 1024 },
});

const LLM_PROVIDER_MODELS = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"],
  anthropic: ["claude-sonnet-4-5", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
  openrouter: ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "google/gemini-2.5-flash"],
  groq: ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
  mistral: ["mistral-large-latest", "mistral-small-latest"],
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  xai: ["grok-2-latest", "grok-2-vision-1212"],
};

function maskApiKey(key) {
  if (!key) return "";
  if (key.length <= 8) return "****";
  return `${key.slice(0, 4)}...${key.slice(-4)}`;
}

function writeSampleOutputs(jobId, jobName, videoName) {
  const dir = path.join(BM_OUTPUT_ROOT, jobId);
  fs.mkdirSync(dir, { recursive: true });

  const stepsContent = `# Business Process SOP: ${jobName}

**Source Video:** ${videoName}
**Generated:** ${new Date().toISOString()}

## Workflow Steps
1. **Open Application & Authenticate** — Navigate to workspace portal and verify user session.
2. **Select Target Module** — Choose the operational queue from the primary navigation sidebar.
3. **Upload & Validate Input** — Attach source records and verify required fields are populated.
4. **Review & Confirm Output** — Inspect extracted summaries and commit finalized workflow data.
5. **Archive & Audit Log** — Export completed SOP artifacts and record execution timestamp.
`;

  const validationContent = `# Manual Validation Checklist: ${jobName}

- [x] Video stream inspected and frames segmented
- [x] Key UI transitions and user actions identified
- [x] Decision branches and exception paths documented
- [x] Final SOP artifact verified ready for export
`;

  fs.writeFileSync(path.join(dir, "workflow_steps_clean.md"), stepsContent, "utf8");
  fs.writeFileSync(path.join(dir, "workflow_validation.md"), validationContent, "utf8");
}

for (const job of store.bmJobs.values()) {
  writeSampleOutputs(job.job_id, job.job_name, job.video_filename);
}

function advanceJobAsync(jobId) {
  const phases = [
    { delay: 800, progress: 55, phase: "Analyzing video frames & audio track" },
    { delay: 1600, progress: 80, phase: "Synthesizing process steps & SOP" },
    { delay: 2400, progress: 100, phase: "Completed" },
  ];

  phases.forEach((step, idx) => {
    setTimeout(async () => {
      const job = store.bmJobs.get(jobId);
      if (!job || job.status === "CANCELLED" || job.status === "FAILED") return;

      job.progress = step.progress;
      job.phase = step.phase;
      const isFinal = idx === phases.length - 1;
      if (isFinal) {
        writeSampleOutputs(job.job_id, job.job_name, job.video_filename);
        job.status = "SUCCESS";
        job.latency_sec = 2.4;
        job.processed_at = new Date().toISOString();
        job.outputs = {
          workflow_steps_clean: `output/${job.job_id}/workflow_steps_clean.md`,
          workflow_validation: `output/${job.job_id}/workflow_validation.md`,
        };
      }

      const pool = getBmPool();
      if (pool) {
        try {
          if (isFinal) {
            await pool.query(
              `UPDATE public.jobs SET status = 'SUCCESS', progress = 100, phase = $1,
               latency_sec = 2.4, updated_at = NOW(), completed_at = NOW() WHERE id = $2`,
              [step.phase, jobId]
            );
          } else {
            await pool.query(
              `UPDATE public.jobs SET progress = $1, phase = $2, updated_at = NOW() WHERE id = $3`,
              [step.progress, step.phase, jobId]
            );
          }
        } catch {
          // best-effort DB sync
        }
      }
    }, step.delay);
  });
}

export const businessMapRouter = express.Router();

businessMapRouter.get("/health", (_req, res) => {
  res.json({
    status: "healthy",
    orchestrator: "healthy",
    audio_service: "healthy",
    video_service: "healthy",
    db_connected: Boolean(getBmPool()),
    timestamp: new Date().toISOString(),
  });
});

async function userCanAccessJob(jobId, user) {
  if (!jobId || typeof jobId !== "string") return false;
  if (user?.role === "admin") return true;
  const memJob = store.bmJobs.get(jobId);
  if (memJob) {
    return memJob.user_id == null || memJob.user_id === user.id;
  }
  const pool = getBmPool();
  if (pool) {
    try {
      const r = await pool.query(`SELECT user_id FROM public.jobs WHERE id = $1 LIMIT 1`, [jobId]);
      if (r.rows[0]) {
        return r.rows[0].user_id == null || Number(r.rows[0].user_id) === user.id;
      }
    } catch {
      return false;
    }
  }
  return false;
}

businessMapRouter.use("/files/:jobId", requireUser, async (req, res, next) => {
  const allowed = await userCanAccessJob(req.params.jobId, req.user);
  if (!allowed) return res.status(403).json({ detail: "Access denied." });
  return next();
});
businessMapRouter.use("/files", requireUser, express.static(BM_OUTPUT_ROOT));
businessMapRouter.use(requireUser);

businessMapRouter.post(
  "/run",
  upload.fields([
    { name: "video", maxCount: 1 },
    { name: "audio", maxCount: 1 },
  ]),
  async (req, res) => {
    const videoFile = req.files?.video?.[0];
    if (!videoFile) {
      return res.status(400).json({ error: "Video file is required." });
    }

    const jobId = generateUuid();
    const baseName = path.basename(videoFile.originalname, path.extname(videoFile.originalname));
    const jobName = baseName.replace(/[^a-zA-Z0-9_-]+/g, "_") || `Job_${jobId.slice(0, 8)}`;
    const username = req.body?.username || req.user.full_name || "anonymous";
    const email = req.body?.email || req.user.email || "";

    const job = {
      job_id: jobId,
      job_name: jobName,
      user_id: req.user.id,
      username,
      email,
      video_filename: videoFile.originalname,
      size_bytes: videoFile.size || 0,
      status: "RUNNING",
      progress: 40,
      phase: "Uploading & inspecting media",
      latency_sec: null,
      error: null,
      created_at: new Date().toISOString(),
      processed_at: null,
      outputs: null,
    };

    store.bmJobs.set(jobId, job);

    const pool = getBmPool();
    if (pool) {
      try {
        await pool.query(
          `INSERT INTO public.users (id, username, email, created_at, last_seen_at)
           VALUES ($1, $2, $3, NOW(), NOW())
           ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, email = EXCLUDED.email, last_seen_at = NOW()`,
          [req.user.id, username, email]
        );
        await pool.query(
          `INSERT INTO public.jobs
             (id, job_name, user_id, status, phase, progress, video_filename, video_size_bytes, recipient_email, created_at, updated_at)
           VALUES ($1, $2, $3, 'RUNNING', $4, 40, $5, $6, $7, NOW(), NOW())`,
          [jobId, jobName, req.user.id, job.phase, videoFile.originalname, videoFile.size || 0, email]
        );
      } catch (err) {
        console.error("[bm] insert job DB error:", err.message);
      }
    }

    advanceJobAsync(jobId);

    res.status(202).json({
      status: "QUEUED",
      job_id: jobId,
      job_name: jobName,
    });
  }
);

businessMapRouter.post("/confirm-audio/:jobId", upload.none(), async (req, res) => {
  const job = store.bmJobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ detail: "Unknown job_id" });
  if (req.user.role !== "admin" && job.user_id != null && job.user_id !== req.user.id) {
    return res.status(403).json({ detail: "Access denied." });
  }

  const proceed = String(req.body?.proceed || "true").toLowerCase() === "true";
  if (!proceed) {
    job.status = "CANCELLED";
    job.phase = "Cancelled";
    const pool = getBmPool();
    if (pool) {
      await pool.query(`UPDATE public.jobs SET status = 'CANCELLED', phase = 'Cancelled', updated_at = NOW() WHERE id = $1`, [job.job_id]).catch(() => {});
    }
    return res.json({ status: "CANCELLED", message: "Processing was cancelled by the user." });
  }

  job.status = "RUNNING";
  job.progress = 45;
  job.phase = "Processing video frames";
  advanceJobAsync(job.job_id);
  res.json({ status: "RUNNING", job_id: job.job_id });
});

businessMapRouter.get("/status/:jobId", async (req, res) => {
  const job = store.bmJobs.get(req.params.jobId);
  if (job) {
    if (req.user.role !== "admin" && job.user_id != null && job.user_id !== req.user.id) {
      return res.status(403).json({ detail: "Access denied." });
    }
    return res.json(job);
  }

  const pool = getBmPool();
  if (pool) {
    try {
      const r = await pool.query(`SELECT * FROM public.jobs WHERE id = $1 LIMIT 1`, [req.params.jobId]);
      const row = r.rows[0];
      if (row) {
        if (req.user.role !== "admin" && row.user_id != null && Number(row.user_id) !== req.user.id) {
          return res.status(403).json({ detail: "Access denied." });
        }
        return res.json({
          job_id: row.id,
          job_name: row.job_name,
          status: row.status,
          progress: row.progress,
          phase: row.phase,
          latency_sec: row.latency_sec,
          error: row.error,
          created_at: row.created_at,
          processed_at: row.completed_at,
          outputs: row.status === "SUCCESS" ? {
            workflow_steps_clean: `output/${row.id}/workflow_steps_clean.md`,
            workflow_validation: `output/${row.id}/workflow_validation.md`,
          } : null,
        });
      }
    } catch {
      // fall through
    }
  }
  return res.status(404).json({ detail: "Unknown job_id" });
});

businessMapRouter.post("/cancel/:jobId", async (req, res) => {
  const allowed = await userCanAccessJob(req.params.jobId, req.user);
  if (!allowed) return res.status(403).json({ detail: "Access denied." });

  const job = store.bmJobs.get(req.params.jobId);
  if (job) {
    if (["SUCCESS", "FAILED", "CANCELLED"].includes(job.status)) {
      return res.json({ status: job.status, message: "Job already finished." });
    }
    job.status = "CANCELLED";
    job.phase = "Cancelled";
  }
  const pool = getBmPool();
  if (pool) {
    await pool.query(
      `UPDATE public.jobs SET status = 'CANCELLED', phase = 'Cancelled', updated_at = NOW()
       WHERE id = $1 AND status NOT IN ('SUCCESS', 'FAILED', 'CANCELLED')`,
      [req.params.jobId]
    ).catch(() => {});
  }
  res.json({ status: "CANCELLED", message: "Processing was cancelled by the user." });
});

businessMapRouter.post("/cancel-active", async (req, res) => {
  const cancelled = [];
  for (const job of store.bmJobs.values()) {
    if (job.user_id === req.user.id && ["QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION"].includes(job.status)) {
      job.status = "CANCELLED";
      job.phase = "Cancelled";
      cancelled.push(job.job_id);
    }
  }
  const pool = getBmPool();
  if (pool) {
    await pool.query(
      `UPDATE public.jobs SET status = 'CANCELLED', phase = 'Cancelled', updated_at = NOW()
       WHERE user_id = $1 AND status IN ('QUEUED', 'RUNNING', 'NEEDS_AUDIO_CONFIRMATION')`,
      [req.user.id]
    ).catch(() => {});
  }
  res.json({ cancelled, already_finished: [], failed: [] });
});

businessMapRouter.get("/jobs", async (req, res) => {
  const page = Math.max(1, Math.trunc(Number(req.query.page) || 1));
  const pageSize = Math.min(100, Math.max(1, Math.trunc(Number(req.query.page_size) || 8)));
  const search = String(req.query.search || "").trim().toLowerCase();
  const pool = getBmPool();

  if (pool) {
    try {
      const params = [];
      const where = [];
      if (req.user.role !== "admin") {
        params.push(req.user.id);
        where.push(`(j.user_id = $${params.length} OR j.user_id IS NULL)`);
      }
      if (search) {
        params.push(`%${search}%`);
        const idx = params.length;
        where.push(`(LOWER(COALESCE(j.video_filename, j.job_name)) LIKE $${idx} OR LOWER(COALESCE(u.username, '')) LIKE $${idx} OR LOWER(j.status) LIKE $${idx})`);
      }
      const whereSql = where.length ? `WHERE ${where.join(" AND ")}` : "";

      const cntRes = await pool.query(
        `SELECT COUNT(*)::int AS total FROM public.jobs j LEFT JOIN public.users u ON u.id = j.user_id ${whereSql}`,
        params
      );
      const total = Number(cntRes.rows[0]?.total || 0);

      params.push(pageSize, (page - 1) * pageSize);
      const rowsRes = await pool.query(
        `SELECT j.id AS job_id, j.job_name, COALESCE(j.video_filename, j.job_name) AS filename,
                COALESCE(u.username, 'anonymous') AS uploader, j.status, j.progress, j.phase,
                j.latency_sec, j.error, j.created_at, j.completed_at AS processed_at,
                j.video_size_bytes AS size_bytes
         FROM public.jobs j
         LEFT JOIN public.users u ON u.id = j.user_id
         ${whereSql}
         ORDER BY j.created_at DESC NULLS LAST
         LIMIT $${params.length - 1} OFFSET $${params.length}`,
        params
      );

      return res.json({
        jobs: rowsRes.rows,
        total,
        page,
        page_size: pageSize,
      });
    } catch (err) {
      console.error("[bm] jobs DB error:", err.message);
    }
  }

  let rows = Array.from(store.bmJobs.values())
    .filter((j) => j.user_id == null || j.user_id === req.user.id || req.user.role === "admin")
    .map((j) => ({
      job_id: j.job_id,
      job_name: j.job_name,
      filename: j.video_filename || j.job_name,
      uploader: j.username || "anonymous",
      status: j.status,
      progress: j.progress,
      phase: j.phase,
      latency_sec: j.latency_sec,
      error: j.error,
      created_at: j.created_at,
      processed_at: j.processed_at,
      size_bytes: j.size_bytes,
    }));

  if (search) {
    rows = rows.filter(
      (r) =>
        (r.filename || "").toLowerCase().includes(search) ||
        (r.uploader || "").toLowerCase().includes(search) ||
        (r.status || "").toLowerCase().includes(search)
    );
  }

  rows.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  const total = rows.length;
  const start = (page - 1) * pageSize;
  res.json({ jobs: rows.slice(start, start + pageSize), total, page, page_size: pageSize });
});

businessMapRouter.get("/stats", async (req, res) => {
  const pool = getBmPool();
  if (pool) {
    try {
      const params = req.user.role === "admin" ? [] : [req.user.id];
      const where = req.user.role === "admin" ? "" : "WHERE user_id = $1 OR user_id IS NULL";
      const r = await pool.query(
        `SELECT status, COUNT(*)::int AS cnt, COALESCE(SUM(video_size_bytes), 0)::bigint AS bytes
         FROM public.jobs ${where} GROUP BY status`,
        params
      );
      let total_uploaded = 0, processing = 0, completed = 0, cancelled = 0, failed = 0, bytes = 0;
      for (const row of r.rows) {
        const cnt = Number(row.cnt || 0);
        total_uploaded += cnt;
        bytes += Number(row.bytes || 0);
        if (["QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION"].includes(row.status)) processing += cnt;
        else if (["SUCCESS", "PARTIAL"].includes(row.status)) completed += cnt;
        else if (row.status === "CANCELLED") cancelled += cnt;
        else if (["FAILED", "ERROR"].includes(row.status)) failed += cnt;
      }
      return res.json({
        total_uploaded,
        processing,
        completed,
        cancelled,
        failed,
        storage_used_gb: Number((bytes / (1024 ** 3)).toFixed(3)),
      });
    } catch (err) {
      console.error("[bm] stats DB error:", err.message);
    }
  }

  const userJobs = Array.from(store.bmJobs.values()).filter(
    (j) => j.user_id == null || j.user_id === req.user.id || req.user.role === "admin"
  );
  let processing = 0, completed = 0, cancelled = 0, failed = 0, bytes = 0;
  for (const job of userJobs) {
    bytes += job.size_bytes || 0;
    if (["QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION"].includes(job.status)) processing++;
    else if (["SUCCESS", "PARTIAL"].includes(job.status)) completed++;
    else if (job.status === "CANCELLED") cancelled++;
    else if (["FAILED", "ERROR"].includes(job.status)) failed++;
  }
  res.json({
    total_uploaded: userJobs.length,
    processing,
    completed,
    cancelled,
    failed,
    storage_used_gb: Number((bytes / (1024 ** 3)).toFixed(3)),
  });
});

// ---------------- LOG SETTINGS ----------------
function defaultBmLog() {
  return {
    level: "DEBUG",
    folder_path: "D:\\OneNextGen\\Logs",
    enabled: true,
    max_size_mb: 50,
    warning: null,
  };
}

businessMapRouter.get("/settings/log-config", async (req, res) => {
  const uid = req.user.id;
  const pool = getBmPool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT log_level, log_folder_path, enabled, max_size_mb FROM public.user_log_settings WHERE user_id = $1 LIMIT 1`,
        [uid]
      );
      if (r.rows[0]) {
        return res.json({
          user_id: uid,
          level: r.rows[0].log_level,
          folder_path: r.rows[0].log_folder_path,
          enabled: Boolean(r.rows[0].enabled),
          max_size_mb: Number(r.rows[0].max_size_mb),
          warning: null,
        });
      }
    } catch {
      // fallback
    }
  }
  if (!store.bmLogSettings.has(uid)) store.bmLogSettings.set(uid, defaultBmLog());
  res.json({ user_id: uid, ...store.bmLogSettings.get(uid) });
});

businessMapRouter.post("/settings/log-config", async (req, res) => {
  const uid = req.user.id;
  const level = String(req.body?.level || "DEBUG").toUpperCase();
  const folder_path = String(req.body?.folder_path || "D:\\OneNextGen\\Logs");
  const enabled = req.body?.enabled !== undefined ? Boolean(req.body.enabled) : true;
  const max_size_mb = Math.trunc(Number(req.body?.max_size_mb || 50));

  if (!folder_path) return res.status(400).json({ detail: "folder_path is required" });
  if (!Number.isInteger(max_size_mb) || max_size_mb <= 0) {
    return res.status(400).json({ detail: "max_size_mb must be a positive integer" });
  }

  const pool = getBmPool();
  if (pool) {
    try {
      const upd = await pool.query(
        `UPDATE public.user_log_settings
         SET log_level = $1, log_folder_path = $2, enabled = $3, max_size_mb = $4, updated_at = NOW()
         WHERE user_id = $5`,
        [level, folder_path, enabled, max_size_mb, uid]
      );
      if (upd.rowCount === 0) {
        await pool.query(
          `INSERT INTO public.user_log_settings (user_id, log_level, log_folder_path, enabled, max_size_mb, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, NOW(), NOW())`,
          [uid, level, folder_path, enabled, max_size_mb]
        );
      }
    } catch (err) {
      console.error("[bm] save log-config DB error:", err.message);
    }
  }

  const next = { level, folder_path, enabled, max_size_mb, warning: null };
  store.bmLogSettings.set(uid, next);
  res.json({ user_id: uid, ...next });
});

businessMapRouter.post("/settings/log-config/reset", async (req, res) => {
  const uid = req.user.id;
  const next = defaultBmLog();
  const pool = getBmPool();
  if (pool) {
    await pool.query(
      `UPDATE public.user_log_settings SET log_level = $1, log_folder_path = $2, enabled = $3, max_size_mb = $4, updated_at = NOW() WHERE user_id = $5`,
      [next.level, next.folder_path, next.enabled, next.max_size_mb, uid]
    ).catch(() => {});
  }
  store.bmLogSettings.set(uid, next);
  res.json({ user_id: uid, ...next });
});

// ---------------- UPLOAD SETTINGS ----------------
function defaultBmUpload() {
  return { max_upload_size_mb: 500, max_audio_upload_size_mb: 50 };
}

businessMapRouter.get("/settings/upload-config", async (req, res) => {
  const uid = req.user.id;
  const pool = getBmPool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT max_upload_size_mb, max_audio_upload_size_mb FROM public.user_upload_settings WHERE user_id = $1 LIMIT 1`,
        [uid]
      );
      if (r.rows[0]) {
        return res.json({
          user_id: uid,
          max_upload_size_mb: Number(r.rows[0].max_upload_size_mb),
          max_audio_upload_size_mb: Number(r.rows[0].max_audio_upload_size_mb),
        });
      }
    } catch {
      // fallback
    }
  }
  if (!store.bmUploadSettings.has(uid)) store.bmUploadSettings.set(uid, defaultBmUpload());
  res.json({ user_id: uid, ...store.bmUploadSettings.get(uid) });
});

businessMapRouter.post("/settings/upload-config", async (req, res) => {
  const uid = req.user.id;
  const maxMb = Number(req.body?.max_upload_size_mb);
  const maxAudioMb = Number(req.body?.max_audio_upload_size_mb);
  if (
    !Number.isInteger(maxMb) || maxMb < 1 || maxMb > 500 ||
    !Number.isInteger(maxAudioMb) || maxAudioMb < 1 || maxAudioMb > 500
  ) {
    return res.status(400).json({ detail: "Maximum upload file size must be between 1 MB and 500 MB." });
  }

  const pool = getBmPool();
  if (pool) {
    try {
      const upd = await pool.query(
        `UPDATE public.user_upload_settings SET max_upload_size_mb = $1, max_audio_upload_size_mb = $2, updated_at = NOW() WHERE user_id = $3`,
        [maxMb, maxAudioMb, uid]
      );
      if (upd.rowCount === 0) {
        await pool.query(
          `INSERT INTO public.user_upload_settings (user_id, max_upload_size_mb, max_audio_upload_size_mb, created_at, updated_at)
           VALUES ($1, $2, $3, NOW(), NOW())`,
          [uid, maxMb, maxAudioMb]
        );
      }
    } catch (err) {
      console.error("[bm] save upload-config DB error:", err.message);
    }
  }

  const next = { max_upload_size_mb: maxMb, max_audio_upload_size_mb: maxAudioMb };
  store.bmUploadSettings.set(uid, next);
  res.json({ user_id: uid, ...next });
});

businessMapRouter.post("/settings/upload-config/reset", async (req, res) => {
  const uid = req.user.id;
  const next = defaultBmUpload();
  const pool = getBmPool();
  if (pool) {
    await pool.query(
      `UPDATE public.user_upload_settings SET max_upload_size_mb = $1, max_audio_upload_size_mb = $2, updated_at = NOW() WHERE user_id = $3`,
      [next.max_upload_size_mb, next.max_audio_upload_size_mb, uid]
    ).catch(() => {});
  }
  store.bmUploadSettings.set(uid, next);
  res.json({ user_id: uid, ...next });
});

// ---------------- LLM SETTINGS ----------------
function defaultBmLlm() {
  return {
    mode: "default",
    provider: "openrouter",
    model: "openai/gpt-4o-mini",
    primary_api_key: "",
  };
}

function llmResponse(cfg) {
  return {
    mode: cfg.mode,
    provider: cfg.provider,
    model: cfg.model,
    primary_key_configured: Boolean(cfg.primary_api_key),
    primary_key_masked: maskApiKey(cfg.primary_api_key),
    encryption_available: true,
  };
}

businessMapRouter.get("/settings/llm-config", async (req, res) => {
  const uid = req.user.id;
  const pool = getBmPool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT use_custom_key, provider, model, primary_api_key FROM public.user_llm_settings WHERE user_id = $1 LIMIT 1`,
        [uid]
      );
      if (r.rows[0]) {
        return res.json(
          llmResponse({
            mode: r.rows[0].use_custom_key ? "custom" : "default",
            provider: r.rows[0].provider || "openrouter",
            model: r.rows[0].model || "openai/gpt-4o-mini",
            primary_api_key: r.rows[0].primary_api_key || "",
          })
        );
      }
    } catch {
      // fallback
    }
  }
  if (!store.bmLlmSettings.has(uid)) store.bmLlmSettings.set(uid, defaultBmLlm());
  res.json(llmResponse(store.bmLlmSettings.get(uid)));
});

businessMapRouter.post("/settings/llm-config", async (req, res) => {
  const uid = req.user.id;
  const pool = getBmPool();
  let prev = store.bmLlmSettings.get(uid) || defaultBmLlm();
  if (pool && !store.bmLlmSettings.has(uid)) {
    try {
      const cur = await pool.query(
        `SELECT use_custom_key, provider, model, primary_api_key FROM public.user_llm_settings WHERE user_id = $1 LIMIT 1`,
        [uid]
      );
      if (cur.rows[0]) {
        prev = {
          mode: cur.rows[0].use_custom_key ? "custom" : "default",
          provider: cur.rows[0].provider || "openrouter",
          model: cur.rows[0].model || "openai/gpt-4o-mini",
          primary_api_key: cur.rows[0].primary_api_key || "",
        };
      }
    } catch {
      // ignore
    }
  }
  const mode = String(req.body?.mode || "default").toLowerCase() === "custom" ? "custom" : "default";
  const provider = String(req.body?.provider ?? prev.provider);
  const model = String(req.body?.model ?? prev.model);
  let primaryKey = prev.primary_api_key;
  if ("primary_api_key" in (req.body || {})) {
    primaryKey = String(req.body.primary_api_key || "");
  }
  const next = { mode, provider, model, primary_api_key: primaryKey };

  if (pool) {
    try {
      const upd = await pool.query(
        `UPDATE public.user_llm_settings SET use_custom_key = $1, provider = $2, model = $3, primary_api_key = $4, updated_at = NOW() WHERE user_id = $5`,
        [mode === "custom", provider, model, primaryKey, uid]
      );
      if (upd.rowCount === 0) {
        await pool.query(
          `INSERT INTO public.user_llm_settings (user_id, use_custom_key, provider, model, primary_api_key, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, NOW(), NOW())`,
          [uid, mode === "custom", provider, model, primaryKey]
        );
      }
    } catch (err) {
      console.error("[bm] save llm-config DB error:", err.message);
    }
  }

  store.bmLlmSettings.set(uid, next);
  res.json(llmResponse(next));
});

businessMapRouter.post("/settings/llm-config/reset", async (req, res) => {
  const uid = req.user.id;
  const next = defaultBmLlm();
  const pool = getBmPool();
  if (pool) {
    await pool.query(
      `UPDATE public.user_llm_settings SET use_custom_key = FALSE, provider = $1, model = $2, primary_api_key = '', updated_at = NOW() WHERE user_id = $3`,
      [next.provider, next.model, uid]
    ).catch(() => {});
  }
  store.bmLlmSettings.set(uid, next);
  res.json(llmResponse(next));
});

businessMapRouter.post("/settings/llm-config/models", (req, res) => {
  const provider = String(req.body?.provider || "openrouter");
  const models = LLM_PROVIDER_MODELS[provider] || LLM_PROVIDER_MODELS.openrouter;
  res.json({ provider, models });
});
