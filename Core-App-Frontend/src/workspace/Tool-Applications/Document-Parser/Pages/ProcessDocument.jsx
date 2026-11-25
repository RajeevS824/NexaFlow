import React, { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useWorkspaceSideBar } from "../../../context/WorkspaceSideBarContext";
import { API_BASE_URL, authFetch, withAuthToken } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import { getNexaflowUserId } from "../../../utils/documentParserUser";
import "../Styles/commonstyle.css";
import "../Styles/processDocument.css";



// ── Build request.json from model (file path/url is filled in by the
// backend after it saves the uploaded file -- see handleProcess) ──────────
function buildRequestJson(model, outputPath = "", loggingSettings = null) {
  const formFields = model?.formFields || [];
  const tableFields = model?.tableFields || {};

  const labels = formFields.map((f) => ({
    label_name: f.fieldLabel || f.fieldName || "",
    required: f.required !== false,
    data_type: (f.datatype || "string").toLowerCase(),
    AI_skill: f.aiEnabled || false,
    AI_prompt: f.prompt || "",
    aliases: f.aliases || [],
  }));

  const table_list = Object.entries(tableFields).map(([tName, tInfo]) => ({
    table_name: tName,
    enabled: tInfo.required !== false,
    min_confidence: 0.75,
    table_rowStart: tInfo.startRows || [],
    table_rowEnd: tInfo.endRows || [],
    headers: (tInfo.fields || []).map((h) => ({
      header_name: h.fieldLabel || h.fieldName || "",
      required: h.required !== false,
      data_type: (h.datatype || "string").toLowerCase(),
      aliases: h.aliases || [],
    })),
  }));

  const request = {
    schema_version: "1.0",
    document: {
      file_name: "",
      url: "",
      Output_path: outputPath || "",
    },
    extrcation_model: {
      model_id: String(model?.id || ""),
    },
    ocr: {
      enabled: true,
      min_confidence: 0.8,
      labels,
    },
    tables: {
      enabled: table_list.length > 0,
      table_list,
    },
    matching: {
      case_sensitive: false,
      trim_whitespace: false,
      fuzzy_match: true,
    },
  };

  // Add logging metadata from SettingConfig if available
  if (loggingSettings) {
    request.logging_type = loggingSettings.logging_type || "INFO";
    request.logging_path = loggingSettings.logging_path || "";
    request.is_logtolocal = loggingSettings.is_logtolocal === true;
  }

  return request;
}

// ── File upload ─────────────────────────────────────────────────────────
// The document is uploaded to the backend (stored temporarily in its
// uploads folder, deleted again as soon as processing finishes) --
// this replaced a "type the file's local path" field that only ever
// worked when frontend and backend shared the same machine, which
// isn't true once this is hosted in the cloud for multiple users.
const ACCEPTED_TYPES = ["application/pdf"];
const isAcceptedFile = (file) =>
  file && (ACCEPTED_TYPES.includes(file.type) || file.type.startsWith("image/"));

// ── Component ──────────────────────────────────────────────────────────────

const DRAFT_KEY = "processDocumentDraft";

function saveDraft(data) {
  localStorage.setItem(
    DRAFT_KEY,
    JSON.stringify(data)
  );
}

