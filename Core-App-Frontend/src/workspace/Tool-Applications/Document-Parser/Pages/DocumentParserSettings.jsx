import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../../../components/WorkspaceHeader";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { getNexaflowUserId } from "../../../utils/documentParserUser";
import "../Styles/commonstyle.css";
import "../Styles/settings.css";

const API_BASE = `${API_BASE_URL}/document`;

function DocumentParserSettings() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    loggingPath: "D:\\OneNextGen\\Logs",
    loggingType: "Debug",
    maxMB: "",
    checked: false,
    outputBasePath: "C:\\Users",
  });

  const [editPath, setEditPath] = useState(false);
  const [editMaxMB, setEditMaxMB] = useState(false);
  const [editOutputPath, setEditOutputPath] = useState(false);
  const pathRef = useRef(null);
  const maxMBRef = useRef(null);
  const outputPathRef = useRef(null);

const [errors, setErrors] = useState({});
  const [isEnabled, setIsEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        // The `userId` in the URL is kept only so the path is
        // self-documenting -- the backend ignores it and always scopes
        // the response to whichever user the Bearer token (attached by
        // authFetch) proves is actually logged in.
        const userId = getNexaflowUserId() ?? 1;
        const res = await authFetch(`${API_BASE}/settings/${userId}`);
        const data = await res.json();

        if (data.status === "success" && data.settings) {
          const s = data.settings;
          let typeVal = "Debug";
          if (s.log_type) {
            const lower = s.log_type.toLowerCase();
            if (lower === "info") typeVal = "Info";
            else if (lower === "error") typeVal = "Error";
            else typeVal = "Debug";
          }

          const isDebugOrError = typeVal === "Debug" || typeVal === "Error";

          setFormData({
            loggingPath: s.log_path || "D:\\OneNextGen\\Logs",
            loggingType: typeVal,
            maxMB: String(s.file_max_size_mb || ""),
            checked: isDebugOrError ? true : (s.checked || false),
            outputBasePath: s.output_base_path || "C:\\Users",
          });
          setIsEnabled(isDebugOrError ? true : (s.checked || false));
        }
      } catch (err) {
        console.warn("Failed to load settings from backend, using defaults.", err);
        const saved = localStorage.getItem("loggingSettings");
        if (saved) {
          const data = JSON.parse(saved);
          const isDebugOrError = data.loggingType === "Debug" || data.loggingType === "Error";
          setFormData({
            loggingPath: data.loggingPath || "D:\\OneNextGen\\Logs",
            loggingType: data.loggingType || "Debug",
            maxMB: data.maxMB || "100",
            checked: isDebugOrError ? true : (data.checked || false),
            outputBasePath: data.outputBasePath || "C:\\Users",
          });
          setIsEnabled(isDebugOrError ? true : (data.enabled !== undefined ? data.enabled : true));
        }
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const val = type === "checkbox" ? checked : value;

    setFormData((prev) => ({ ...prev, [name]: val }));
    setErrors((prev) => ({ ...prev, [name]: "" }));

    if (name === "loggingType") {
      if (value === "Debug" || value === "Error") {
        setIsEnabled(true);
        setFormData((prev) => ({ ...prev, checked: true }));
      }
    }

    if (name === "checked") {
      setIsEnabled(checked);
    }
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

    if (!formData.outputBasePath.trim()) {
      newErrors.outputBasePath = "Document output path is required.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;

    const settingsPayload = {
      log_path: formData.loggingPath,
      log_type: formData.loggingType,
      checked: formData.loggingType === "Info" ? isEnabled : true,
      file_max_size_mb: parseInt(formData.maxMB, 10) || 50,
      output_base_path: formData.outputBasePath,
    };

try {
      const userId = getNexaflowUserId() ?? 1;
      const res = await authFetch(`${API_BASE}/settings/${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          log_path: settingsPayload.log_path,
          log_type: settingsPayload.log_type,
          checked: settingsPayload.checked,
          file_max_size_mb: settingsPayload.file_max_size_mb,
          output_base_path: settingsPayload.output_base_path,
        }),
      });

      const data = await res.json();

      if (data.status === "success") {
        alert("Settings saved successfully.");
      } else {
        alert("Failed to save settings.");
      }
    } catch (err) {
      console.error("Backend save failed, saving to localStorage as fallback.", err);
      const settings = {
        loggingPath: formData.loggingPath,
        loggingType: formData.loggingType,
        maxMB: formData.maxMB,
        checked: settingsPayload.checked,
        enabled: isEnabled,
        outputBasePath: formData.outputBasePath,
      };

      localStorage.setItem("loggingSettings", JSON.stringify(settings));
      alert("Settings saved locally (backend unavailable).");
    }
  };

  const handleCancel = () => {
    navigate(-1);
  };

  if (loading) {
    return (
      <>
        <Header title="Document Parser Settings" />
        <main className="main-content">
          <div className="settings-container">
            <p>Loading settings...</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header
        title="Document Parser Settings"
        description="Configure logging for the Document Parser"
        actions={
          <>
            <button className="cancel-btn" onClick={handleCancel}>
              Cancel
            </button>
            <button className="save-btn" onClick={handleSave}>
              Save
            </button>
          </>
        }
      />
      <main className="main-content">
        <div className="settings-container">
        <div className="settings-card">
          <div className="settings-header">
            <h2>Logging Configuration</h2>
            <p>Configure application logging settings.</p>
          </div>

          <div className="settings-body">
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
                  ref={pathRef}
                />

                <button
                  type="button"
                  className="change-btn"
                  onClick={() => {
                    setEditPath(true);
                    setTimeout(() => pathRef.current?.focus(), 0);
                  }}
                >
                  Change
                </button>
              </div>

              {errors.loggingPath && (
                <span className="error-text">{errors.loggingPath}</span>
              )}
            </div>

            {/* Document Output Path */}
            <div className="settings-group">
              <label>
                Document output path
                <span className="required">*</span>
              </label>

              <div className="path-wrapper">
                <input
                  type="text"
                  name="outputBasePath"
                  value={formData.outputBasePath}
                  onChange={handleChange}
                  readOnly={!editOutputPath}
                  ref={outputPathRef}
                />

                <button
                  type="button"
                  className="change-btn"
                  onClick={() => {
                    setEditOutputPath(true);
                    setTimeout(() => outputPathRef.current?.focus(), 0);
                  }}
                >
                  Change
                </button>
              </div>

              {errors.outputBasePath && (
                <span className="error-text">{errors.outputBasePath}</span>
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
                className="settings-select"
              >
                <option value="Debug">Debug</option>
                <option value="Info">Info</option>
                <option value="Error">Error</option>
              </select>

              {errors.loggingType && (
                <span className="error-text">{errors.loggingType}</span>
              )}

              <div className="logging-info">
                <label className="checkbox-wrapper">
                  <input
                    type="checkbox"
                    name="checked"
                    checked={isEnabled}
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
                    isEnabled &&
                    `Info logs will be stored in ${formData.loggingPath}.`}

                  {formData.loggingType === "Info" &&
                    !isEnabled &&
                    "Info logs will be stored on the server."}
                </span>
              </div>
            </div>

            {/* Max MB */}
            <div className="settings-group">
              <label>
                Maximum Input file Size(MB)
                <span className="required">*</span>
              </label>

              <div className="path-wrapper">
                <input
                  type="number"
                  name="maxMB"
                  placeholder="Enter Maximum Input file Size(MB)"
                  value={formData.maxMB}
                  onChange={handleChange}
                  readOnly={!editMaxMB}
                  ref={maxMBRef}
                />

                <button
                  type="button"
                  className="change-btn"
                  onClick={() => {
                    setEditMaxMB(true);
                    setTimeout(() => maxMBRef.current?.focus(), 0);
                  }}
                >
                  Change
                </button>
              </div>

              {errors.maxMB && (
                <span className="error-text">{errors.maxMB}</span>
              )}
            </div>
          </div>
        </div>
        </div>
      </main>
    </>
  );
}

export default DocumentParserSettings;