import React, { useState, useEffect, useMemo } from "react";
import Header from "./components/Header";
import Modal from "./components/Modal";
import {
  getLogConfig,
  saveLogConfig,
  resetLogConfig,
  getUploadConfig,
  saveUploadConfig,
  resetUploadConfig,
  getLlmConfig,
  saveLlmConfig,
  resetLlmConfig,
  refreshLlmModels,
} from "../../../config/businessMapApi";
import "../Styles/settings.css";
import "../Styles/bm-common.css";

// Predefined default values (mirror the backend defaults).
const DEFAULT_VALUES = {
  loggingPath: "D:\\OneNextGen\\Logs",
  loggingType: "Debug",
  maxMB: "50",
  isEnabled: true,
  maxUploadMb: "500",
  maxAudioUploadMb: "50",
  llmMode: "default",
  llmProvider: "openrouter",
  llmModel: "",
};

// Must match LLM_PROVIDER_BASE_URLS in the backend (job_manager.py).
const LLM_PROVIDERS = [
  { id: "openai", label: "ChatGPT / OpenAI" },
  { id: "anthropic", label: "Claude / Anthropic" },
  { id: "gemini", label: "Google Gemini" },
  { id: "openrouter", label: "OpenRouter" },
  { id: "groq", label: "Groq" },
  { id: "mistral", label: "Mistral" },
  { id: "deepseek", label: "DeepSeek" },
  { id: "xai", label: "xAI (Grok)" },
];

/**
 * Text to show for a failed request. The backend reports problems as
 * { detail: "text" } or, for validation errors, { detail: [{ msg }, ...] }.
 * Falls back to err.message and then to the page's generic text.
 */
function backendErrorText(err, fallback) {
  const detail = err && err.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (typeof d === "string" ? d : d && (d.msg || d.message)))
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return (err && err.message) || fallback;
}