function loadDraft() {
  try {
    return JSON.parse(
      localStorage.getItem(DRAFT_KEY)
    );
  } catch {
    return null;
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
}

async function fetchWithTimeout(url, options = {}) {
  // Timeout removed to allow processing of large files/images without client-side interruption.
  // Routed through authFetch so every request here also carries the
  // logged-in user's Bearer token -- the Document Parser backend
  // requires it on every /document/* route.
  return await authFetch(url, options);
}

async function readJsonResponse(response) {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function escapeCsvValue(value) {
  const text = value == null ? "" : String(value);

  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }

  return text;
}

function ProcessDocument() {
  const [processingCompleted, setProcessingCompleted] =
    useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;
  const { collapseAll } = useWorkspaceSideBar();

  // Collapse the sidebar by default whenever this page is opened
  // (including when it is opened in a new tab via the Process button),
  // so the content area gets full width.
  useEffect(() => {
    collapseAll();
  }, [collapseAll]);

  const [selectedFile, setSelectedFile] = useState(null);
  const [showMain, setShowMain] = useState(false);
  const [popup, setPopup] = useState(null);
  const [successPopup, setSuccessPopup] = useState(false);
  const [invalidSuccessPopup, setInvalidSuccessPopup] = useState(false);
  const [previewSrc, setPreviewSrc] = useState(null);
  const [isPdf, setIsPdf] = useState(false);
  const [requestJson, setRequestJson] = useState(null);  // built JSON object
  const [responseData, setResponseData] = useState(null);
  const [annotatedImages, setAnnotatedImages] = useState([]);
  const [enhancedImages, setEnhancedImages] = useState([]);
  const [manualValues, setManualValues] = useState({});
  const [tableData, setTableData] = useState({});
  const [editableTables, setEditableTables] = useState({});
  const [showReason, setShowReason] = useState({});
  const [reasonPopup, setReasonPopup] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showProcessPopup, setShowProcessPopup] = useState(false);
  const [activeField, setActiveField] = useState(null);
  const [activeTab, setActiveTab] = useState("preview"); // "preview" | "json"
  const [selectionBox, setSelectionBox] = useState(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [startPoint, setStartPoint] = useState(null);
  const [historyId, setHistoryId] = useState(null);
  const [autoReprocess, setAutoReprocess] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [pages, setPages] = useState([]);
  const [currentModel, setCurrentModel] = useState(null);
  const [allModels, setAllModels] = useState([]);
  const [reprocessHistoryId, setReprocessHistoryId] = useState(null);
  const [imageZoom, setImageZoom] = useState(100);
  const [fieldFilter, setFieldFilter] = useState("all");
  const [sectionFilter, setSectionFilter] = useState("all");
  const [outputPath, setOutputPath] = useState("");
  const [processedPages, setProcessedPages] = useState(new Set());
  const [isJobCompleted, setIsJobCompleted] = useState(false);
  const [pendingPageIndices, setPendingPageIndices] = useState([]);
  const [pendingIndex, setPendingIndex] = useState(0);
  const [reprocessPopup, setReprocessPopup] = useState(null); // {modelName, historyId}
  const fileInputRef = useRef(null);
  const viewerRef = useRef(null);
  const validationRef = useRef(null);
  const resizerRef = useRef(null);
  const imageContainerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const [selectedField, setSelectedField] = useState(null);
  const [invalidFields, setInvalidFields] = useState([]);
  useEffect(() => {

    const draft = loadDraft();

    if (!draft) return;

    setPreviewSrc(
      draft.previewSrc || null
    );

    setIsPdf(
      draft.isPdf || false
    );

    setShowMain(
      draft.showMain || false
    );

    setRequestJson(
      draft.requestJson || null
    );

    setResponseData(
      draft.responseData || null
    );

    setAnnotatedImages(
      draft.annotatedImages || []
    );

    setEnhancedImages(
      draft.enhancedImages || []
    );

    setManualValues(
      draft.manualValues || {}
    );

    setEditableTables(
      draft.editableTables || {}
    );

    setHistoryId(
      draft.historyId || null
    );

    setOutputPath(
      draft.outputPath || ""
    );

  }, []);

// ── Load output base path from DB settings ──────────────────────────
  useEffect(() => {
    const fetchOutputBasePath = async () => {
      try {
        const userId = getNexaflowUserId() ?? 1;
        const res = await authFetch(`${API_BASE_URL}/document/settings/${userId}`);
        const data = await res.json();
        if (data.status === "success" && data.settings) {
          const basePath = data.settings.output_base_path || "C:\\Users";
          setOutputPath(basePath);
        }
      } catch (err) {
        console.warn("Failed to load output base path from settings, using default.", err);
      }
    };
    fetchOutputBasePath();
  }, []);

  useEffect(() => {

    saveDraft({
      previewSrc,
      isPdf,
      showMain,
      requestJson,
      responseData,
      annotatedImages,
      enhancedImages,
      manualValues,
      editableTables,
      historyId,
      outputPath
    });

  }, [
    previewSrc,
    isPdf,
    showMain,
    requestJson,
    responseData,
    annotatedImages,
    enhancedImages,
    manualValues,
    editableTables,
    historyId,
    outputPath
  ]);
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isProcessing) {
        e.preventDefault();
        e.returnValue = "Document is currently being processed. Leaving this page will cancel the operation. Do you want to stop processing?";
        return e.returnValue;
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      if (isProcessing && abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isProcessing]);
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const modelId = params.get("modelId");
    const incomingReprocessHistoryId = params.get("reprocessHistoryId");

    if (incomingReprocessHistoryId) {
      setReprocessHistoryId(incomingReprocessHistoryId);
      setAutoReprocess(true);
    } else {
      setReprocessHistoryId(null);
      setAutoReprocess(false);
    }

    const loadModel = async () => {
      if (!modelId) {
        setCurrentModel(null);
        setAllModels([]);
        return;
      }

      try {
        const response = await authFetch(`${API_BASE_URL}/document/models`);
        const data = await response.json();
        const rows = Array.isArray(data?.models) ? data.models : [];
        setAllModels(rows);
        setCurrentModel(rows.find((m) => String(m.id) === String(modelId)) || null);
      } catch (error) {
        console.error("Unable to load selected model:", error);
        setCurrentModel(null);
        setAllModels([]);
      }
    };

    loadModel();

    // If reprocessHistoryId is set, check the job status and show the reprocess popup
    if (incomingReprocessHistoryId) {
      (async () => {
        try {
          const histResponse = await authFetch(`${API_BASE_URL}/document/history/${encodeURIComponent(incomingReprocessHistoryId)}`);
          if (histResponse.ok) {
            const histData = await histResponse.json();
            const jobStatus = (histData?.history?.status || "").toLowerCase();
            if (["cancelled", "failed"].includes(jobStatus)) {
              // Show the reprocess popup with model name for cancelled or failed jobs
              const modelName = histData?.history?.modelname || currentModel?.name || "the previously selected model";
              setReprocessPopup({
                modelName: modelName,
                historyId: incomingReprocessHistoryId,
              });
            }
          }
        } catch (e) {
          console.warn("[reprocess] Failed to check job status:", e);
        }
      })();
    }
  }, [location.search]);
  const formFields = currentModel?.formFields || [];
  const tables = currentModel?.tableFields || {};

  const getHistoryImageUrl = (path) => {
    if (!path) return null;

    let cleaned = String(path).replace(/\\/g, "/").trim();

    // If this is a full URL, keep only the path portion.
    if (/^https?:\/\//i.test(cleaned)) {
      const url = new URL(cleaned);
      cleaned = url.pathname;
    }

    // Remove leading slashes and windows drive prefixes.
    cleaned = cleaned.replace(/^\/+/, "");
    cleaned = cleaned.replace(/^[A-Za-z]:\//, "");

    // Strip leading "output/" if present.
    if (cleaned.toLowerCase().startsWith("output/")) {
      cleaned = cleaned.slice("output/".length);
    }

    // If the path contains a filesystem root like "Output/<workspace>/...",
    // strip everything up to and including "Output/<workspace>/" so the
    // remainder is relative to OUTPUT_ROOT.
    // Examples seen in this project:
    // - "backend/Output/<job>/page_1/images/..."
    // - "Output/<job>/<job>/page_1/images/..." (duplicated job id)
    const parts = cleaned.split("/").filter(Boolean);
    const outputIdx = parts.findIndex((p) => p.toLowerCase() === "output");

    if (outputIdx !== -1) {
      // If we have "Output/<workspace>/...", drop through <workspace>.
      if (parts.length > outputIdx + 1) {
        const workspace = parts[outputIdx + 1];
        parts.splice(0, outputIdx + 1); // keep from <workspace> onward
        // Now drop duplicated workspace if it appears twice consecutively.
        if (parts[0] && parts.length > 1 && parts[1] === workspace) {
          parts.splice(0, 1);
        }
      }
    }

    // Also handle accidental duplication like "<job>/<job>/page_1/...".
    // If the first segment appears again as the second, drop the first.
    if (parts.length > 2 && parts[0] === parts[1]) {
      parts.splice(0, 1);
    }

    cleaned = parts.join("/");

    // /output/* now requires authentication (see DP-backend/app/main.py).
    // <img src> can't send a custom Authorization header, so the token
    // is appended as a query param instead -- the backend accepts either.
    // Every <img> in this file gets its src from this function (directly
    // or via enhancedImages/annotatedImages, which are populated by it),
    // so patching the return here covers all of them.
    return withAuthToken(`${API_BASE_URL}/output/${cleaned}`);
  };

  const initializeFromResponseData = (responsePayload) => {
    if (!currentModel || !responsePayload) return;

    const initialTables = {};
    Object.keys(tables).forEach((tableName) => {
      initialTables[tableName] = getTableRowsFromResponse(
        responsePayload,
        tableName
      );
    });

    setTableData(initialTables);
    setEditableTables(initialTables);
    setManualValues({});
  };

  const loadHistoryResult = async (historyIdValue) => {
    try {
      // First try to load only pending pages (for resume)
      let pendingPages = [];
      try {
        const pendingResponse = await authFetch(
          `${API_BASE_URL}/document/history/${encodeURIComponent(historyIdValue)}/pages/pending`
        );
        if (pendingResponse.ok) {
          const pendingData = await pendingResponse.json();
          pendingPages = Array.isArray(pendingData.pages) ? pendingData.pages : [];
        }
      } catch (e) {
        console.warn("[loadHistoryResult] Failed to load pending pages:", e);
      }

      // Load full history for context (images, etc.)
      const response = await authFetch(
        `${API_BASE_URL}/document/history/${encodeURIComponent(historyIdValue)}`
      );
      const data = await response.json();


      if (!response.ok) {
        setPopup(data.detail || "Unable to load history result.");
        return;
      }

      // DEBUG: surface page / workspace resolution details to help diagnose 404s
      try {
        console.debug("[loadHistoryResult] history fetched", {
          historyId: historyIdValue,
          page_count: Array.isArray(data.pages) ? data.pages.length : 0,
          pages: data.pages,
          page_statuses: data.history?.page_statuses || data.page_statuses || null,
          pendingPagesCount: pendingPages.length,
        });
      } catch (dbgErr) {
        console.warn("[loadHistoryResult debug] failed to log history details:", dbgErr);
      }

      const allPages = Array.isArray(data.pages) ? data.pages : [];
      setPages(allPages);
      const historyEntry = data.history || {};

      // Use the local variable allPages (NOT the state variable pages) because
      // the state update from setPages() hasn't taken effect yet (React batching).
      const _pages = allPages;

      // If we have pending pages, use those. Otherwise fall back to all pages.
      const pagesToUse = pendingPages.length > 0 ? pendingPages : allPages;

      if (pagesToUse.length === 0) {
        const jobStatus = (historyEntry.status || "").toLowerCase();

        if (jobStatus === "pending" || jobStatus === "processing") {
          // Never finalized — show upload UI so user can reprocess.
          setHistoryId(historyIdValue);
          setIsProcessing(false);
          return;
        }

        // For failed or cancelled jobs: don't show any error popup,
        // simply set the historyId so the user can click Reprocess.
        if (jobStatus === "failed" || jobStatus === "cancelled") {
          setHistoryId(historyIdValue);
          setIsProcessing(false);
          return;
        }

        // For completed / failed jobs: try to recover images from disk
        console.warn("[loadHistoryResult] pages=0 — trying disk scan fallback.");
        try {
          const scanRes = await authFetch(`${API_BASE_URL}/document/history/${encodeURIComponent(historyIdValue)}/scan-images`);
          if (scanRes.ok) {
            const scanData = await scanRes.json();
            const scannedAnnotated = (scanData.annotated || []).map((p) => getHistoryImageUrl(p)).filter(Boolean);
            const scannedEnhanced = (scanData.enhanced || []).map((p) => getHistoryImageUrl(p)).filter(Boolean);

            if (scannedAnnotated.length > 0 || scannedEnhanced.length > 0) {
              setHistoryId(historyIdValue);
              // The history API returns the original document file name
              // (from dbo.documents.original_filename) under the "documentname"
              // key — not "original_filename". Using the right field here keeps
              // the Validate/reprocess flow from falling back to the generic
              // "Previous Document" placeholder when saving Submit / Mark-as-Invalid.
              setSelectedFile({ name: historyEntry.documentname || "Previous Document" });
              setAnnotatedImages(scannedAnnotated);
              setEnhancedImages(scannedEnhanced);
              setPreviewSrc(scannedEnhanced[0] || scannedAnnotated[0] || null);
              setIsPdf(false);
              setCurrentPage(0);
              setShowMain(true);
              setProcessingCompleted(true);
              setIsProcessing(false);
              setActiveTab("preview");
              return;
            }
          }
        } catch (scanErr) {
          console.warn("[loadHistoryResult] scan-images fallback failed:", scanErr);
        }

        setHistoryId(historyIdValue);
        setPopup(
          "This history entry has no saved pages to display. It may have been " +
          "processed before this build, or page persistence failed for that run."
        );
        return;
      }

      // Determine which page indices have already been processed
      const doneIndices = new Set();
      allPages.forEach((page, idx) => {
        const status = (page.status || "Pending").toLowerCase();
        if (status === "completed" || status === "marked as invalid") {
          doneIndices.add(idx);
        }
      });
      setProcessedPages(doneIndices);

      // Build index list of pending pages
      const pendingIndices = [];
      pagesToUse.forEach((page) => {
        const idx = page.page_number ? page.page_number - 1 : allPages.indexOf(page);
        if (!doneIndices.has(idx)) {
          pendingIndices.push(idx);
        }
      });
      setPendingPageIndices(pendingIndices);
      setPendingIndex(0);

      // Determine the first pending page index to start from
      let firstPendingIdx = 0;
      while (firstPendingIdx < allPages.length && doneIndices.has(firstPendingIdx)) {
        firstPendingIdx++;
      }
      // If all pages are done, start at 0
      if (firstPendingIdx >= allPages.length) firstPendingIdx = 0;
      // Determine which pages to display: prefer pending pages (pagesToUse),
      // otherwise fall back to all pages. This avoids fetching response.json
      // for completed pages that may not have per-page response files.
      const pagesForDisplay = pagesToUse.length > 0 ? pagesToUse : allPages;

      const workspaceName = (() => {
        // Collect candidate paths from both all pages and pages chosen for display
        const pagePaths = [
          ...(allPages || []).map((p) => p?.enhanced_image_path || p?.annotated_image_path).filter(Boolean),
          ...(pagesForDisplay || []).map((p) => p?.enhanced_image_path || p?.annotated_image_path).filter(Boolean),
        ];

        const seen = new Set();
        const candidatePaths = [];
        pagePaths.forEach((p) => { if (p && !seen.has(p)) { seen.add(p); candidatePaths.push(p); } });
        if (historyEntry?.output_folder) candidatePaths.push(historyEntry.output_folder);
        candidatePaths.push(historyIdValue);

        for (const candidate of candidatePaths) {
          const pathText = String(candidate).replace(/\\/g, "/").trim();
          if (!pathText) continue;

          // If absolute URL with output/<model>/<job>/... -> return 'model/job'
          if (/^https?:\/\//i.test(pathText)) {
            const withoutScheme = pathText.replace(/^https?:\/\//i, "");
            const urlParts = withoutScheme.split("/");
            if (urlParts.length > 3 && urlParts[1].toLowerCase() === "output") {
              return `${urlParts[2]}/${urlParts[3]}`;
            }
            if (urlParts.length > 2 && urlParts[1].toLowerCase() === "output") {
              return urlParts[2];
            }
          }

          const parts = pathText.split("/");
          // If path contains 'output', next two segments are model and job (if present)
          const outputIndex = parts.findIndex((part) => part.toLowerCase() === "output");
          if (outputIndex >= 0) {
            if (parts.length > outputIndex + 2) {
              return `${parts[outputIndex + 1]}/${parts[outputIndex + 2]}`;
            }
            if (parts.length > outputIndex + 1) {
              return parts[outputIndex + 1];
            }
          }

          // If we see the job id in the path and there's a preceding segment,
          // return 'model/job' (handles 'dws/<job>/...')
          const jobIdx = parts.findIndex((part) => part === historyIdValue || part.toLowerCase() === String(historyIdValue).toLowerCase());
          if (jobIdx > 0) {
            return `${parts[jobIdx - 1]}/${parts[jobIdx]}`;
          }

          // As a last resort, if the candidate equals the job id, return it
          if (pathText === historyIdValue || pathText.toLowerCase() === String(historyIdValue).toLowerCase()) {
            return pathText;
          }
        }
        return "";
      })();

      // DEBUG: log resolved workspaceName and which pages will be displayed/fetched
      try {
        console.debug("[loadHistoryResult] resolved workspaceName and pagesForDisplay", {
          workspaceName,
          pagesForDisplayCount: pagesForDisplay.length,
          pagesForDisplaySample: pagesForDisplay.slice(0, 5).map(p => ({ page_number: p.page_number, status: p.status })),
        });
      } catch (dbgErr) {
        console.warn("[loadHistoryResult debug] failed to log workspaceName/pagesForDisplay:", dbgErr);
      }


      let previewPath = "";
      let annotatedUrls = [];
      let enhancedUrls = [];
      let jsonData = null;

      if (pagesForDisplay.length > 0) {
        previewPath = pagesForDisplay[0].enhanced_image_path || pagesForDisplay[0].annotated_image_path;
        annotatedUrls = pagesForDisplay
          .map((page) => getHistoryImageUrl(page.annotated_image_path || page.enhanced_image_path))
          .filter(Boolean);
        enhancedUrls = pagesForDisplay
          .map((page) => getHistoryImageUrl(page.enhanced_image_path || page.annotated_image_path))
          .filter(Boolean);
      }

      let loadedOutputPath = "";

      if (workspaceName && allPages.length > 0) {
        try {
          // ── Load request.json to extract the saved output_path ──
          const requestJsonUrl = `${API_BASE_URL}/output/${encodeURIComponent(
            workspaceName
          )}/request/request.json`;
          try {
            const reqRes = await authFetch(requestJsonUrl);
            if (reqRes.ok) {
              const reqParsed = await reqRes.json();
              loadedOutputPath = reqParsed?.document?.Output_path || "";
            }
          } catch (reqErr) {
            console.warn("[loadHistoryResult] Failed to load request.json:", reqErr);
          }

          const perPageResults = await Promise.all(
            pagesForDisplay.map(async (page) => {
              const pageNum = page.page_number || 1;
              const pageJsonUrl = `${API_BASE_URL}/output/${encodeURIComponent(
                workspaceName
              )}/page_${pageNum}/response/response.json`;
              try {
                const res = await authFetch(pageJsonUrl);
                if (!res.ok) {
                  console.warn(`[loadHistoryResult] ${res.status} fetching`, pageJsonUrl);
                  return null;
                }
                const parsed = await res.json();
                // Backend writes each page's response.json as a single-item
                // array ([pageObj]) so the on-disk shape matches the old
                // combined file's per-page entries.
                const pageData = Array.isArray(parsed) ? parsed[0] : parsed;

                // Extract output_path from response.json as fallback if request.json didn't have it
                if (!loadedOutputPath && pageData?.output_path) {
                  loadedOutputPath = pageData.output_path;
                }

                return pageData;
              } catch (err) {
                console.warn("[loadHistoryResult] fetch failed for", pageJsonUrl, err);
                return null;
              }
            })
          );

          const merged = perPageResults.filter(Boolean);
          if (merged.length > 0) {
            jsonData = merged;
            const firstPage = jsonData[0];
            const metadata = firstPage?.metadata || {};
            const fallbackPath = metadata.image || metadata.annotated_image || firstPage?.image || firstPage?.annotated_image || "";
            if (!previewPath && fallbackPath) {
              previewPath = fallbackPath;
            }
            if (annotatedUrls.length === 0) {
              annotatedUrls = jsonData
                .map((page) => getHistoryImageUrl(page?.metadata?.annotated_image || page?.annotated_image || page?.metadata?.image || page?.image))
                .filter(Boolean);
            }
            if (enhancedUrls.length === 0) {
              enhancedUrls = jsonData
                .map((page) => getHistoryImageUrl(page?.metadata?.image || page?.image || page?.metadata?.annotated_image || page?.annotated_image))
                .filter(Boolean);
            }
          } else {
            console.warn(
              "[loadHistoryResult] every page's response.json failed to load -- " +
              "see the per-page 404/error lines above for the exact URLs tried."
            );
          }
        } catch (err) {
          console.warn("Unable to load per-page response.json for history result:", err);
        }
      }

      // Populate the Output Path textbox with the saved output path
      if (loadedOutputPath) {
        setOutputPath(loadedOutputPath);
      }

      if (!previewPath && enhancedUrls.length > 0) {
        previewPath = enhancedUrls[0];
      }

      const previewUrl = getHistoryImageUrl(previewPath);

      // The history API returns the original document file name (from
      // dbo.documents.original_filename) under the "documentname" key — not
      // "original_filename". Using the right field here keeps the
      // Validate/reprocess flow from falling back to the generic
      // "Previous Document" placeholder when saving Submit / Mark-as-Invalid.
      setSelectedFile({ name: historyEntry.documentname || "Previous Document" });
      setPreviewSrc(previewUrl);
      setIsPdf(false);
      setAnnotatedImages(annotatedUrls);
      setEnhancedImages(enhancedUrls);
      setCurrentPage(firstPendingIdx);
      setResponseData(jsonData || null);
      setShowMain(true);
      setProcessingCompleted(true);
      setIsProcessing(false);
      setActiveTab("preview");
      setHistoryId(historyIdValue);
    } catch (error) {
      console.error(error);
      setPopup("Unable to load history result.");
    }
  };

  useEffect(() => {
    if (!autoReprocess || !reprocessHistoryId) return;
    loadHistoryResult(reprocessHistoryId).finally(() => {
      setAutoReprocess(false);
    });
  }, [autoReprocess, reprocessHistoryId]);

  useEffect(() => {
    if (currentModel && responseData) {
      initializeFromResponseData(responseData);
    }
  }, [currentModel, responseData]);

  // Display name for the uploaded document (tab title, CSV filename, etc).
  const getDocumentDisplayName = () => {
    return selectedFile ? selectedFile.name : "";
  };

  const getCurrentPreviewUrl = () => {
    // "Original Document" must never show annotated images.
    // Always use enhanced images (output from image_enhancement.py).
    // enhancedImages already contains fully resolved URLs (processed through
    // getHistoryImageUrl in loadHistoryResult and handleProcess), so return
    // the URL directly without calling getHistoryImageUrl again.
    if (!enhancedImages || enhancedImages.length === 0) return null;
    return enhancedImages[Math.min(currentPage, enhancedImages.length - 1)];
  };


  const getPreviewPageCount = () => {
    return enhancedImages?.length || 0;
  };


  // ── Page-stream-segmentation grouping ────────────────────────────────
  // The backend writes a `page_group` array (1-based page numbers) onto
  // every page's response payload whenever page-stream segmentation
  // decided a run of pages belongs to the same source document (e.g.
  // groups=[[1,2],[3,4],[5,6,7],[8]] -> pages 1 and 2 both carry
  // page_group=[1,2]). Ungrouped pages simply carry their own page
  // number, e.g. page_group=[8], so callers never need a separate
  // "is this page grouped" branch.
  const getPageGroupPayload = (pageIndex, data = responseData) => {
    const page = getPageResponseAtIndexFromPayload(data, pageIndex);
    const raw = Array.isArray(page?.page_group) && page.page_group.length
      ? page.page_group
      : [pageIndex + 1];
    // Convert the 1-based page numbers coming from the backend to 0-based
    // page indices used everywhere else in this component.
    return [...new Set(raw.map((n) => n - 1))].sort((a, b) => a - b);
  };

  /** True when pageA and pageB (0-based indices) belong to the same
   *  page-stream-segmentation group. */
  const isSameGroup = (pageA, pageB, data = responseData) => {
    if (pageA === pageB) return true;
    return getPageGroupPayload(pageA, data).includes(pageB);
  };

  /** Every distinct page-stream-segmentation group in `data`, as sorted
   *  0-based page-index arrays, in document order (e.g.
   *  [[0,1],[2],[3,4]] for groups=[[1,2],[3],[4,5]]). */
  const getUniqueGroups = (data) => {
    const pageCount = Array.isArray(data)
      ? data.length
      : Array.isArray(data?.data)
        ? data.data.length
        : data
          ? 1
          : 0;
    const seen = new Set();
    const groups = [];
    for (let idx = 0; idx < pageCount; idx++) {
      if (seen.has(idx)) continue;
      const group = getPageGroupPayload(idx, data);
      group.forEach((g) => seen.add(g));
      groups.push(group);
    }
    return groups;
  };

  const nextPage = () => {
    const pageCount = getPreviewPageCount();
    if (currentPage < pageCount - 1) setCurrentPage((p) => p + 1);
  };


  const prevPage = () => {
    if (currentPage > 0 && !processedPages.has(currentPage - 1)) setCurrentPage((p) => p - 1);
  };

  // Auto-advance to next page after processing the current one
  const advanceToNextPending = (justCompletedIndices = []) => {
    const pageCount = getPreviewPageCount();
    // The pages we just marked Completed / Marked as Invalid may not have
    // reached `processedPages` state yet (state updates are async), so
    // merge them in locally rather than trusting the stale closure value
    // -- otherwise a group's own later pages (e.g. finishing group [4,5]
    // from page 4) wouldn't be recognized as done yet and we'd wrongly
    // stop on page 5 instead of skipping past the whole group.
    const effectiveProcessed = new Set(processedPages);
    justCompletedIndices.forEach((idx) => effectiveProcessed.add(idx));

    // 1) Look forward for the next pending page/group.
    let nextIdx = currentPage + 1;
    while (nextIdx < pageCount && effectiveProcessed.has(nextIdx)) {
      nextIdx++;
    }
    if (nextIdx < pageCount) {
      setCurrentPage(nextIdx);
      return;
    }

    // 2) Nothing pending after this page -- fall back to the nearest
    // pending page before it. E.g. groups [[1,2],[3],[4,5]]: finishing
    // group [4,5] (no group after it) should land back on group [3]'s
    // page rather than staying stuck on an already-completed page.
    let prevIdx = currentPage - 1;
    while (prevIdx >= 0 && effectiveProcessed.has(prevIdx)) {
      prevIdx--;
    }
    if (prevIdx >= 0) {
      setCurrentPage(prevIdx);
    }
    // else: no pending page left anywhere -- stay put; the job-completion
    // check elsewhere flips the UI to "completed".
  };

  // Tracks the page we were on before the current render, so the effect
  // below can tell whether we just moved within the same segmentation
  // group (carry values forward) or jumped to a genuinely different
  // document (clear the form).
  const previousPageRef = useRef(null);

  // Reset per-page state when the current page changes (after submit/invalid)
  useEffect(() => {
    const previousPage = previousPageRef.current;
    previousPageRef.current = currentPage;

    // A required field the user filled in on page 1 of a group must still
    // show as filled when they click Next to page 2 of that same group --
    // page 2 "belongs to" page 1. Only clear the manually-typed values when
    // we've actually left the group (or this is the very first page load).
    const stayedInSameGroup =
      previousPage !== null && isSameGroup(previousPage, currentPage);

    if (!stayedInSameGroup) {
      setManualValues({});
    }

    // Re-initialize table data from the new page's response
    if (currentModel && responseData) {
      const pagePayload = getPagePayload(responseData);
      if (pagePayload) {
        const initialTables = {};
        Object.keys(tables).forEach((tableName) => {
          initialTables[tableName] = getTableRowsFromResponse(
            responseData,
            tableName
          );
        });
        setEditableTables(initialTables);
      }
    }
  }, [currentPage]);

  const handleFileChange = (e) => {
    collapseAll();

    const file = e.target.files[0];
    if (!file) return;

    // Allow only PDF and Images
    const isSupported =
      file.type === "application/pdf" ||
      file.type.startsWith("image/");

    if (!isSupported) {
      setSelectedFile(null);
      setPreviewSrc(null);
      setIsPdf(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      setPopup("File format not supported.");
      return;
    }

    setSelectedFile(file);

    localStorage.setItem(
      "draftFileName",
      file.name
    );

    if (file.type === "application/pdf") {
      setIsPdf(true);
      setPreviewSrc(URL.createObjectURL(file));
    } else {
      setIsPdf(false);

      const reader = new FileReader();
      reader.onload = (ev) =>
        setPreviewSrc(ev.target.result);

      reader.readAsDataURL(file);
    }
  };

  const confirmProcess = () => {
    setShowProcessPopup(false);

    setTimeout(() => {
      handleProcess();
    }, 100);
  };

  const validateOutputPath = async (pathValue) => {
    const trimmedPath = (pathValue || "").trim();

    if (!trimmedPath) {
      setPopup("Please enter a valid output folder path.");
      return false;
    }

    try {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/document/validate-output-path`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ output_folder: trimmedPath }),
        }
      );

      const result = await readJsonResponse(response);

      if (!response.ok) {
        setPopup(result.detail || "Please enter a valid output folder path.");
        return false;
      }

      return true;
    } catch (error) {
      setPopup("Unable to validate the output path. Please enter a valid output folder path.");
      return false;
    }
  };

  const handleProcess = async () => {
    collapseAll();

    if (!selectedFile) {
      setPopup("Please choose a document to upload (PDF, JPG, PNG, TIFF, or BMP).");
      return;
    }

    if (!isAcceptedFile(selectedFile)) {
      setPopup("File format not supported.");
      return;
    }

    if (!currentModel?.id) {
      setPopup("Please select an extraction model before processing.");
      return;
    }

    const isOutputPathValid = await validateOutputPath(outputPath);

    if (!isOutputPathValid) {
      return;
    }

    setIsProcessing(true);

    abortControllerRef.current = new AbortController();

    // Fetch logging settings from SettingConfig and include in request
    let loggingSettings = null;
    try {
      const userId = getNexaflowUserId() ?? 1;
      const settingsRes = await authFetch(`${API_BASE_URL}/document/settings/${userId}`);
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        if (settingsData.status === "success" && settingsData.settings) {
          const s = settingsData.settings;
          loggingSettings = {
            logging_type: s.log_type || "INFO",
            logging_path: s.log_path || "",
            is_logtolocal: s.checked === true,
          };
        }
      }
    } catch (e) {
      console.warn("[handleProcess] Failed to fetch logging settings, proceeding without:", e);
    }

    const json = buildRequestJson(currentModel, outputPath, loggingSettings);

    setRequestJson(json);

    try {
      // Real upload: the file's bytes are sent to the backend, which
      // stores it temporarily in its uploads folder, processes it,
      // and deletes it again once the pipeline finishes (success or
      // failure) -- see app/api/routes/document.py:process_upload.
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("request_json", JSON.stringify(json));
      formData.append("job_id", reprocessHistoryId || historyId || "");

      const response = await fetchWithTimeout(
        `${API_BASE_URL}/document/process-upload`,
        {
          method: "POST",
          body: formData,
          signal: abortControllerRef.current.signal,
        }
      );

      const result = await readJsonResponse(response);

      if (!response.ok) {
        setIsProcessing(false);
        setPopup(result.detail);
        return;
      }

      setResponseData(result);

      const annotated = (result.annotated_images || [])
        .map((img) => getHistoryImageUrl(img))
        .filter(Boolean);
      setAnnotatedImages(annotated);

      const enhanced = (result.raw_results || [])
        .map((page) => getHistoryImageUrl(page?.image))
        .filter(Boolean);
      setEnhancedImages(enhanced);

      const enrichedPreview = enhanced.length > 0
        ? enhanced[0]
        : annotated.length > 0
          ? annotated[0]
          : null;
      if (enrichedPreview) {
        setPreviewSrc(enrichedPreview);
        setIsPdf(false);
      }


      const initialTables = {};

      Object.keys(tables).forEach((tableName) => {
        initialTables[tableName] = getTableRowsFromResponse(
          result,
          tableName
        );
      });

      setTableData(initialTables);

      const tempTables = {};

      Object.keys(tables).forEach((tableName) => {
        tempTables[tableName] =
          getTableRowsFromResponse(
            result,
            tableName
          );
      });

      setEditableTables(tempTables);
      setManualValues({});

      try {
        localStorage.setItem("lastRequest", JSON.stringify(json, null, 2));
      } catch { }

      let currentHistoryId = null;

      if (reprocessHistoryId) {
        const id = reprocessHistoryId;
        setHistoryId(id);
        currentHistoryId = id;
        await authFetch(`${API_BASE_URL}/document/history/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "processing" }),
        });
      } else if (result?.historyid) {
        // Server created the history entry for us during processing
        currentHistoryId = result.historyid;
        setHistoryId(result.historyid);
      } else {
        const historyResponse = await authFetch(`${API_BASE_URL}/document/history`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model_id: currentModel?.id || "",
            model_name: currentModel?.name || "",
            document_type: currentModel?.documentType || "",
            createddate: currentModel?.created || "",
            processdate: new Date().toLocaleString(),
            status: "processing",
          }),
        });
        const historyResult = await historyResponse.json();
        if (historyResponse.ok) {
          currentHistoryId = historyResult?.history?.historyid || null;
          setHistoryId(currentHistoryId);
        }
      }

      // The backend already ran per-group straight-through-processing
      // (STP) before returning: any page-stream-segmentation group whose
      // required fields/table-cells were all present had its CSV saved
      // to extractedoutput/success/ and its pages marked "Completed"
      // (see document_service.py's STEP 7.6 and result.page_statuses).
      // The frontend's job here is just to read that back -- never to
      // redo the check or re-submit, which would double-write CSVs.
      const groups = getUniqueGroups(result);
      const backendPageStatuses = result.page_statuses || {};
      const isPageAutoCompleted = (pageIndex) =>
        String(backendPageStatuses[pageIndex + 1] || "").toLowerCase() === "completed";
      const autoCompletedIndices = groups
        .filter((g) => isPageAutoCompleted(g[0]))
        .flat();
      const anyGroupPending = groups.some((g) => !isPageAutoCompleted(g[0]));

      // Filter the result and images to only include pages with status = 'Pending'
      // so the Process UI shows only pages that require manual validation.
      try {
        const pageStatuses = result.page_statuses || {};
        const pendingMask = [];
        // enhanced/annotated arrays are parallel to raw_results pages
        for (let i = 0; i < Math.max(enhanced.length, annotated.length, (result.data && Array.isArray(result.data) ? result.data.length : (result.raw_results ? result.raw_results.length : 0))); i++) {
          const status = String(pageStatuses[i + 1] || "Pending").toLowerCase();
          pendingMask.push(status === "pending");
        }

        const anyPending = pendingMask.some(Boolean);

        if (anyPending) {
          // Build filtered arrays in the original order
          const filteredAnnotated = annotated.filter((_, idx) => pendingMask[idx]);
          const filteredEnhanced = enhanced.filter((_, idx) => pendingMask[idx]);

          // Filter response data payloads (result.data or result.raw_results)
          const filteredResult = { ...result };
          if (Array.isArray(result.data)) {
            filteredResult.data = result.data.filter((_, idx) => pendingMask[idx]);
          } else if (Array.isArray(result)) {
            // unlikely: keep as-is
          } else if (Array.isArray(result.raw_results)) {
            // some callers expect data under `data` — keep raw_results filtered
            filteredResult.raw_results = result.raw_results.filter((_, idx) => pendingMask[idx]);
          }

          setResponseData(filteredResult);
          setAnnotatedImages(filteredAnnotated);
          setEnhancedImages(filteredEnhanced);
          const enrichedPreview = filteredEnhanced.length > 0
            ? filteredEnhanced[0]
            : filteredAnnotated.length > 0
              ? filteredAnnotated[0]
              : null;
          if (enrichedPreview) {
            setPreviewSrc(enrichedPreview);
            setIsPdf(false);
          }
        }
      } catch (e) {
        console.warn("[handleProcess] failed to filter pending pages:", e);
      }

      if (currentHistoryId) {
        if (autoCompletedIndices.length) {
          setProcessedPages((prev) => {
            const next = new Set(prev);
            autoCompletedIndices.forEach((idx) => next.add(idx));
            return next;
          });
        }

        if (!anyGroupPending) {
          // Every group was auto-extracted -- the job is already
          // "completed" server-side (see process_upload's
          // check_and_update_job_completion call), nothing left to
          // validate.
          setIsJobCompleted(true);
          clearDraft();
          localStorage.removeItem("draftFileName");
          setPopup("File saved to output path. Click OK to continue.");
          setIsProcessing(false);
          return; // EXIT here after auto-extraction success
        }

        // Some groups are still Pending -- open the validation screen
        // directly on the first one (skip whatever was auto-completed).
        const firstPending = groups.find((g) => !isPageAutoCompleted(g[0]));
        setCurrentPage(firstPending ? firstPending[0] : 0);
      }

      setShowMain(true);

      saveDraft({
        previewSrc,
        isPdf,
        showMain: true,
        requestJson: json,
        responseData: result,
        annotatedImages:
          result.annotated_images || [],
        manualValues: {},
        editableTables: tempTables,
        historyId: currentHistoryId,
      });

      setProcessingCompleted(true);

      setIsProcessing(false);

      setActiveTab("preview");

    } catch (error) {
      console.error(error);

      if (reprocessHistoryId) {
        await updateJobStatus(reprocessHistoryId, "failed", 0);
      } else if (historyId) {
        await updateJobStatus(historyId, "failed", 0);
      }

      setIsProcessing(false);
      setPopup("Processing failed.");
    }
  };
  const handleReprocess = () => {

    setProcessingCompleted(false);
    clearDraft();

    if (historyId) {
      updateJobStatus(historyId, "failed", 0).catch(() => { });
    }

    collapseAll();

    // setSelectedFile(null);
    // setPreviewSrc(null);
    // setIsPdf(false);
    setShowMain(false);
    setRequestJson(null);



    if (fileInputRef.current)
      fileInputRef.current.value = "";

    // setTimeout(
    //   () => fileInputRef.current?.click(),
    //   100
    // );

    // automatically process again
    // handleProcess();
    setShowProcessPopup(true);
  };

  const updateTableCell = (
    tableName,
    rowIndex,
    field,
    value
  ) => {
    setEditableTables((prev) => ({
      ...prev,
      [tableName]: prev[tableName].map((row, index) =>
        index === rowIndex
          ? {
            ...row,
            [field]: value
          }
          : row
      )
    }));
  };

  const addTableRow = (tableName) => {
    const tableInfo = tables[tableName];

    const newRow = {};

    tableInfo.fields.forEach((f) => {
      newRow[f.fieldLabel] = "";
    });

    setEditableTables((prev) => ({
      ...prev,
      [tableName]: [
        ...(prev[tableName] || []),
        newRow,
      ],
    }));
  };

  const deleteTableRow = (
    tableName,
    rowIndex
  ) => {
    setEditableTables((prev) => ({
      ...prev,
      [tableName]: prev[tableName].filter(
        (_, i) => i !== rowIndex
      ),
    }));
  };


  const getPagePayload = (data = responseData) => {
    if (!data) return null;
    const pageIndex = Math.max(0, Math.min(currentPage, (Array.isArray(data) ? data.length : Array.isArray(data?.data) ? data.data.length : 1) - 1));
    if (Array.isArray(data)) {
      return data[pageIndex] || null;
    }
    if (Array.isArray(data?.data)) {
      return data.data[pageIndex] || null;
    }
    return data;
  };

  const getFieldExtraction = (field, data = responseData) => {
    const page = getPagePayload(data);
    const extractions = page?.label_extraction || data?.label_extraction || [];

    if (field.aliases?.length) {
      for (const alias of field.aliases) {
        const match = extractions.find(
          (item) =>
            String(item.label_name || "")
              .trim()
              .toLowerCase() ===
            String(alias || "")
              .trim()
              .toLowerCase()
        );

        if (match) return match;
      }
    }

    return extractions.find(
      (item) =>
        String(item.label_name || "")
          .trim()
          .toLowerCase() ===
        String(field.fieldLabel || "")
          .trim()
          .toLowerCase()
    );
  };

  const getMissingCount = ({
    manual = manualValues,
    editable = editableTables,
    response = responseData,
    fields = formFields,
    tablesSource = tables,
  } = {}) => {
    let count = 0;

    fields
      .filter(
        (field) =>
          field.required === "Required" ||
          field.required === true
      )
      .forEach((field) => {
        const value =
          manual[field.fieldLabel] ??
          (getFieldExtraction(field, response)?.value ?? "");

        if (isEmptyValue(value)) {
          count++;
        }
      });

    Object.keys(tablesSource).forEach((tableName) => {
      const tableInfo = tablesSource[tableName];

      if (
        tableInfo.required === false ||
        tableInfo.required === "false"
      ) {
        return;
      }

      const rows = editable[tableName] || [];

      rows.forEach((row, rowIndex) => {
        tableInfo.fields
          .filter(
            (f) =>
              f.required === "Required" ||
              f.required === true
          )
          .forEach((field) => {
            const value =
              manual[
              `${tableName}_${rowIndex}_${field.fieldLabel}`
              ] ??
              row[field.fieldLabel] ??
              row[field.fieldName] ??
              "";

            if (!value || String(value).trim() === "") {
              count++;
            }
          });
      });
    });

    return count;
  };

  const downloadCsv = (csvContent, filename) => {
    // BOM prefix keeps Excel happy with UTF-8 (matches the previous
    // server-side "utf-8-sig" encoding).
    const blob = new Blob(["\uFEFF" + csvContent], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getPageResponseAtIndexFromPayload = (data, pageIndex) => {
    if (!data) return null;
    if (Array.isArray(data)) {
      return data[pageIndex] || data[0] || null;
    }
    if (Array.isArray(data?.data)) {
      return data.data[pageIndex] || data.data[0] || null;
    }
    return data;
  };

  const buildCurrentPageCsv = (payload = responseData, pageIndex = currentPage) => {
    // Build CSV for the CURRENT page only (not all pages)
    const pageResponse = getPageResponseAtIndexFromPayload(payload, pageIndex);
    let csvContent = "";

    // Form Fields
    const formHeaders = [];
    const formValues = [];

    formFields.forEach((field) => {
      formHeaders.push(field.fieldLabel);

      const value =
        manualValues.hasOwnProperty(field.fieldLabel)
          ? manualValues[field.fieldLabel]
          : getFieldValue(field, payload);

      formValues.push(escapeCsvValue(value ?? ""));
    });

    csvContent += formHeaders.map(escapeCsvValue).join(",") + "\n";
    csvContent += formValues.join(",") + "\n\n";

    // Tables
    Object.keys(tables).forEach((tableName) => {
      csvContent += tableName + "\n";

      const tableInfo = tables[tableName];

      const headers = tableInfo.fields.map(
        (f) => f.fieldLabel
      );

      csvContent += headers.map(escapeCsvValue).join(",") + "\n";

      const rows = editableTables[tableName] || [];

      rows.forEach((row, rowIndex) => {
        const rowValues = tableInfo.fields.map((f) => {
          return (
            editableTables?.[tableName]?.[rowIndex]?.[
            f.fieldLabel
            ] || ""
          );
        });

        csvContent += rowValues.map(escapeCsvValue).join(",") + "\n";
      });

      csvContent += "\n";
    });

    return csvContent;
  };

  const updateJobStatus = async (targetHistoryId, nextStatus, nextStp) => {
    if (!targetHistoryId) return;
    try {
      await authFetch(`${API_BASE_URL}/document/history/${encodeURIComponent(targetHistoryId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: nextStatus,
          ...(nextStp !== undefined ? { stp: nextStp } : {}),
        }),
      });
    } catch (error) {
      console.warn("Failed to update job status", error);
    }
  };

  const handleSubmit = async () => {
    if (getMissingCount() > 0) {
      setPopup("Please fill all required fields.");
      return;
    }

    const trimmedOutputPath = (outputPath || "").trim();

    if (!trimmedOutputPath) {
      setPopup("Please enter a valid output folder path.");
      return;
    }

    const targetHistoryId = historyId || reprocessHistoryId;
    if (!targetHistoryId) {
      setPopup("No active history ID found for this document.");
      return;
    }

    // buildCurrentPageCsv() already reflects the WHOLE group's data, not
    // just this one page: the backend runs KV/table extraction once per
    // group and copies the identical result onto every page in that group
    // (see document_service.py's extraction fan-out), so whichever group
    // page is on screen has the full picture. That means one CSV here is
    // enough to represent every page in the group -- we must not build or
    // save a second one per page.
    const csvContent = buildCurrentPageCsv();
    const pageNumber = currentPage + 1; // 1-based
    const displayName = getDocumentDisplayName() || "export";

    // Pages that are grouped by page-stream segmentation (e.g. [1,2]) are
    // submitted together: one CSV named "Page_1,2", and every page in the
    // group flips to Completed in the same call.
    const groupPageIndices = getPageGroupPayload(currentPage);
    const groupPageNumbers = groupPageIndices.map((idx) => idx + 1);

    try {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/document/history/${encodeURIComponent(targetHistoryId)}/pages/${pageNumber}/submit`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            output_folder: trimmedOutputPath,
            csv_content: csvContent,
            input_filename: displayName,
            group_pages: groupPageNumbers,
          }),
        }
      );

      const result = await readJsonResponse(response);

      if (!response.ok) {
        setPopup(result.detail || "Failed to submit page.");
        return;
      }

      // Mark every page in the group as processed (a group of 1 just
      // marks the current page, same as before).
      setProcessedPages((prev) => {
        const next = new Set(prev);
        groupPageIndices.forEach((idx) => next.add(idx));
        return next;
      });

      const wasJobCompleted = result.job_completed === true;

      if (wasJobCompleted) {
        await updateJobStatus(targetHistoryId, "completed", 0);
        setIsJobCompleted(true);
        clearDraft();
        localStorage.removeItem("draftFileName");
        setSuccessPopup(true);
      } else {
        // Auto-advance to the next pending page/group.
        advanceToNextPending(groupPageIndices);

        // Show success and continue
        setPopup("Page submitted successfully. Click OK to continue...");
      }
    } catch (error) {
      console.error(error);
      setPopup("Failed to submit page.");
      return;
    }
  };

  // ── Per-page helpers for mark-as-invalid ─────────────────────────────

  /** Build CSV content for a single page given its response payload.
   *  Returns the CSV string for that page's form fields + tables.
   */
  const buildPageCsv = (pageResponse, pageIndex) => {
    let csvContent = "";

    // Form fields: extract values from this page's response
    const formHeaders = [];
    const formValues = [];

    formFields.forEach((field) => {
      formHeaders.push(field.fieldLabel);

      // Use manual override only if on the currently visible page
      const manualValue =
        pageIndex === currentPage && manualValues.hasOwnProperty(field.fieldLabel)
          ? manualValues[field.fieldLabel]
          : null;

      let value;
      if (manualValue !== null) {
        value = manualValue;
      } else {
        // Look up extraction from this specific page's response
        const extractions = pageResponse?.label_extraction || [];
        let match = null;
        if (field.aliases?.length) {
          for (const alias of field.aliases) {
            match = extractions.find(
              (item) =>
                String(item.label_name || "").trim().toLowerCase() ===
                String(alias || "").trim().toLowerCase()
            );
            if (match) break;
          }
        }
        if (!match) {
          match = extractions.find(
            (item) =>
              String(item.label_name || "").trim().toLowerCase() ===
              String(field.fieldLabel || "").trim().toLowerCase()
          );
        }
        value = match?.value || "";
      }

      formValues.push(escapeCsvValue(value ?? ""));
    });

    csvContent += formHeaders.map(escapeCsvValue).join(",") + "\n";
    csvContent += formValues.join(",") + "\n\n";

    // Tables: get rows from this page's response
    Object.keys(tables).forEach((tableName) => {
      csvContent += tableName + "\n";
      const tableInfo = tables[tableName];
      const headers = tableInfo.fields.map((f) => f.fieldLabel);
      csvContent += headers.map(escapeCsvValue).join(",") + "\n";

      // Extract table rows from this page's header_extraction
      const pageTables = pageResponse?.header_extraction || [];
      const table = pageTables.find(
        (t) => t.table_name?.toLowerCase() === tableName?.toLowerCase()
      );

      let rows = [];
      if (table && table.columns) {
        const columns = table.columns || [];
        const maxRows = Math.max(
          ...columns.map((c) => c.value?.length || 0),
          0
        );
        for (let i = 0; i < maxRows; i++) {
          const row = {};
          columns.forEach((col) => {
            row[col.header_name] = col.value?.[i] || "";
          });
          rows.push(row);
        }
      }

      // Use editable table rows for the current page if available
      if (pageIndex === currentPage && editableTables[tableName]) {
        rows = editableTables[tableName];
      }

      rows.forEach((row) => {
        const rowValues = tableInfo.fields.map((f) => {
          return row[f.fieldLabel] || row[f.fieldName] || "";
        });
        csvContent += rowValues.map(escapeCsvValue).join(",") + "\n";
      });

      csvContent += "\n";
    });

    return csvContent;
  };

  /** Get the total number of pages from response data. */
  const getPageCount = () => {
    // First check pages array (from history)
    if (pages && pages.length > 0) return pages.length;
    // Then check enhancedImages (from process or history)
    if (enhancedImages && enhancedImages.length > 0) return enhancedImages.length;
    // Then check if responseData is an array
    if (Array.isArray(responseData)) return responseData.length;
    if (responseData?.data && Array.isArray(responseData.data)) return responseData.data.length;
    return 1;
  };

  /** Get the response payload for a specific page index. */
  const getPageResponseAtIndex = (pageIndex) => {
    return getPageResponseAtIndexFromPayload(responseData, pageIndex);
  };

  const handleMarkAsInvalid = async () => {
    const targetHistoryId = historyId || reprocessHistoryId;
    if (!targetHistoryId) {
      setPopup("No active history ID found for this document.");
      return;
    }

    const trimmedOutputPath = (outputPath || "").trim();
    const pageNumber = currentPage + 1; // 1-based

    // Pages grouped by page-stream segmentation are invalidated together:
    // one CSV named "Page_1,2_invalid", every page's images copied into
    // the invalid folder, and every page in the group flips to
    // "Marked as Invalid" in the same call.
    const groupPageIndices = getPageGroupPayload(currentPage);
    const groupPageNumbers = groupPageIndices.map((idx) => idx + 1);

    // Build CSV representing the group (see handleSubmit for why the
    // currently-viewed page's response already covers every page in the
    // group -- one CSV, not one per page).
    const pageResponse = getPageResponseAtIndex(currentPage);
    const csvContent = buildPageCsv(pageResponse, currentPage);

    try {
      const response = await authFetch(`${API_BASE_URL}/document/history/${encodeURIComponent(targetHistoryId)}/pages/${pageNumber}/mark-invalid`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          output_folder: trimmedOutputPath,
          csv_content: csvContent,
          input_filename: getDocumentDisplayName() || "document.pdf",
          group_pages: groupPageNumbers,
        }),
      });

      const resData = await response.json();
      if (!response.ok) {
        setPopup(resData.detail || "Failed to mark page as invalid.");
        return;
      }

      // Mark every page in the group as processed (a group of 1 just
      // marks the current page, same as before).
      setProcessedPages((prev) => {
        const next = new Set(prev);
        groupPageIndices.forEach((idx) => next.add(idx));
        return next;
      });

      const wasJobCompleted = resData.job_completed === true;

      if (wasJobCompleted) {
        await updateJobStatus(targetHistoryId, "completed", 0);
        setIsJobCompleted(true);
        clearDraft();
        localStorage.removeItem("draftFileName");
        setSuccessPopup(true);
      } else {
        // Auto-advance to the next pending page/group.
        advanceToNextPending(groupPageIndices);

        setPopup("Page marked as invalid. Click OK to continue...");
      }
    } catch (error) {
      console.error(error);
      setPopup("Error marking page as invalid.");
    }
  };
  const getExtractedField = (field, data = responseData) => {
    const page = getPagePayload(data);
    const extractions = page?.label_extraction || data?.label_extraction || [];

    if (field.aliases?.length) {
      for (const alias of field.aliases) {
        const match = extractions.find(
          (item) =>
            String(item.label_name || "")
              .trim()
              .toLowerCase() ===
            String(alias || "")
              .trim()
              .toLowerCase()
        );

        if (match) return match;
      }
    }

    return extractions.find(
      (item) =>
        String(item.label_name || "")
          .trim()
          .toLowerCase() ===
        String(field.fieldLabel || "")
          .trim()
          .toLowerCase()
    );
  };

  const getFieldValue = (field, data = responseData) => {
    const match = getExtractedField(field, data);
    return match?.value || "";
  };

  const normalizeDraggedDate = (text) => {
    if (!text) return "";

    const match = text.match(
      /(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/
    );

    if (!match) return "";

    let [, month, day, year] = match;

    if (year.length === 2) {
      year = "20" + year;
    }

    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  };

  const formatDateForInput = (text) => {
    if (!text) return "";

    let str = String(text).trim();

    // remove ordinal suffix
    str = str.replace(
      /\b(\d{1,2})(st|nd|rd|th)\b/gi,
      "$1"
    );

    const monthMap = {
      jan: "01", january: "01",
      feb: "02", february: "02",
      mar: "03", march: "03",
      apr: "04", april: "04",
      may: "05",
      jun: "06", june: "06",
      jul: "07", july: "07",
      aug: "08", august: "08",
      sep: "09", sept: "09", september: "09",
      oct: "10", october: "10",
      nov: "11", november: "11",
      dec: "12", december: "12"
    };

    // ISO / RFC3339
    let d = new Date(str);
    if (!isNaN(d)) {
      return d.toISOString().split("T")[0];
    }

    let match;

    // YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    match = str.match(
      /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/
    );
    if (match) {
      return `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
    }

    // DD-MM-YYYY / DD/MM/YYYY / DD.MM.YYYY
    match = str.match(
      /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/
    );
    if (match) {
      return `${match[3]}-${match[2].padStart(2, "0")}-${match[1].padStart(2, "0")}`;
    }

    // DD-MMM-YYYY or DD MMM YYYY
    match = str.match(
      /^(\d{1,2})[- ]([A-Za-z]+)[- ](\d{2,4})$/
    );
    if (match) {
      let year = match[3];
      if (year.length === 2) year = "20" + year;

      const month =
        monthMap[match[2].toLowerCase()];

      if (month)
        return `${year}-${month}-${match[1].padStart(2, "0")}`;
    }

    // MMM DD, YYYY
    match = str.match(
      /^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$/
    );
    if (match) {
      const month =
        monthMap[match[1].toLowerCase()];

      if (month)
        return `${match[3]}-${month}-${match[2].padStart(2, "0")}`;
    }

    // YYYYMMDD
    match = str.match(/^(\d{4})(\d{2})(\d{2})$/);
    if (match) {
      return `${match[1]}-${match[2]}-${match[3]}`;
    }

    // DDMMYYYY
    match = str.match(/^(\d{2})(\d{2})(\d{4})$/);
    if (match) {
      return `${match[3]}-${match[2]}-${match[1]}`;
    }

    return "";
  };

  const getTableRowsFromResponse = (
    response,
    tableName
  ) => {
    const page = getPagePayload(response);
    const tables = page?.header_extraction || response?.header_extraction || [];

    if (!Array.isArray(tables)) return [];

    const table = tables.find(
      (t) =>
        t.table_name?.toLowerCase() ===
        tableName?.toLowerCase()
    );

    if (!table) return [];

    const columns = table.columns || [];
    const maxRows = Math.max(
      ...columns.map((c) => c.value?.length || 0),
      0
    );

    const rows = [];

    for (let i = 0; i < maxRows; i++) {
      const row = {};
      columns.forEach((col) => {
        row[col.header_name] = col.value?.[i] || "";
      });
      rows.push(row);
    }

    return rows;
  };

  const getTableRows = (tableName) => {
    const page = getPagePayload(responseData);
    const tables = page?.header_extraction || responseData?.header_extraction || [];

    if (!Array.isArray(tables)) return [];

    const table = tables.find(
      (t) =>
        t.table_name?.toLowerCase() ===
        tableName?.toLowerCase()
    );

    if (!table) return [];

    const columns = table.columns || [];
    const maxRows = Math.max(
      ...columns.map((c) => c.value?.length || 0),
      0
    );

    const rows = [];

    for (let i = 0; i < maxRows; i++) {
      const row = {};
      columns.forEach((col) => {
        row[col.header_name] = col.value?.[i] || "";
      });
      rows.push(row);
    }

    return rows;
  };

  const isEmptyValue = (value) => {
    return (
      value === null ||
      value === undefined ||
      String(value).trim() === ""
    );
  };

  const getMissingReason = (field, value) => {
    if (isEmptyValue(value)) {
      return "Data missing. Drag and select the value from the document image to populate this field.";
    }

    return "";
  };

  const handleMouseDown = (e) => {

    if (!activeField) {
      alert("Select input field first");
      return;
    }

    const rect =
      imageContainerRef.current.getBoundingClientRect();

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setStartPoint({ x, y });
    setIsSelecting(true);
  };

  const handleMouseMove = (e) => {

    if (!isSelecting) return;

    const rect =
      imageContainerRef.current.getBoundingClientRect();

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setSelectionBox({
      x: Math.min(startPoint.x, x),
      y: Math.min(startPoint.y, y),
      width: Math.abs(x - startPoint.x),
      height: Math.abs(y - startPoint.y)
    });
  };

  const handleMouseUp = () => {

    if (!selectionBox) return;

    setIsSelecting(false);

    // Every page has its own response.json. getPagePayload() resolves the
    // ACTIVE page from currentPage, and works whether responseData is the
    // live process-upload result ({ data: [...] }) or a reprocessed/
    // history response.json loaded straight off disk (a bare [...] array)
    // -- see getPagePayload's two branches above.
    const pagePayload = getPagePayload(responseData);

    const pageOCR =
      pagePayload?.ocr ||
      pagePayload?.ocr_tokens ||
      [];

    // Table-cell-text fallback (used when the OCR tokens above didn't
    // land any text inside the drawn box). Read this from the SAME
    // page's response.json ("tables[].cells"), not from a separate
    // raw_results array -- raw_results is only populated right after a
    // fresh process-upload and is undefined after loading a job from
    // history, which silently broke this fallback on every page after
    // reprocessing/history load.
    const pageTables = pagePayload?.tables || [];
    const pageCellsText = [];

    pageTables.forEach((t) => {
      (t.cells || []).forEach((c) => {
        const coords = c?.coordinates || [];
        if (Array.isArray(coords) && coords.length === 4) {
          // coords from backend may be [x0,y0,x1,y1]
          pageCellsText.push({
            coordinates: coords,
            text: c?.text || "",
          });
        }
      });
    });

    const img =
      imageContainerRef.current.querySelector("img");

    // Guard: if the image hasn't finished loading yet (naturalWidth/
    // clientWidth are 0), bail out instead of dividing by zero and
    // producing NaN/Infinity coordinates that silently break selection.
    if (!img || !img.naturalWidth || !img.clientWidth || !img.naturalHeight || !img.clientHeight) {
      setSelectionBox(null);
      return;
    }

    const scaleX = img.naturalWidth / img.clientWidth;
    const scaleY = img.naturalHeight / img.clientHeight;

    const selectedTexts = [];

    pageOCR.forEach((item) => {
      // OCR in response.json uses coordinates: [x1, y1, x2, y2]
      // (not docling poly points). raw_results may also use same.
      const coords = item?.coordinates || [];

      let left, right, top, bottom;

      if (Array.isArray(coords) && coords.length === 4 && typeof coords[0] === "number") {
        left = coords[0] / scaleX;
        top = coords[1] / scaleY;
        right = coords[2] / scaleX;
        bottom = coords[3] / scaleY;
      } else {
        // Old/alternate shape: points like [[x,y],...]
        const points = coords || [];
        if (!points.length) return;
        const xs = points.map((p) => p[0]);
        const ys = points.map((p) => p[1]);
        left = Math.min(...xs) / scaleX;
        right = Math.max(...xs) / scaleX;
        top = Math.min(...ys) / scaleY;
        bottom = Math.max(...ys) / scaleY;
      }

      const inside =
        left < selectionBox.x + selectionBox.width &&
        right > selectionBox.x &&
        top < selectionBox.y + selectionBox.height &&
        bottom > selectionBox.y;

      if (inside) {
        selectedTexts.push(item?.text || "");
      }
    });

    const extractedTextInitial = selectedTexts.filter(Boolean).join(" ");

    // If OCR tokens had no text, fallback to any table/cell text inside the selection
    let extractedText = extractedTextInitial;

    if (!extractedText || !extractedText.trim()) {
      const selectedCellTexts = [];

      pageCellsText.forEach((item) => {
        const coords = item?.coordinates || [];
        if (!Array.isArray(coords) || coords.length !== 4) return;

        const left = coords[0] / scaleX;
        const top = coords[1] / scaleY;
        const right = coords[2] / scaleX;
        const bottom = coords[3] / scaleY;

        const inside =
          left < selectionBox.x + selectionBox.width &&
          right > selectionBox.x &&
          top < selectionBox.y + selectionBox.height &&
          bottom > selectionBox.y;

        if (inside && item.text) selectedCellTexts.push(item.text);
      });

      extractedText = selectedCellTexts.join(" ").trim();
    }



    // FORM FIELD
    if (activeField?.type === "form") {

      const fieldInfo = formFields.find(
        (f) => f.fieldLabel === activeField.field
      );

      const cleanText = extractedText.trim();

      const finalValue =
        fieldInfo?.datatype?.toLowerCase() === "date"
          ? formatDateForInput(cleanText)
          : cleanText;

      setManualValues((prev) => ({
        ...prev,
        [activeField.field]: finalValue
      }));
    }

    // TABLE FIELD
    if (activeField?.type === "table") {

      const tableInfo = tables[activeField.tableName];

      const fieldInfo = tableInfo?.fields?.find(
        (f) => f.fieldLabel === activeField.field
      );

      const cleanText = extractedText.trim();

      const finalValue =
        fieldInfo?.datatype?.toLowerCase() === "date"
          ? formatDateForInput(cleanText)
          : cleanText;



      updateTableCell(
        activeField.tableName,
        activeField.rowIndex,
        activeField.field,
        finalValue
      );
    }

    setSelectionBox(null);
  };

  const addRow = (tableName, fields) => {

    const newRow = {};

    fields.forEach((f) => {
      newRow[f.fieldLabel] = "";
    });

    setTableData((prev) => ({
      ...prev,
      [tableName]: [
        ...(prev[tableName] || []),
        newRow,
      ],
    }));
  };

  // Resizer
  useEffect(() => {


    const resizer = resizerRef.current;
    const left = viewerRef.current;
    const right = validationRef.current;
    if (!resizer || !left || !right) return;
    let isResizing = false;
    const onMouseDown = () => { isResizing = true; document.body.style.cursor = "col-resize"; };
    const onMouseMove = (e) => {
      if (!isResizing) return;
      const container = resizer.parentElement;
      const rect = container.getBoundingClientRect();
      let leftW = e.clientX - rect.left;
      leftW = Math.max(300, Math.min(leftW, rect.width - 300 - resizer.offsetWidth));
      left.style.width = leftW + "px";
      right.style.width = (rect.width - leftW - resizer.offsetWidth) + "px";
    };
    const onMouseUp = () => { isResizing = false; document.body.style.cursor = "default"; };
    resizer.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      resizer.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, [showMain]);

  return (
    <div className="process-doc-wrapper">
      {/* ── Top bar ── */}
      <div className="process-topbar">
        <h2>
          {currentModel?.name
            ? `${currentModel.name} - Document Processing`
            : "Document Processing"}
        </h2>
        <div className="upload-section">
          <input
            type="file"
            ref={fileInputRef}
            className="dp-visually-hidden-input"
            onChange={handleFileChange}
            accept="application/pdf,image/*"
          />
          <span className="file-name-display">{selectedFile ? selectedFile.name : "No file selected"}</span>
          <div className="browse-tooltip-wrapper">
            <button
              className="browse-btn"
              disabled={processingCompleted}
              onClick={() => fileInputRef.current.click()}
            >
              📁 Choose Document
            </button>

            <div className="browse-tooltip">
              PDF, JPG, JPEG, PNG, TIFF, or BMP -- uploaded to the server and deleted automatically once processing finishes
            </div>
          </div>
          <div className="output-folder-row">
            <label className="output-folder-label" htmlFor="output-path-input">
              Output Folder
            </label>
            <input
              id="output-path-input"
              type="text"
              value={outputPath}
              readOnly
              placeholder="e.g. C:\\Exports or /home/user/exports"
              className="output-folder-input output-folder-input-readonly"
            />
          </div>
          <button
            className="proc-btn"
            onClick={() => setShowProcessPopup(true)}
            disabled={
              processingCompleted ||
              isProcessing ||
              !selectedFile
            }
          >
            {isProcessing
              ? "Processing..."
              : autoReprocess
                ? "▶ Resume Processing"
                : "▶ Process"}
          </button>
        </div>
      </div>

      {/* ── Main area ── */}
      {showMain && (
        <div className="process-main-container">
          {/* LEFT – document viewer */}
          <div className="viewer-panel" ref={viewerRef}>
            <div className="document-preview">
              <div className="preview-header">
                <h3>{getDocumentDisplayName() || "No File Selected"}</h3>
                {/* Tab switcher */}
                <div className="tab-switcher">

                  {(activeTab === "preview" || activeTab === "output") && (
                    <div className="zoom-controls">
                      <button
                        type="button"
                        className="zoom-btn"
                        onClick={() =>
                          setImageZoom((prev) => Math.max(25, prev - 25))
                        }
                      >
                        −
                      </button>

                      <span className="zoom-percentage">
                        {imageZoom}%
                      </span>

                      <button
                        type="button"
                        className="zoom-btn"
                        onClick={() =>
                          setImageZoom((prev) => Math.min(300, prev + 25))
                        }
                      >
                        +
                      </button>
                    </div>
                  )}

                  <button
                    className={`tab-btn ${activeTab === "preview" ? "tab-active" : ""}`}
                    onClick={() => setActiveTab("preview")}
                  >
                    Original Document
                  </button>

                  <button
                    className={`tab-btn ${activeTab === "output" ? "tab-active" : ""
                      }`}
                    onClick={() => setActiveTab("output")}
                  >
                    Extraction Results
                  </button>

                </div>
              </div>

              {activeTab === "preview" ? (

                enhancedImages.length > 0 ? (

                  <div className="annotated-tab-content">
                    <div className="page-nav-row">

                      <button className="tab-btn" onClick={prevPage} disabled={currentPage <= 0}>
                        Previous
                      </button>
                      <div className="page-counter">Page {currentPage + 1} / {getPreviewPageCount()}</div>
                      <button className="tab-btn" onClick={nextPage} disabled={currentPage >= getPreviewPageCount() - 1}>
                        Next
                      </button>
                    </div>

                    <div className="image-scroll-box">
                      <div
                        ref={imageContainerRef}
                        className="image-container"
                      >
                        <img
                          src={getCurrentPreviewUrl()}
                          className="document-image dp-zoomable-image"
                          alt="Document preview"
                          style={{ width: `${imageZoom}%` }}
                        />

                        {selectionBox && (
                          <div
                            className="dp-selection-box"
                            style={{
                              left: selectionBox.x,
                              top: selectionBox.y,
                              width: selectionBox.width,
                              height: selectionBox.height,
                            }}
                          />
                        )}
                      </div>
                    </div>
                  </div>

                ) : isPdf && previewSrc ? (

                  <iframe
                    src={previewSrc}
                    className="pdf-iframe"
                    title="PDF Preview"
                  />

                ) : previewSrc ? (

                  <img
                    src={previewSrc}
                    className="document-image"
                    alt="Document preview"
                  />

                ) : (

                  <div className="empty-state">
                    No preview available
                  </div>

                )

              ) : activeTab === "json" ? (

                <div className="json-viewer">
                  <div className="json-viewer-header">
                    <span className="json-badge">
                      request/request.json
                    </span>

                    <button
                      className="json-copy-btn"
                      onClick={() =>
                        navigator.clipboard.writeText(
                          JSON.stringify(requestJson, null, 2)
                        )
                      }
                    >
                      📋 Copy
                    </button>
                  </div>

                  <pre className="json-content">
                    {JSON.stringify(requestJson, null, 2)}
                  </pre>
                </div>

              ) : (

                /* ── Extraction Results tab ──
                   Same flex column wrapper as "Original Document" tab so
                   .image-scroll-box gets a real bounded height to overflow
                   against -- its flex:1/min-height:0 only take effect when
                   it is a direct flex item of a flex-column parent.
                   Drag-to-select (onMouseDown/Move/Up) is intentionally
                   ONLY wired up here -- not on the Original Document tab. */
                <div className="annotated-tab-content">

                  {getPreviewPageCount() > 0 ? (

                    <>
                      {/* Zoom Controls + Page Navigation */}
                      <div className="page-nav-row">
                        <button className="tab-btn" onClick={prevPage} disabled={currentPage <= 0}>
                          Previous
                        </button>
                        <div className="page-counter">Page {currentPage + 1} / {getPreviewPageCount()}</div>
                        <button className="tab-btn" onClick={nextPage} disabled={currentPage >= getPreviewPageCount() - 1}>
                          Next
                        </button>
                      </div>

                      <div className="image-scroll-box">
                        <div
                          ref={imageContainerRef}
                          className="image-container"
                          onMouseDown={handleMouseDown}
                          onMouseMove={handleMouseMove}
                          onMouseUp={handleMouseUp}
                        >
                          <img
                            src={
                              annotatedImages?.length > 0
                                ? annotatedImages[
                                Math.min(
                                  currentPage,
                                  annotatedImages.length - 1
                                )
                                ]
                                : null
                            }
                            className="document-image dp-zoomable-image"
                            alt="Output"
                            style={{ width: `${imageZoom}%` }}
                            onError={() => {}}
                          />

                          {selectionBox && (
                            <div
                              className="dp-selection-box"
                              style={{
                                left: selectionBox.x,
                                top: selectionBox.y,
                                width: selectionBox.width,
                                height: selectionBox.height,
                              }}
                            />
                          )}
                        </div>
                      </div>

                    </>

                  ) : (
                    <div className="empty-state">
                      No output image available
                    </div>

                  )}

                </div>

              )}

            </div>
          </div>

          <div className="panel-resizer" ref={resizerRef} />

          {/* RIGHT – validation panel */}
          <div className="validation-panel" ref={validationRef}>
            <div className="validation-header">

              {getMissingCount() > 0 && (
                <h3>{getMissingCount()} Fields to Validate</h3>
              )}

              <div className="validation-filters-row">
                {/* Existing Filter */}
                <select
                  className="filter-box"
                  value={fieldFilter}
                  onChange={(e) => setFieldFilter(e.target.value)}
                >
                  <option value="all">All Fields</option>
                  <option value="required">Required fields</option>
                  <option value="invalid">Invalid fields</option>
                </select>

                {/* Form/Table Filter */}
                <select
                  className="filter-box"
                  value={sectionFilter}
                  onChange={(e) => setSectionFilter(e.target.value)}
                >
                  <option value="all">All Sections</option>
                  <option value="form">Form Only</option>
                  <option value="table">Table Only</option>
                </select>
              </div>

            </div>

            <div className="fields-section">

              {(sectionFilter === "all" || sectionFilter === "form") && (
                <div className="proc-section-card">
                  <div className="proc-section-title">Form Fields</div>

                  {formFields
                    .filter((field) => {

                      const value =
                        manualValues[field.fieldLabel] ??
                        getFieldValue(field);

                      if (fieldFilter === "required") {
                        return (
                          field.required === "Required" ||
                          field.required === true
                        );
                      }

                      if (fieldFilter === "invalid") {
                        return isEmptyValue(value);
                      }

                      return true;
                    })
                    .map((field, i) => (
                      <div className="field-row" key={i}>
                        <div className="field-label-text">
                          {field.fieldLabel}

                          {(
                            field.required === "Required" ||
                            field.required === true
                          ) &&
                            isEmptyValue(
                              manualValues[field.fieldLabel] ??
                              getFieldValue(field)
                            ) && (
                              <button
                                type="button"
                                className="info-btn"
                                onClick={() =>
                                  setReasonPopup({
                                    field: field.fieldLabel,
                                    reason:
                                      "Data missing. Drag and select the value from the document image to populate this field."
                                  })
                                }
                              >
                                i
                              </button>
                            )}
                        </div>
                        <div className="field-value">
                          <input
                            type={
                              field.datatype?.toLowerCase() === "number"
                                ? "number"
                                : field.datatype?.toLowerCase() === "date"
                                  ? "date"
                                  : "text"
                            }
                            onFocus={() =>
                              setActiveField({
                                type: "form",
                                field: field.fieldLabel
                              })
                            }
                            value={
                              field.datatype?.toLowerCase() === "date"
                                ? formatDateForInput(
                                  manualValues[field.fieldLabel] ??
                                  getFieldValue(field)
                                )
                                : (
                                  manualValues[field.fieldLabel] ??
                                  getFieldValue(field)
                                )
                            }
                            className={
                              invalidFields.includes(field.fieldLabel) ||
                                (
                                  (
                                    field.required === "Required" ||
                                    field.required === true
                                  ) &&
                                  isEmptyValue(
                                    manualValues[field.fieldLabel] ??
                                    getFieldValue(field)
                                  )
                                )
                                ? "dp-input-invalid"
                                : ""
                            }
                            onChange={(e) => {
                              const val = e.target.value;

                              setManualValues((prev) => ({
                                ...prev,
                                [field.fieldLabel]: val
                              }));
                            }}
                            onClick={() =>
                              setSelectedField(
                                field.fieldLabel
                              )
                            }
                          />

                          {showReason[field.fieldLabel] && (
                            <div className="field-reason-text">
                              {getMissingReason(
                                field,
                                manualValues[field.fieldLabel] ??
                                getFieldValue(field)
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                  {formFields.length === 0 && (
                    <div className="no-fields-text">No form fields.</div>
                  )}
                </div>
              )}
              {(sectionFilter === "all" || sectionFilter === "table") &&
                Object.keys(tables)
                  .filter((name) => {
                    const t = tables[name];
                    return t.required !== false && t.required !== "false";
                  })
                  .map((tableName) => {
                    const tableInfo = tables[tableName];

                    const filteredRows = (editableTables[tableName] || []).filter(
                      (row) => {

                        if (fieldFilter === "all")
                          return true;

                        if (fieldFilter === "required")
                          return true;

                        if (fieldFilter === "invalid") {

                          return tableInfo.fields.some(
                            (f) =>
                              isEmptyValue(row[f.fieldLabel]) ||
                              invalidFields.includes(
                                `${tableName}_${(editableTables[tableName] || []).indexOf(row)}_${f.fieldLabel}`
                              )
                          );
                        }

                        return true;
                      }
                    );


                    return (

                      <div className="proc-section-card" key={tableName}>
                        <div className="proc-section-title">{tableName}</div>
                        <div className="table-wrapper">
                          <table>
                            <thead>
                              <tr>
                                {tableInfo.fields
                                  .filter((f) => {

                                    if (fieldFilter === "required") {
                                      return (
                                        f.required === "Required" ||
                                        f.required === true
                                      );
                                    }

                                    if (fieldFilter === "invalid") {

                                      const rows = editableTables[tableName] || [];

                                      return rows.some(
                                        row =>
                                          isEmptyValue(
                                            row[f.fieldLabel]
                                          )
                                      );
                                    }

                                    return true;
                                  })
                                  .map((f) => (
                                    <th key={f.fieldName}>
                                      {f.fieldLabel}
                                    </th>
                                  ))}

                                <th>Action</th>
                              </tr>
                            </thead>
                            <tbody>

                              {filteredRows.length > 0 ? (
                                filteredRows.map(
                                  (row, rowIndex) => (
                                    <tr key={rowIndex}>
                                      {tableInfo.fields
                                        .filter((f) => {

                                          if (fieldFilter === "required") {
                                            return (
                                              f.required === "Required" ||
                                              f.required === true
                                            );
                                          }

                                          if (fieldFilter === "invalid") {
                                            return isEmptyValue(
                                              editableTables?.[tableName]?.[rowIndex]?.[
                                              f.fieldLabel
                                              ]
                                            );
                                          }

                                          return true;
                                        })
                                        .map((f) => {

                                          const value =
                                            row[f.fieldLabel] ||
                                            row[f.fieldName] ||
                                            "";



                                          return (
                                            <td key={f.fieldName}>
                                              <div className="table-cell-flex">
                                                <input
                                                  type={
                                                    f.datatype?.toLowerCase() === "number"
                                                      ? "number"
                                                      : f.datatype?.toLowerCase() === "date"
                                                        ? "date"
                                                        : "text"
                                                  }
                                                  onFocus={() =>
                                                    setActiveField({
                                                      type: "table",
                                                      tableName,
                                                      rowIndex,
                                                      field: f.fieldLabel
                                                    })
                                                  }
                                                  value={
                                                    f.datatype?.toLowerCase() === "date"
                                                      ? formatDateForInput(
                                                        editableTables?.[tableName]?.[rowIndex]?.[
                                                        f.fieldLabel
                                                        ] || ""
                                                      )
                                                      : (
                                                        editableTables?.[tableName]?.[rowIndex]?.[
                                                        f.fieldLabel
                                                        ] || ""
                                                      )
                                                  }
                                                  className={
                                                    invalidFields.includes(
                                                      `${tableName}_${rowIndex}_${f.fieldLabel}`
                                                    ) ||
                                                      (
                                                        (
                                                          f.required === "Required" ||
                                                          f.required === true
                                                        ) &&
                                                        isEmptyValue(
                                                          editableTables?.[tableName]?.[rowIndex]?.[
                                                          f.fieldLabel
                                                          ]
                                                        )
                                                      )
                                                      ? "dp-table-cell-input dp-input-invalid"
                                                      : "dp-table-cell-input"
                                                  }
                                                  onChange={(e) => {
                                                    const val = e.target.value;

                                                    if (
                                                      f.datatype === "Number" &&
                                                      val !== "" &&
                                                      isNaN(val)
                                                    ) {
                                                      return;
                                                    }

                                                    updateTableCell(
                                                      tableName,
                                                      rowIndex,
                                                      f.fieldLabel,
                                                      val
                                                    );
                                                  }}
                                                  onClick={() =>
                                                    setSelectedField(
                                                      `${tableName}_${rowIndex}_${f.fieldLabel}`
                                                    )
                                                  }
                                                />

                                                {(
                                                  f.required === "Required" ||
                                                  f.required === true
                                                ) &&
                                                  isEmptyValue(
                                                    editableTables?.[tableName]?.[rowIndex]?.[
                                                    f.fieldLabel
                                                    ]
                                                  ) && (
                                                    <button
                                                      type="button"
                                                      className="info-btn"
                                                      onClick={() =>
                                                        setReasonPopup({
                                                          field: f.fieldLabel,
                                                          reason:
                                                            "Data missing. Click inside this field and drag-select the value from the document image. You can also enter the value manually."
                                                        })
                                                      }
                                                    >
                                                      i
                                                    </button>
                                                  )}
                                              </div>
                                            </td>

                                          );
                                        })}

                                      <td>
                                        {(fieldFilter === "all" ||

                                          (fieldFilter === "required" &&
                                            tableInfo.fields.some(
                                              f =>
                                                f.required === "Required" ||
                                                f.required === true
                                            )) ||

                                          (fieldFilter === "invalid" &&
                                            tableInfo.fields.some(
                                              f =>
                                                isEmptyValue(
                                                  editableTables?.[tableName]?.[
                                                  rowIndex
                                                  ]?.[f.fieldLabel]
                                                ) ||
                                                invalidFields.includes(
                                                  `${tableName}_${rowIndex}_${f.fieldLabel}`
                                                )
                                            ))
                                        ) && (

                                            <button
                                              type="button"
                                              className="delete-btn"
                                              onClick={() =>
                                                deleteTableRow(
                                                  tableName,
                                                  rowIndex
                                                )
                                              }
                                            >
                                              🗑
                                            </button>

                                          )}
                                      </td>

                                    </tr>
                                  ))
                              ) : (
                                <tr>
                                  <td colSpan={tableInfo.fields.length + 1}>
                                    No rows available. Click "Add Row".
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                          <div className="add-row-wrapper">
                            <button
                              type="button"
                              className="add-row-btn"
                              onClick={() => addTableRow(tableName)}
                            >
                              + Add Row
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
            </div>

            <div className="proc-footer-actions">
              <div className="proc-action-group">
                {/* <button className="proc-btn-outline" onClick={handleReprocess}>Reprocess</button> */}
                <button
                  className="proc-btn-danger"
                  onClick={handleMarkAsInvalid}
                >
                  Mark as Invalid
                </button>
              </div>
              <button
                className="proc-btn-primary"
                onClick={handleSubmit}
                disabled={getMissingCount() > 0}

              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}

      {isProcessing && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">
            <div className="proc-spinner" />
            <h3>Processing Document</h3>
            <p>Please wait while the document is being processed...</p>
          </div>
        </div>
      )}

      {reasonPopup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box reason-popup">
            <h3>Missing Data</h3>

            <p className="reason-text">
              {reasonPopup.reason}
            </p>

            <button
              className="proc-popup-btn"
              onClick={() =>
                setReasonPopup(null)
              }
            >
              Close
            </button>
          </div>
        </div>
      )}

      {showProcessPopup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">

            <h3>Start Processing</h3>

            <p>
              Do you want to start document processing?
            </p>

            <div className="popup-actions-row">
              <button
                className="proc-popup-btn"
                onClick={confirmProcess}
              >
                Process
              </button>

              <button
                className="proc-btn-danger"
                onClick={() =>
                  setShowProcessPopup(false)
                }
              >
                Cancel
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Popup */}
      {popup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">
            <div className="proc-popup-icon">
              {popup.includes("saved") || popup.includes("successfully") ? "✅" : "⚠️"}
            </div>
            <h3>
              {popup.includes("saved") || popup.includes("successfully") ? "Success" : "Validation Error"}
            </h3>
            <p>{popup}</p>
            <button
              className="proc-popup-btn"
              onClick={() => {
                setPopup(null);
                // "Click OK to continue..." messages only ever appear
                // right after Submit/Mark-as-Invalid when the document
                // still has other pending pages/groups left (the fully-
                // done case uses the dedicated successPopup/
                // invalidSuccessPopup below instead) -- so just close
                // the popup and let the user keep validating the next
                // page we already advanced to, instead of bouncing them
                // back to the extraction-model picker.
                if (popup && popup.includes("Click OK to continue...")) {
                  return;
                }
                clearDraft();
                localStorage.removeItem("draftFileName");
                navigate(`${docBase}/document-process-model`);
              }}
            >
              OK
            </button>
          </div>
        </div>
      )}

      {successPopup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">

            <div className="proc-popup-icon">
              ✅
            </div>

            <h3>Job Completed</h3>

            <p>
              All pages have been processed successfully.
            </p>

            <button
              className="proc-popup-btn"
              onClick={() => {

                setSuccessPopup(false);

                navigate(
                  `${docBase}/document-process-model`
                );

              }}
            >
              OK
            </button>

          </div>
        </div>
      )}

      {invalidSuccessPopup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">
            <div className="proc-popup-icon">ℹ️</div>
            <h3>Marked as Invalid</h3>
            <p>The last page has been marked as invalid. Redirecting to models page.</p>
            <button
              className="proc-popup-btn"
              onClick={() => {
                setInvalidSuccessPopup(false);
                navigate(
                  `${docBase}/document-process-model`
                );
              }}
            >
              OK
            </button>
          </div>
        </div>
      )}

      {/* ── Reprocess popup (for client-disconnect failed jobs) ── */}
      {reprocessPopup && (
        <div className="proc-popup-overlay">
          <div className="proc-popup-box">
            <div className="proc-popup-icon">ℹ️</div>
            <h3>Reprocess Required</h3>
            <p>
              This job was interrupted due to a client disconnect. Please select the
              original file and reprocess the document using the previously selected model:
              <strong> {reprocessPopup.modelName}</strong>.
            </p>
            <div className="popup-actions-row">
              <button
                className="proc-popup-btn"
                onClick={() => {
                  setReprocessPopup(null);
                  // Close the popup — user can select a file and click Process
                }}
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default ProcessDocument;