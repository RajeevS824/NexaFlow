import { useCallback, useEffect, useState } from "react";
import "../Styles/commonstyle.css";
import "../Styles/HistoryExtractionModel.css";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../../../components/WorkspaceHeader";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import { useDocumentParserHistorySocket } from "../../../hooks/useDocumentParserHistorySocket";

// Display raw datetime value from database without modification
function formatDateTime(raw) {
  return raw || "-";
}

function ViewExtractionModel() {
  const [history, setHistory] = useState([]);
  const [searchText, setSearchText] = useState("");
  const [modelName, setModelName] = useState("");
  const [errorPopup, setErrorPopup] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  const params = new URLSearchParams(location.search);
  const historyModelId = params.get("modelId");
  const modelNameFromUrl = params.get("modelName");

  const loadHistory = useCallback(async () => {
    const currentParams = new URLSearchParams(location.search);
    const currentModelId = currentParams.get("modelId");

    try {
      const endpoint = currentModelId
        ? `${API_BASE_URL}/document/history?model_id=${encodeURIComponent(currentModelId)}`
        : `${API_BASE_URL}/document/history`;
      const response = await authFetch(endpoint);
      const data = await response.json();
      const nextHistory = Array.isArray(data?.history) ? data.history : [];
      setHistory(nextHistory);

      // If history exists
      if (nextHistory.length > 0) {
        setModelName(nextHistory[0].modelname || "");
      }
      // If no history, fetch model name using modelId
      else if (currentModelId) {
        const modelRes = await authFetch(`${API_BASE_URL}/document/models`);
        const modelData = await modelRes.json();

        const models = Array.isArray(modelData.models) ? modelData.models : [];

        const model = models.find(
          (m) => String(m.modelid) === String(currentModelId)
        );

        if (model) {
          setModelName(model.modelname);
        }
      }
    } catch (error) {
      console.error("Unable to load history:", error);
      setHistory([]);
    }
  }, [location.search]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Live updates: whenever the backend reports a job being created,
  // updated, completed, or failed for this model, re-pull the history
  // list instead of waiting for the user to refresh the page. See
  // DP-backend/app/core/ws_manager.py for the events this reacts to.
  useDocumentParserHistorySocket(historyModelId, () => {
    loadHistory();
  });

  const filteredHistory = history.filter((item) => {
    const search = searchText.toLowerCase().trim();

    return (
      (item.modelname || "").toLowerCase().includes(search) ||
      (item.enginetype || "").toLowerCase().includes(search) ||
      (item.documenttype || "").toLowerCase().includes(search) ||
      (item.status || "").toLowerCase().includes(search) ||
      (item.processdate || "").toLowerCase().includes(search)
    );
  });

  return (
    <div className="hem-page">
      <Header
        title={
          historyModelId
            ? `${modelName || modelNameFromUrl || ""} - History Extraction Model`
            : "History Extraction Model"
        }
        actions={
          <>
            <input
              type="text"
              className="table-search"
              placeholder="Search Model, Engine, Status, Date..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />

            <button
              className="btn-secondary-dp"
              onClick={() => navigate(historyModelId ? `${docBase}/document-process-model` : docBase)}
            >
              Back
            </button>
          </>
        }
      />

      {errorPopup && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div
            style={{
              backgroundColor: "#fff",
              borderRadius: "12px",
              padding: "24px",
              maxWidth: "500px",
              width: "90%",
              boxShadow: "0 10px 40px rgba(0,0,0,0.3)",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "48px", marginBottom: "12px" }}>⚠️</div>
            <h3 style={{ margin: "0 0 12px", color: "#dc2626" }}>Processing Failed</h3>
            <p style={{ margin: "8px 0 20px", fontSize: "14px", color: "#6b7280", wordBreak: "break-word" }}>
              Error interrupted: {errorPopup.errorMessage}
            </p>
            <button
              onClick={() => setErrorPopup(null)}
              style={{
                backgroundColor: "#dc2626",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "8px 32px",
                fontSize: "14px",
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              OK
            </button>
          </div>
        </div>
      )}

      <div className="hem-body">
        <div className="hem-card">

          <div className="hem-card-title">
            History
          </div>

          <div className="hem-table-wrap">
            <table className="hem-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Model Name</th>
                  <th>Document Type</th>
                  <th>Document Name</th>
                  <th>Process Date & Time</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filteredHistory.length > 0 ? (
                  filteredHistory.map((item) => (
                    <tr key={item.historyid}>
                      <td>{item.status}</td>
                      <td>
                        <strong>{item.modelname}</strong>
                      </td>
                      <td>{item.documenttype}</td>
                      <td>{item.documentname || "-"}</td>
                      <td>{formatDateTime(item.processdate)}</td>
                      <td className="hem-action-cell">
                        <div className="hem-action-buttons">

                          {["cancelled"].includes(
                            item.status?.toLowerCase()
                          ) && (
                            <button
                              className="hem-btn-reprocess"
                              onClick={() => {
                                const modelName =
                                  item.modelname || "the previously selected model";

                                const confirmed = window.confirm(
                                  `This job was interrupted due to a client disconnect. Please select the original file and reprocess the document using the previously selected model: ${modelName}.`
                                );

                                if (confirmed) {
                                  navigate(
                                    `${docBase}/document-processing?modelId=${encodeURIComponent(
                                      item.modelid
                                    )}&reprocessHistoryId=${encodeURIComponent(
                                      item.historyid
                                    )}`
                                  );
                                }
                              }}
                            >
                              Reprocess
                            </button>
                          )}

                          {["processing", "pending", "failed"].includes(
                            item.status?.toLowerCase()
                          ) && (
                            <button
                              className="hem-btn-validate"
                              onClick={async () => {
                                const status = (item.status || "").toLowerCase();
                                // For failed jobs, fetch the error message from the
                                // processing_jobs table and show it in a popup
                                if (status === "failed") {
                                  try {
                                    const res = await authFetch(
                                      `${API_BASE_URL}/document/history/${encodeURIComponent(item.historyid)}`
                                    );
                                    const data = await res.json();
                                    const errorMsg =
                                      data?.history?.error_message ||
                                      item.error_message ||
                                      "An unexpected error occurred during processing.";
                                    setErrorPopup({
                                      jobId: item.historyid,
                                      errorMessage: errorMsg,
                                    });
                                  } catch (err) {
                                    console.error("Failed to fetch job error message:", err);
                                    setErrorPopup({
                                      jobId: item.historyid,
                                      errorMessage: item.error_message || "An unexpected error occurred during processing.",
                                    });
                                  }
                                  return;
                                }
                                navigate(
                                  `${docBase}/document-processing?modelId=${encodeURIComponent(
                                    item.modelid
                                  )}&reprocessHistoryId=${encodeURIComponent(
                                    item.historyid
                                  )}`
                                );
                              }}
                            >
                              Validate
                            </button>
                          )}

                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr className="hem-no-data">
                    <td colSpan="6">
                      No history found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

        </div>
      </div>
    </div>
  );
}

export default ViewExtractionModel;