function Settings() {
  // ── Single consolidated form state for the entire page ──
  const [formData, setFormData] = useState({
    loggingPath: DEFAULT_VALUES.loggingPath,
    loggingType: DEFAULT_VALUES.loggingType,
    maxMB: DEFAULT_VALUES.maxMB,
    isEnabled: DEFAULT_VALUES.isEnabled,
    maxUploadMb: DEFAULT_VALUES.maxUploadMb,
    maxAudioUploadMb: DEFAULT_VALUES.maxAudioUploadMb,
    // LLM Configuration — mode is "default" or "custom". The key fields
    // themselves are NOT part of formData: they always start blank (see
    // llmPrimaryKey below) since the server never sends
    // back the real key value, only a masked preview to show as a
    // placeholder. Typing a new value is the only way to change a key.
    llmMode: DEFAULT_VALUES.llmMode,
    llmProvider: DEFAULT_VALUES.llmProvider,
    llmModel: DEFAULT_VALUES.llmModel,
  });

  // ── LLM Configuration — kept separate from formData/originalData's
  // simple string-diff dirty-tracking because these fields don't round-trip
  // the same way (server never echoes the real key back). Secondary API Key
  // is intentionally not part of the UI — only Primary is collected/edited
  // here (see api.js/database.py for the still-supported secondary field,
  // kept for backward compatibility but unused by this page). ──
  const [llmPrimaryKey, setLlmPrimaryKey] = useState("");
  const [llmPrimaryConfigured, setLlmPrimaryConfigured] = useState(false);
  const [llmPrimaryMasked, setLlmPrimaryMasked] = useState("");
  const [llmEncryptionAvailable, setLlmEncryptionAvailable] = useState(true);
  const [deletingLlmKey, setDeletingLlmKey] = useState(false);
  const [llmModels, setLlmModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Snapshot of the values as loaded from the backend — used to
  // determine which fields have actually been modified.
  const [originalData, setOriginalData] = useState(null);

  const [editPath, setEditPath] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  // {type: "success" | "error" | "warning", text: string}
  const [statusMessage, setStatusMessage] = useState(null);

  // Load both configurations on mount.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [logData, uploadData, llmData] = await Promise.all([
          getLogConfig(),
          getUploadConfig(),
          getLlmConfig(),
        ]);
        if (cancelled) return;

        const loaded = {
          loggingPath: logData.folder_path || DEFAULT_VALUES.loggingPath,
          loggingType: toTitleCase(logData.level) || DEFAULT_VALUES.loggingType,
          maxMB: String(logData.max_size_mb ?? DEFAULT_VALUES.maxMB),
          isEnabled: logData.enabled !== undefined ? logData.enabled : true,
          maxUploadMb: String(
            uploadData.max_upload_size_mb ?? DEFAULT_VALUES.maxUploadMb
          ),
          maxAudioUploadMb: String(
            uploadData.max_audio_upload_size_mb ?? DEFAULT_VALUES.maxAudioUploadMb
          ),
          llmMode: llmData.mode || DEFAULT_VALUES.llmMode,
          llmProvider: llmData.provider || DEFAULT_VALUES.llmProvider,
          llmModel: llmData.model || "",
        };

        setFormData(loaded);
        setOriginalData(loaded);

        setLlmPrimaryConfigured(!!llmData.primary_key_configured);
        setLlmPrimaryMasked(llmData.primary_key_masked || "");
        setLlmEncryptionAvailable(llmData.encryption_available !== false);

        if (logData.warning) {
          setStatusMessage({ type: "warning", text: logData.warning });
        }
      } catch (err) {
        if (!cancelled) {
          setStatusMessage({
            type: "error",
            text: backendErrorText(err, "Could not load settings from the server."),
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ── Dirty tracking: any field differs from the loaded snapshot? ──
  const hasChanges = useMemo(() => {
    if (!originalData) return false;
    const fieldsChanged = Object.keys(formData).some(
      (key) => String(formData[key]) !== String(originalData[key])
    );
    return fieldsChanged || llmPrimaryKey.trim() !== "";
  }, [formData, originalData, llmPrimaryKey]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const nextValue = type === "checkbox" ? checked : value;

    setFormData((prev) => ({ ...prev, [name]: nextValue }));

    setErrors((prev) => ({ ...prev, [name]: "" }));

    if (name === "loggingType") {
      if (value === "Debug" || value === "Error") {
        setFormData((prev) => ({ ...prev, isEnabled: true }));
      }
    }
  };

  // Loads the model list for the selected provider (uses the typed key,
  // or the already-saved key when the field is left blank).
  const handleRefreshModels = async () => {
    setLoadingModels(true);
    setStatusMessage(null);
    try {
      const models = await refreshLlmModels({
        provider: formData.llmProvider,
        apiKey: llmPrimaryKey,
      });
      const ids = models.map((m) => (typeof m === "string" ? m : m.id || m.name)).filter(Boolean);
      setLlmModels(ids);
      if (ids.length && !ids.includes(formData.llmModel)) {
        setFormData((prev) => ({ ...prev, llmModel: ids[0] }));
      }
      setStatusMessage({ type: "success", text: `Loaded ${ids.length} models.` });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: backendErrorText(err, "Could not load models. Check the provider and API key."),
      });
    } finally {
      setLoadingModels(false);
    }
  };

  // Deletes the saved Primary API Key immediately (not part of the page's
  // normal Save flow — this takes effect right away, same as the request
  // itself instructed: "no need [for Show], instead keep Delete"). Falls
  // back to Default Application API Key since custom mode requires a
  // primary key.
  const handleDeleteLlmKey = async () => {
    if (!llmPrimaryConfigured && !llmPrimaryKey.trim()) return;
    if (!window.confirm("Delete the saved Primary API Key? This cannot be undone.")) {
      return;
    }
    setDeletingLlmKey(true);
    try {
      const data = await saveLlmConfig({ mode: "default", primaryApiKey: "" });
      setLlmPrimaryConfigured(!!data.primary_key_configured);
      setLlmPrimaryMasked(data.primary_key_masked || "");
      setLlmPrimaryKey("");
      setFormData((prev) => ({ ...prev, llmMode: data.mode }));
      setOriginalData((prev) => (prev ? { ...prev, llmMode: data.mode } : prev));
      setStatusMessage({ type: "success", text: "Primary API Key deleted." });
    } catch (err) {
      setStatusMessage({ type: "error", text: backendErrorText(err, "Failed to delete the API key.") });
    } finally {
      setDeletingLlmKey(false);
    }
  };

  const validateUploadValue = (value) => {
    const num = Number(value);
    if (!String(value).trim() || isNaN(num)) {
      return "Please enter a valid number.";
    }
    if (num > 500 || num < 1) {
      return "Maximum upload file size cannot exceed 500 MB. Please enter a value between 1 MB and 500 MB.";
    }
    return null;
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.loggingPath.trim()) {
      newErrors.loggingPath = "Logging Path is required.";
    }

    if (!formData.loggingType) {
      newErrors.loggingType = "Please select Logging Type.";
    }

    if (!formData.maxMB.trim()) {
      newErrors.maxMB = "Max MB is required.";
    } else if (isNaN(formData.maxMB) || Number(formData.maxMB) <= 0) {
      newErrors.maxMB = "Enter a valid number.";
    }

    const videoErr = validateUploadValue(formData.maxUploadMb);
    if (videoErr) newErrors.maxUploadMb = videoErr;

    const audioErr = validateUploadValue(formData.maxAudioUploadMb);
    if (audioErr) newErrors.maxAudioUploadMb = audioErr;

    if (formData.llmMode === "custom") {
      if (!llmEncryptionAvailable) {
        newErrors.llmMode =
          "Custom API keys aren't available right now. Please contact your administrator.";
      } else if (!llmPrimaryConfigured && !llmPrimaryKey.trim()) {
        newErrors.llmPrimaryKey = "API key is required.";
      }
      if (!formData.llmModel) {
        newErrors.llmModel = "Select a model (click Refresh to load the list).";
      }
    }

    setErrors(newErrors);

    return Object.keys(newErrors).length === 0;
  };

  // ── Single Save: validate everything, then save only modified sections ──
  const handleSave = async () => {
    if (!validate()) return;

    setSaving(true);
    setStatusMessage(null);

    const nextFormData = { ...formData };
    let warning = null;

    try {
      // Save log config only if it changed.
      const logChanged =
        !originalData ||
        formData.loggingPath !== originalData.loggingPath ||
        formData.loggingType !== originalData.loggingType ||
        formData.maxMB !== originalData.maxMB ||
        formData.isEnabled !== originalData.isEnabled;

      if (logChanged) {
        const enabled =
          formData.loggingType === "Debug" || formData.loggingType === "Error"
            ? true
            : formData.isEnabled;

        const data = await saveLogConfig({
          level: formData.loggingType.toUpperCase(),
          folderPath: formData.loggingPath,
          enabled,
          maxSizeMb: parseInt(formData.maxMB, 10) || 50,
        });

        // The folder actually in effect may differ from what was typed,
        // if it wasn't writable and the backend fell back to the default
        // — reflect that back into the form instead of showing a stale value.
        nextFormData.loggingPath = data.folder_path;
        if (data.warning) warning = data.warning;
      }

      // Save upload config only if it changed.
      const uploadChanged =
        !originalData ||
        formData.maxUploadMb !== originalData.maxUploadMb ||
        formData.maxAudioUploadMb !== originalData.maxAudioUploadMb;

      if (uploadChanged) {
        const data = await saveUploadConfig(
          Number(formData.maxUploadMb),
          Number(formData.maxAudioUploadMb)
        );
        nextFormData.maxUploadMb = String(data.max_upload_size_mb);
        nextFormData.maxAudioUploadMb = String(data.max_audio_upload_size_mb);
      }

      // Save LLM config only if the mode changed or a new key was typed.
      // Untouched key field is omitted entirely so the backend leaves the
      // already-stored key as-is (see saveLlmConfig()'s docstring).
      const llmModeChanged =
        !originalData ||
        formData.llmMode !== originalData.llmMode ||
        formData.llmProvider !== originalData.llmProvider ||
        formData.llmModel !== originalData.llmModel;
      const llmChanged = llmModeChanged || llmPrimaryKey.trim() !== "";

      if (llmChanged) {
        const data = await saveLlmConfig({
          mode: formData.llmMode,
          ...(formData.llmMode === "custom"
            ? { provider: formData.llmProvider, model: formData.llmModel }
            : {}),
          ...(llmPrimaryKey.trim() !== "" ? { primaryApiKey: llmPrimaryKey.trim() } : {}),
        });
        nextFormData.llmMode = data.mode;
        nextFormData.llmProvider = data.provider || nextFormData.llmProvider;
        nextFormData.llmModel = data.model || nextFormData.llmModel;
        setLlmPrimaryConfigured(!!data.primary_key_configured);
        setLlmPrimaryMasked(data.primary_key_masked || "");
        setLlmPrimaryKey("");
      }

      setFormData(nextFormData);
      setOriginalData(nextFormData);
      setEditPath(false);

      setStatusMessage(
        warning
          ? { type: "warning", text: warning }
          : { type: "success", text: "Settings saved successfully." }
      );
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: backendErrorText(err, "Could not save settings."),
      });
    } finally {
      setSaving(false);
    }
  };

  // ── Reset to Default: confirm, then reset both sections ──
  const handleResetConfirm = async () => {
    setShowResetConfirm(false);
    setResetting(true);
    setStatusMessage(null);
    setErrors({});

    try {
      const [logData, uploadData, llmData] = await Promise.all([
        resetLogConfig(),
        resetUploadConfig(),
        resetLlmConfig(),
      ]);

      const defaults = {
        loggingPath: logData.folder_path || DEFAULT_VALUES.loggingPath,
        loggingType: toTitleCase(logData.level) || DEFAULT_VALUES.loggingType,
        maxMB: String(logData.max_size_mb ?? DEFAULT_VALUES.maxMB),
        isEnabled: logData.enabled !== undefined ? logData.enabled : true,
        maxUploadMb: String(
          uploadData.max_upload_size_mb ?? DEFAULT_VALUES.maxUploadMb
        ),
        maxAudioUploadMb: String(
          uploadData.max_audio_upload_size_mb ?? DEFAULT_VALUES.maxAudioUploadMb
        ),
        llmMode: llmData.mode || DEFAULT_VALUES.llmMode,
        llmProvider: llmData.provider || DEFAULT_VALUES.llmProvider,
        llmModel: llmData.model || "",
      };

      setFormData(defaults);
      setOriginalData(defaults);
      setEditPath(false);

      setLlmPrimaryKey("");
      setLlmModels([]);
      setLlmPrimaryConfigured(!!llmData.primary_key_configured);
      setLlmPrimaryMasked(llmData.primary_key_masked || "");

      setStatusMessage({ type: "success", text: "All settings reset to default." });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: backendErrorText(err, "Could not reset settings."),
      });
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="business-map-app settings-wrapper">
        <Header title="Settings" />
        <div className="settings-container">
          <div className="settings-card">
            <div className="settings-body">
              <p>Loading settings…</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="business-map-app settings-wrapper">
      <Header
        title="Settings"
        actions={
          <>
            <button
              className="cancel-btn"
              onClick={() => setShowResetConfirm(true)}
              disabled={saving || resetting}
            >
              {resetting ? "Resetting..." : "Reset to Default"}
            </button>
            <button
              className="save-btn"
              onClick={handleSave}
              disabled={saving || resetting || !hasChanges}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </>
        }
      />
      <div className="settings-container">
        <div className="settings-card">
          <div className="settings-header">
            <h2>Logging Configuration</h2>
            <p>Configure application logging settings.</p>
          </div>

          <div className="settings-body">
            {statusMessage && (
              <div className={`settings-banner settings-banner-${statusMessage.type}`}>
                {statusMessage.text}
              </div>
            )}

            {/* Logging Path */}
            <div className="settings-group">
              <label>
                Logging Path
                <span className="required">*</span>
              </label>

              <div className="path-wrapper">
                <input
                  type="text"
                  name="loggingPath"
                  value={formData.loggingPath}
                  onChange={handleChange}
                  readOnly={!editPath}
                />

                <button
                  type="button"
                  className="change-btn"
                  onClick={() => setEditPath(true)}
                >
                  Change
                </button>
              </div>

              {errors.loggingPath && (
                <span className="error-text">{errors.loggingPath}</span>
              )}
            </div>

            {/* Logging Type */}
            <div className="settings-group">
              <label>
                Logging Type
                <span className="required">*</span>
              </label>

              <select
                name="loggingType"
                value={formData.loggingType}
                onChange={handleChange}
              >
                <option>Debug</option>
                <option>Info</option>
                <option>Error</option>
              </select>

              {errors.loggingType && (
                <span className="error-text">{errors.loggingType}</span>
              )}

              <div className="logging-info">
                <label className="checkbox-wrapper">
                  <input
                    type="checkbox"
                    name="isEnabled"
                    checked={formData.isEnabled}
                    disabled={
                      formData.loggingType === "Debug" ||
                      formData.loggingType === "Error"
                    }
                    onChange={handleChange}
                  />
                  Enable Logging
                </label>

                <span className="logging-info-text">
                  {(formData.loggingType === "Debug" ||
                    formData.loggingType === "Error") &&
                    `All ${formData.loggingType} logs will be stored in ${formData.loggingPath}.`}

                  {formData.loggingType === "Info" &&
                    formData.isEnabled &&
                    `Info logs will be stored in ${formData.loggingPath}.`}

                  {formData.loggingType === "Info" &&
                    !formData.isEnabled &&
                    "Info logs will be stored on the server."}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="settings-card">
          <div className="settings-header">
            <h2>Upload Configuration</h2>
            <p>Configure the maximum file size users can upload.</p>
          </div>

          <div className="settings-body">
            <div className="settings-group">
              <label>
                Maximum Upload File Size for Video (MB)
                <span className="required">*</span>
              </label>

              <input
                type="number"
                name="maxUploadMb"
                min={1}
                max={500}
                placeholder="Enter maximum upload size (1-500 MB)"
                value={formData.maxUploadMb}
                onChange={handleChange}
              />

              {errors.maxUploadMb && (
                <span className="error-text">{errors.maxUploadMb}</span>
              )}
            </div>

            <div className="settings-group">
              <label>
                Maximum Upload File Size for Audio (MB)
                <span className="required">*</span>
              </label>

              <input
                type="number"
                name="maxAudioUploadMb"
                min={1}
                max={500}
                placeholder="Enter maximum upload size (1-500 MB)"
                value={formData.maxAudioUploadMb}
                onChange={handleChange}
              />

              {errors.maxAudioUploadMb && (
                <span className="error-text">{errors.maxAudioUploadMb}</span>
              )}
            </div>
          </div>
        </div>

        <div className="settings-card">
          <div className="settings-header">
            <h2>LLM Configuration</h2>
            <p>Choose which LLM credentials to use for report generation.</p>
          </div>

          <div className="settings-body">
            {!llmEncryptionAvailable && (
              <div className="settings-banner settings-banner-warning">
                Custom API keys aren't available right now — please contact
                your administrator. The application default credentials
                will be used.
              </div>
            )}

            <div className="settings-group">
              <label className="llm-radio-option">
                <input
                  type="radio"
                  name="llmMode"
                  value="default"
                  checked={formData.llmMode === "default"}
                  onChange={handleChange}
                />
                <span className="llm-radio-text">
                  <span className="llm-radio-title">Default Application API Key</span>
                  <span className="llm-radio-desc">
                    Use the API key configured by the system. No key needed from you.
                  </span>
                </span>
              </label>

              <label className="llm-radio-option">
                <input
                  type="radio"
                  name="llmMode"
                  value="custom"
                  checked={formData.llmMode === "custom"}
                  onChange={handleChange}
                  disabled={!llmEncryptionAvailable}
                />
                <span className="llm-radio-text">
                  <span className="llm-radio-title">Use My Own API Key</span>
                  <span className="llm-radio-desc">
                    Use custom LLM credentials for this account instead of the application default.
                  </span>
                </span>
              </label>

              {errors.llmMode && <span className="error-text">{errors.llmMode}</span>}
            </div>

            {formData.llmMode === "custom" && (
              <div className="llm-custom-keys">
                <div className="settings-group">
                  <label>Provider</label>
                  <select
                    value={formData.llmProvider}
                    onChange={(e) => {
                      setFormData((prev) => ({
                        ...prev,
                        llmProvider: e.target.value,
                        llmModel: "",
                      }));
                      setLlmModels([]);
                    }}
                  >
                    {LLM_PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="settings-group">
                  <label>
                    API Key
                    {!llmPrimaryConfigured && <span className="required">*</span>}
                  </label>
                  <div className="path-wrapper">
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={llmPrimaryKey}
                      onChange={(e) => {
                        setLlmPrimaryKey(e.target.value);
                        setErrors((prev) => ({ ...prev, llmPrimaryKey: "" }));
                      }}
                      placeholder={
                        llmPrimaryConfigured
                          ? llmPrimaryMasked || "Configured — leave blank to keep"
                          : "Paste the API key"
                      }
                    />
                    {llmPrimaryConfigured && (
                      <button
                        type="button"
                        className="change-btn"
                        onClick={handleDeleteLlmKey}
                        disabled={deletingLlmKey}
                      >
                        {deletingLlmKey ? "Deleting…" : "Delete"}
                      </button>
                    )}
                  </div>
                  {errors.llmPrimaryKey && (
                    <span className="error-text">{errors.llmPrimaryKey}</span>
                  )}
                  {llmPrimaryConfigured && !llmPrimaryKey && (
                    <span className="logging-info-text">
                      A key is already saved. Leave blank to keep it, enter a new one to replace it, or delete it.
                    </span>
                  )}
                </div>

                <div className="settings-group">
                  <label>
                    Model<span className="required">*</span>
                  </label>
                  <div className="path-wrapper">
                    <select
                      value={formData.llmModel}
                      onChange={(e) => {
                        setFormData((prev) => ({ ...prev, llmModel: e.target.value }));
                        setErrors((prev) => ({ ...prev, llmModel: "" }));
                      }}
                    >
                      {!llmModels.includes(formData.llmModel) && (
                        <option value={formData.llmModel}>
                          {formData.llmModel || "Press Refresh to load the models"}
                        </option>
                      )}
                      {llmModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="change-btn"
                      onClick={handleRefreshModels}
                      disabled={loadingModels}
                    >
                      {loadingModels ? "Loading…" : "Refresh"}
                    </button>
                  </div>
                  {errors.llmModel && <span className="error-text">{errors.llmModel}</span>}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Reset to Default confirmation dialog ── */}
      <Modal open={showResetConfirm} labelledBy="reset-confirm-title">
        <div className="bm-modal-icon">⚠️</div>
        <h2 className="bm-modal-title" id="reset-confirm-title">
          Reset to Default?
        </h2>
        <p className="bm-modal-body">
          All unsaved and customized settings will be reverted to their default
          values. This action cannot be undone.
        </p>
        <div className="bm-modal-actions">
          <button
            className="bm-modal-btn bm-modal-btn-edit"
            onClick={() => setShowResetConfirm(false)}
            type="button"
          >
            Cancel
          </button>
          <button
            className="bm-modal-btn bm-modal-btn-ok"
            onClick={handleResetConfirm}
            type="button"
          >
            Reset
          </button>
        </div>
      </Modal>
    </div>
  );
}

function toTitleCase(levelUpper) {
  if (!levelUpper) return "Debug";
  return levelUpper.charAt(0) + levelUpper.slice(1).toLowerCase();
}

export default Settings;