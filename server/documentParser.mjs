import express from "express";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import multer from "multer";
import { WebSocketServer } from "ws";
import { requireUser, verifyToken, resolveAccountFromPayload } from "./auth.mjs";
import { store, generateUuid } from "./store.mjs";

export const DP_OUTPUT_ROOT = path.join(os.tmpdir(), "nexaflow-dp-output");
fs.mkdirSync(DP_OUTPUT_ROOT, { recursive: true });

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024 },
});

// Track connected WebSocket clients: Set<{ ws, modelId, userId }>
const wsClients = new Set();

export function attachDocumentParserWs(httpServer) {
  const wss = new WebSocketServer({ noServer: true });

  httpServer.on("upgrade", (req, socket, head) => {
    const url = new URL(req.url || "/", "http://localhost");
    if (url.pathname !== "/document/ws/history") return;

    const token = url.searchParams.get("token") || "";
    const modelId = url.searchParams.get("model_id") || "*";
    const payload = verifyToken(token);
    const account = resolveAccountFromPayload(payload);
    if (!account) {
      wss.handleUpgrade(req, socket, head, (ws) => {
        ws.close(4401, "Unauthorized");
      });
      return;
    }

    wss.handleUpgrade(req, socket, head, (ws) => {
      const client = { ws, modelId, userId: account.id };
      wsClients.add(client);
      ws.on("close", () => wsClients.delete(client));
      ws.on("error", () => wsClients.delete(client));
    });
  });
}

function broadcastJobEvent(modelId, event, extra = {}) {
  const msg = JSON.stringify({ event, model_id: modelId || "*", ...extra });
  for (const client of wsClients) {
    if (client.ws.readyState !== 1) continue;
    if (client.modelId === "*" || !modelId || client.modelId === modelId) {
      try {
        client.ws.send(msg);
      } catch {
        // ignore closed sockets
      }
    }
  }
}

function formatNow() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${dd}-${mm}-${yyyy} ${hh}:${min}:${ss}`;
}

function defaultSettings() {
  return {
    log_path: "D:\\OneNextGen\\Logs",
    log_type: "INFO",
    checked: false,
    file_max_size_mb: 50,
    output_base_path: "C:\\Users",
  };
}

function makeSampleValue(label, idx = 0) {
  const name = String(label?.label_name || label?.fieldLabel || label?.fieldName || "field").toLowerCase();
  const dt = String(label?.data_type || label?.datatype || "string").toLowerCase();
  if (name.includes("invoice") && (name.includes("num") || name.includes("no") || name.includes("id"))) {
    return `INV-2026-${100 + idx}`;
  }
  if (name.includes("po") && (name.includes("num") || name.includes("no"))) {
    return `PO-2026-${300 + idx}`;
  }
  if (name.includes("vendor") || name.includes("supplier") || name.includes("company")) {
    return "Acme Industrial Supplies";
  }
  if (dt === "date" || name.includes("date")) {
    return new Date().toISOString().slice(0, 10);
  }
  if (dt === "number" || name.includes("amount") || name.includes("total") || name.includes("price")) {
    return "1250.00";
  }
  if (name.includes("qty") || name.includes("quantity")) {
    return "2";
  }
  return `Extracted ${label?.label_name || label?.fieldLabel || "Value"}`;
}

export const documentParserRouter = express.Router();
documentParserRouter.use(requireUser);

// ---------------- SETTINGS ----------------
documentParserRouter.get("/settings/:userId", (req, res) => {
  const uid = String(req.user.id);
  if (!store.dpSettings.has(uid)) {
    store.dpSettings.set(uid, defaultSettings());
  }
  res.json({ status: "success", settings: store.dpSettings.get(uid) });
});

documentParserRouter.put("/settings/:userId", (req, res) => {
  const uid = String(req.user.id);
  const body = req.body || {};
  const next = {
    log_path: String(body.log_path ?? "D:\\OneNextGen\\Logs"),
    log_type: String(body.log_type ?? "INFO"),
    checked: Boolean(body.checked),
    file_max_size_mb: Number(body.file_max_size_mb || 50),
    output_base_path: String(body.output_base_path ?? "C:\\Users"),
  };
  store.dpSettings.set(uid, next);
  res.json({ status: "success", settings: next });
});

// ---------------- MODELS ----------------
documentParserRouter.get("/models", (req, res) => {
  const models = store.dpModels
    .filter((m) => m.ownerId == null || m.ownerId === req.user.id)
    .map((m) => ({
      ...m,
      processCount: store.dpHistory.filter((h) => h.modelid === m.id).length,
    }));
  res.json({ status: "success", models });
});

documentParserRouter.post("/models", (req, res) => {
  const body = req.body || {};
  const now = formatNow();
  const id = body.id ? String(body.id) : generateUuid();
  const existingIdx = store.dpModels.findIndex((m) => m.id === id);

  const modelObj = {
    id,
    ownerId: req.user.id,
    name: String(body.name || "Untitled Model"),
    engine: String(body.engine || "OCR"),
    documentType: String(body.documentType || "invoice"),
    language: String(body.language || "en"),
    description: String(body.description || ""),
    created: existingIdx >= 0 ? store.dpModels[existingIdx].created : now,
    updated: now,
    processCount: store.dpHistory.filter((h) => h.modelid === id).length,
    formFields: Array.isArray(body.formFields) ? body.formFields : [],
    tableFields: body.tableFields && typeof body.tableFields === "object" ? body.tableFields : {},
  };

  if (existingIdx >= 0) {
    store.dpModels[existingIdx] = modelObj;
  } else {
    store.dpModels.unshift(modelObj);
  }

  res.json({ status: "success", model: modelObj });
});

documentParserRouter.delete("/models/:modelId", (req, res) => {
  const { modelId } = req.params;
  const force = req.query.force === "true";
  const idx = store.dpModels.findIndex((m) => m.id === modelId);
  if (idx === -1) {
    return res.status(404).json({ detail: "Model not found." });
  }

  const relatedJobs = store.dpHistory.filter((h) => h.modelid === modelId);
  if (relatedJobs.length > 0 && !force) {
    return res.status(409).json({
      detail: `This model has ${relatedJobs.length} processing job(s). Pass force=true to delete both.`,
    });
  }

  if (force) {
    store.dpHistory = store.dpHistory.filter((h) => h.modelid !== modelId);
  }
  store.dpModels.splice(idx, 1);
  res.json({ status: "success" });
});

// ---------------- HISTORY ----------------
documentParserRouter.get("/history", (req, res) => {
  const modelId = req.query.model_id ? String(req.query.model_id) : null;
  const rows = store.dpHistory
    .filter((h) => (h.ownerId == null || h.ownerId === req.user.id || req.user.role === "admin"))
    .filter((h) => !modelId || h.modelid === modelId)
    .map(({ pages, ownerId, queuedAt, ...rest }) => rest);

  res.json({ status: "success", history: rows });
});

documentParserRouter.post("/history", (req, res) => {
  const b = req.body || {};
  const historyid = generateUuid();
  const entry = {
    historyid,
    ownerId: req.user.id,
    modelid: String(b.model_id || ""),
    status: String(b.status || "processing"),
    modelname: String(b.model_name || ""),
    documenttype: String(b.document_type || ""),
    createddate: String(b.createddate || formatNow()),
    processdate: String(b.processdate || formatNow()),
    queuedAt: new Date().toISOString(),
    documentname: String(b.document_name || "document.pdf"),
    stp: false,
    error_message: "",
    pages: [],
  };
  store.dpHistory.unshift(entry);
  const { pages, ownerId, queuedAt, ...publicEntry } = entry;
  res.json({ status: "success", history: publicEntry });
});

documentParserRouter.get("/history/:historyId", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (!entry) return res.status(404).json({ detail: "History record not found." });
  const { pages, ownerId, queuedAt, ...historyMeta } = entry;
  res.json({
    status: "success",
    history: historyMeta,
    pages: pages || [],
  });
});

documentParserRouter.patch("/history/:historyId", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (!entry) return res.status(404).json({ detail: "History record not found." });

  if (req.body?.status !== undefined) entry.status = String(req.body.status);
  if (req.body?.stp !== undefined && req.body.stp !== null) entry.stp = Boolean(req.body.stp);
  if (req.body?.error_message !== undefined) entry.error_message = String(req.body.error_message || "");
  res.json({ status: "success" });
});

documentParserRouter.get("/history/:historyId/scan-images", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  const annotated = (entry?.pages || []).map((p) => p.annotated_image_path).filter(Boolean);
  const enhanced = (entry?.pages || []).map((p) => p.enhanced_image_path).filter(Boolean);
  res.json({ status: "success", annotated, enhanced });
});

documentParserRouter.post("/history/:historyId/disconnect-cleanup", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (entry) {
    entry.status = "failed";
    entry.error_message = "Client disconnected during processing.";
    entry.pages = [];
  }
  res.json({ status: "success", job_id: req.params.historyId });
});

documentParserRouter.get("/history/:historyId/pages/pending", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (!entry) return res.status(404).json({ detail: "History record not found." });
  const pages = (entry.pages || []).filter((p) => String(p.status).toLowerCase() === "pending");
  res.json({ status: "success", pages });
});

documentParserRouter.post("/history/:historyId/pages/:pageNumber/submit", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (!entry) return res.status(404).json({ detail: "History record not found." });

  const pageNumber = Number(req.params.pageNumber);
  const groupPages = Array.isArray(req.body?.group_pages) && req.body.group_pages.length
    ? req.body.group_pages.map(Number)
    : [pageNumber];

  for (const p of entry.pages || []) {
    if (groupPages.includes(p.page_number)) {
      p.status = "Completed";
    }
  }

  const allDone = (entry.pages || []).every((p) => String(p.status).toLowerCase() !== "pending");
  if (allDone) {
    entry.status = "completed";
  }

  broadcastJobEvent(entry.modelid, "page_updated", {
    job_id: entry.historyid,
    page_number: pageNumber,
    group_pages: groupPages,
    status: allDone ? "completed" : "processing",
  });

  res.json({
    status: "success",
    csv_file: `${entry.historyid}_page_${pageNumber}.csv`,
    page_number: pageNumber,
    group_pages: groupPages,
    job_completed: allDone,
  });
});

documentParserRouter.post("/history/:historyId/pages/:pageNumber/mark-invalid", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (!entry) return res.status(404).json({ detail: "History record not found." });

  const pageNumber = Number(req.params.pageNumber);
  const groupPages = Array.isArray(req.body?.group_pages) && req.body.group_pages.length
    ? req.body.group_pages.map(Number)
    : [pageNumber];

  for (const p of entry.pages || []) {
    if (groupPages.includes(p.page_number)) {
      p.status = "Marked as Invalid";
    }
  }

  const allDone = (entry.pages || []).every((p) => String(p.status).toLowerCase() !== "pending");
  if (allDone) entry.status = "completed";

  broadcastJobEvent(entry.modelid, "page_updated", {
    job_id: entry.historyid,
    page_number: pageNumber,
    group_pages: groupPages,
    status: allDone ? "completed" : "processing",
  });

  res.json({
    status: "success",
    csv_file: `${entry.historyid}_page_${pageNumber}_invalid.csv`,
    page_number: pageNumber,
    group_pages: groupPages,
    job_completed: allDone,
  });
});

documentParserRouter.post("/history/:historyId/mark-invalid", (req, res) => {
  const entry = store.dpHistory.find((h) => h.historyid === req.params.historyId);
  if (entry) {
    entry.status = "marked_as_invalid";
  }
  res.json({
    status: "success",
    save_dir: `Output/${req.params.historyId}/invalid`,
    saved_images: [],
    saved_csvs: [],
  });
});

// ---------------- UPLOAD & PROCESS ----------------
documentParserRouter.post("/process-upload", upload.single("file"), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ detail: "No file selected." });
  }

  let requestDict = {};
  try {
    requestDict = JSON.parse(req.body?.request_json || "{}");
  } catch {
    return res.status(400).json({ detail: "Invalid request payload." });
  }

  const modelId = String(requestDict?.extrcation_model?.model_id || "");
  const model = store.dpModels.find((m) => m.id === modelId);
  const modelName = model?.name || "default_model";
  const safeName = path.basename(req.file.originalname || "document.png");
  const existingJobId = String(req.body?.job_id || "").trim();
  const historyId = existingJobId || generateUuid();

  // Save uploaded image or generate clean SVG preview for PDFs
  const relImgDir = path.join(modelName.replace(/[^a-zA-Z0-9_-]/g, "_"), historyId, "page_1", "images");
  const absImgDir = path.join(DP_OUTPUT_ROOT, relImgDir);
  fs.mkdirSync(absImgDir, { recursive: true });

  const ext = path.extname(safeName).toLowerCase();
  const isImage = [".png", ".jpg", ".jpeg", ".webp", ".bmp"].includes(ext);
  const previewFilename = isImage ? `page_1${ext}` : "page_1.svg";
  const absPreviewPath = path.join(absImgDir, previewFilename);
  const relOutputPath = `Output/${relImgDir.replace(/\\/g, "/")}/${previewFilename}`;

  if (isImage) {
    fs.writeFileSync(absPreviewPath, req.file.buffer);
  } else {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1040" viewBox="0 0 800 1040">
      <rect width="800" height="1040" fill="#ffffff"/>
      <rect x="36" y="36" width="728" height="968" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2" rx="8"/>
      <text x="64" y="96" font-family="sans-serif" font-size="24" font-weight="bold" fill="#0f172a">Document Preview</text>
      <text x="64" y="132" font-family="sans-serif" font-size="16" fill="#475569">${safeName.replace(/[<>&]/g, "")}</text>
      <line x1="64" y1="160" x2="736" y2="160" stroke="#e2e8f0" stroke-width="2"/>
      <rect x="64" y="190" width="672" height="140" fill="#ffffff" stroke="#3b82f6" stroke-width="2" rx="6"/>
      <text x="84" y="230" font-family="sans-serif" font-size="15" font-weight="600" fill="#1d4ed8">Extracted Header Fields</text>
      <text x="84" y="264" font-family="monospace" font-size="14" fill="#334155">Model: ${modelName.replace(/[<>&]/g, "")}</text>
      <text x="84" y="294" font-family="monospace" font-size="14" fill="#334155">Status: OCR Extraction Complete (Page 1)</text>
      <rect x="64" y="360" width="672" height="280" fill="#ffffff" stroke="#10b981" stroke-width="2" rx="6"/>
      <text x="84" y="400" font-family="sans-serif" font-size="15" font-weight="600" fill="#047857">Detected Table Region</text>
      <line x1="84" y1="425" x2="716" y2="425" stroke="#d1fae5" stroke-width="2"/>
      <text x="84" y="460" font-family="monospace" font-size="13" fill="#475569">Row 1 — Processed item line extracted automatically</text>
      <text x="84" y="495" font-family="monospace" font-size="13" fill="#475569">Row 2 — Processed item line extracted automatically</text>
    </svg>`;
    fs.writeFileSync(absPreviewPath, svg, "utf8");
  }

  // Build extracted labels & tables matching ProcessDocument.jsx expectations
  const labels = Array.isArray(requestDict?.ocr?.labels) ? requestDict.ocr.labels : [];
  const labelExtraction = labels.map((l, idx) => ({
    label_name: l.label_name,
    value: makeSampleValue(l, idx),
    confidence: 0.94,
  }));

  const tableList = Array.isArray(requestDict?.tables?.table_list) ? requestDict.tables.table_list : [];
  const headerExtraction = tableList.map((tbl) => ({
    table_name: tbl.table_name,
    columns: (tbl.headers || []).map((h, colIdx) => ({
      header_name: h.header_name,
      value: [makeSampleValue(h, colIdx + 1), makeSampleValue(h, colIdx + 2)],
    })),
  }));

  const pagePayload = {
    page_number: 1,
    page_group: [1],
    image: relOutputPath,
    annotated_image: relOutputPath,
    label_extraction: labelExtraction,
    header_extraction: headerExtraction,
  };

  let entry = store.dpHistory.find((h) => h.historyid === historyId);
  if (!entry) {
    entry = {
      historyid: historyId,
      ownerId: req.user.id,
      modelid: modelId,
      status: "pending",
      modelname: modelName,
      documenttype: model?.documentType || "Document",
      createddate: formatNow(),
      processdate: formatNow(),
      queuedAt: new Date().toISOString(),
      documentname: safeName,
      stp: false,
      error_message: "",
      pages: [],
    };
    store.dpHistory.unshift(entry);
    broadcastJobEvent(modelId, "job_created", { job_id: historyId, status: "processing" });
  } else {
    entry.status = "pending";
    entry.processdate = formatNow();
    entry.documentname = safeName;
  }

  entry.pages = [
    {
      page_number: 1,
      status: "Pending",
      annotated_image_path: relOutputPath,
      enhanced_image_path: relOutputPath,
      extracted_data: {
        label_extraction: labelExtraction,
        header_extraction: headerExtraction,
      },
    },
  ];

  broadcastJobEvent(modelId, "job_updated", { job_id: historyId, status: "pending" });

  res.json({
    status: "success",
    job_id: historyId,
    historyid: historyId,
    data: [pagePayload],
    annotated_images: [relOutputPath],
    raw_results: [pagePayload],
    page_statuses: { 1: "Pending" },
    uploaded_file: safeName,
  });
});

documentParserRouter.post("/validate-output-path", (_req, res) => {
  res.json({ status: "success", output_folder: "Output" });
});

documentParserRouter.post("/save-csv", (req, res) => {
  const filename = path.basename(req.body?.input_filename || "export").replace(/\.[^.]+$/, "");
  res.json({ status: "success", csv_file: `Output/${filename}_${Date.now()}.csv` });
});
