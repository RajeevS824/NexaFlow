

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useDPUnsavedChanges } from "../../../context/DP-UnsavedChangesContext";
import Header from "../../../components/WorkspaceHeader";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import { registerChildWindow } from "../../../utils/childWindows";
import "../Styles/commonstyle.css";
import "../Styles/processExtractionModel.css";

// Format a date string to "DD-MM-YYYY HH:MM AM/PM"
function formatDateTime(raw) {
  if (!raw) return "-";
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw;
    const dateStr = [
      String(d.getDate()).padStart(2, "0"),
      String(d.getMonth() + 1).padStart(2, "0"),
      d.getFullYear(),
    ].join("-");
    let hours = d.getHours();
    const minutes = String(d.getMinutes()).padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;
    const timeStr = `${String(hours).padStart(2, "0")}:${minutes} ${ampm}`;
    return `${dateStr} ${timeStr}`;
  } catch {
    return raw;
  }
}

const hasProcessableFields = (model) => {
  const hasFormFields =
    Array.isArray(model.formFields) &&
    model.formFields.length > 0;

  const hasTableFields =
    model.tableFields &&
    typeof model.tableFields === "object" &&
    Object.values(model.tableFields).some(
      (table) =>
        Array.isArray(table.fields) &&
        table.fields.length > 0
    );

  return hasFormFields || hasTableFields;
};

function ProcessExtractionModel() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  const {
    checkUnsavedChanges
  } = useDPUnsavedChanges();

  const [models, setModels] = useState([]);
  const [dbReady, setDbReady] = useState(false);
  const [editModal, setEditModal] = useState(null);
  const [deleteModal, setDeleteModal] = useState(null);
  const [popup, setPopup] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [searchText, setSearchText] = useState("");

  useEffect(() => {
    refreshModels();
  }, []);

  const refreshModels = async () => {
    try {
      setDbReady(false);
      const response = await authFetch(`${API_BASE_URL}/document/models`);
      const data = await response.json();
      const rows = Array.isArray(data?.models) ? data.models : [];
      setModels(rows);
      localStorage.setItem("extractionModels", JSON.stringify(rows));
      setDbReady(true);
    } catch (error) {
      console.error("Model loading failed:", error);
      setModels([]);
      setDbReady(true);
      setPopup({
        title: "Loading Error",
        message: "Unable to load extraction models.",
      });
    }
  };


  const handleProcess = (model) => {

    if (processing) return;

    if (!hasProcessableFields(model)) {
      setPopup({
        title: "No Fields Available",
        message:
          "Please create at least one Form Field or one Table before processing.",
      });
      return;
    }


    setProcessing(true);


    const processWindow = window.open(
      `${docBase}/document-processing?modelId=${encodeURIComponent(model.id)}`,
      "_blank"
    );


    if (!processWindow) {
      setPopup({
        title: "Popup Blocked",
        message:
          "Please allow popup permission to open processing page.",
      });

      setProcessing(false);
      return;
    }

    // Track this tab so that logging out (in this tab or any other) also
    // closes it -- it holds its own copy of the session and would
    // otherwise keep "processing" after the user has signed out.
    registerChildWindow(processWindow);

    setTimeout(() => {
      setProcessing(false);
    }, 1000);
  };

    const handleView = (model) => {
      navigate(
        `${docBase}/history-process-model?modelId=${encodeURIComponent(
          model.id
        )}&modelName=${encodeURIComponent(model.name)}`
      );
    };


  const handleEdit = (model) => {
    for (let i = localStorage.length - 1; i >= 0; i -= 1) {
      const key = localStorage.key(i);
      if (key && key.startsWith("draftExtractionFields")) {
        localStorage.removeItem(key);
      }
    }

    setEditModal(model);
  };


  const handleDelete = (model) => {
    setDeleteModal(model);
  };


  const confirmEdit = () => {

    if (!editModal) return;


    localStorage.setItem(
      "editModelId",
      String(editModal.id)
    );


    localStorage.setItem(
      "fromProcessModel",
      `${docBase}/document-process-model`
    );


    navigate(
      `${docBase}/create-process-model?edit=true`
    );


    setEditModal(null);
  };


  const confirmDelete = async () => {
    if (!deleteModal || deleting) return;

    try {
      setDeleting(true);
      const force = deleteModal.processCount > 0 ? "?force=true" : "";
      const response = await authFetch(`${API_BASE_URL}/document/models/${encodeURIComponent(deleteModal.id)}${force}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "Unable to delete model.");
      await refreshModels();
      setDeleteModal(null);
    } catch (error) {
      console.error("Delete failed:", error);
      setPopup({ title: "Delete Error", message: error.message || "Unable to delete model. Please try again." });
    } finally {
      setDeleting(false);
    }
  };



  const openCreatePage = () => {

    for (let i = localStorage.length - 1; i >= 0; i -= 1) {
      const key = localStorage.key(i);
      if (key && key.startsWith("draftExtractionFields")) {
        localStorage.removeItem(key);
      }
    }

    localStorage.removeItem(
      "editModelId"
    );

    localStorage.removeItem(
      "tempModel_modelName"
    );

    localStorage.removeItem(
      "tempModel_selectModel"
    );

    localStorage.removeItem(
      "tempModel_description"
    );

    localStorage.removeItem(
      "tempModel_documentType"
    );

    localStorage.removeItem(
      "tempModel_language"
    );


    localStorage.setItem(
      "fromProcessModel",
      `${docBase}/document-process-model`
    );


    navigate(
      `${docBase}/create-process-model`
    );

  };


  const openCancelPage = () => {

    checkUnsavedChanges(() => {

      navigate(
        docBase
      );

    });

  };

  const filteredModels = models.filter((model) => {
    const search = searchText.toLowerCase().trim();

    return (
      (model.name || "").toLowerCase().includes(search) ||
      (model.engine || "").toLowerCase().includes(search) ||
      (model.documentType || "").toLowerCase().includes(search) ||
      formatDateTime(model.created).toLowerCase().includes(search) ||
      formatDateTime(model.updated).toLowerCase().includes(search)
    );
  });

    return (
    <div className="pem-page">

      <Header
        title="Document Process Model"
        actions={
          <>
             <input
                type="text"
                className="table-search"
                placeholder="Search Model, Engine, Document Type, Date..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />

            <button
              className="btn-primary-dp"
              onClick={openCreatePage}
            >
              + Create
            </button>


            <button
              className="btn-secondary-dp"
              onClick={openCancelPage}
            >
              Cancel
            </button>
          </>
        }
      />


      <div className="pem-body">

        <div className="pem-card">

          <div className="pem-card-title">
            Models
          </div>
          


          {!dbReady ? (

            <div className="pem-loading">
              Loading database…
            </div>

          ) : (

            <div className="pem-table-wrap">

              <table className="pem-table">

                <thead>

                  <tr>
                    <th>ID</th>
                    <th>Model Name</th>
                    <th>Engine Type</th>
                    <th>Document Type</th>
                    <th>Form Fields</th>
                    <th>Tables</th>
                    <th>Created</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>

                </thead>


                <tbody>

                {filteredModels.length === 0 ? (

                  <tr className="pem-no-data">

                    <td colSpan={9}>
                      No extraction models found.
                    </td>

                  </tr>

                ) : (

                  filteredModels.map((model, idx) => (

                    <tr key={model.id || idx}>


                      <td>
                        {idx + 1}
                      </td>


                      <td>
                        <strong>
                          {model.name || "-"}
                        </strong>
                      </td>


                      <td>

                        <span
                          className={`engine-badge engine-${
                            typeof model.engine === "string"
                              ? model.engine.toLowerCase()
                              : "ocr"
                          }`}
                        >
                          {model.engine || "OCR"}
                        </span>

                      </td>


                      <td>
                        {model.documentType || "invoice"}
                      </td>


                      <td>
                        {
                          Array.isArray(model.formFields)
                            ? model.formFields.length
                            : 0
                        }
                      </td>


                      <td>
                        {
                          model.tableFields &&
                          typeof model.tableFields === "object"
                            ? Object.keys(model.tableFields).length
                            : 0
                        }
                      </td>


                      <td>
                        {formatDateTime(model.created)}
                      </td>


                      <td>
                        {formatDateTime(model.updated)}
                      </td>


                      <td>
                        <div className="pem-action-group">

                        <button
                          className="pem-action-btn process"
                          disabled={processing || !hasProcessableFields(model)}
                          onClick={() =>
                            handleProcess(model)
                          }
                        >
                          Process
                        </button>


                        <button
                          className="pem-action-btn view"
                          onClick={() =>
                            handleView(model)
                          }
                        >
                          History
                        </button>


                        <button
                          className="pem-action-btn edit"
                          onClick={() =>
                            handleEdit(model)
                          }
                        >
                          Edit
                        </button>


                        <button
                          className="pem-action-btn delete"
                          onClick={() =>
                            handleDelete(model)
                          }
                        >
                          Delete
                        </button>
                      </div>

                      </td>

                      
                    </tr>

                  ))

                )}

                </tbody>

              </table>

            </div>

          )}

        </div>

      </div>



      {editModal && (

        <div className="pem-modal-overlay">

          <div className="pem-modal-card">

            <h3>
              Edit Model
            </h3>


            <p>
              Do you want to edit{" "}
              <strong>
                {editModal.name}
              </strong>
              ?
            </p>


            <div className="pem-modal-actions">

              <button
                className="btn-secondary-dp"
                onClick={() =>
                  setEditModal(null)
                }
              >
                No
              </button>


              <button
                className="btn-primary-dp"
                onClick={confirmEdit}
              >
                Yes
              </button>


            </div>

          </div>

        </div>

      )}



      {deleteModal && (

        <div className="pem-modal-overlay">

          <div className="pem-modal-card">

            <h3>
              Delete Model
            </h3>

            {deleteModal.processCount > 0 ? (
              <>
                <p>
                  {deleteModal.processCount} process{deleteModal.processCount === 1 ? "" : "es"} done. Deleting this model will also delete all associated process data permanently.
                </p>
                <p>
                  Do you want to delete{" "}
                  <strong>
                    {deleteModal.name}
                  </strong>
                  ?
                </p>
              </>
            ) : (
              <p>
                Do you want to delete{" "}
                <strong>
                  {deleteModal.name}
                </strong>
                ?
              </p>
            )}

            <div className="pem-modal-actions">


              <button
                className="btn-secondary-dp"
                onClick={() =>
                  setDeleteModal(null)
                }
              >
                No
              </button>


              <button
                className="btn-primary-dp"
                disabled={deleting}
                onClick={confirmDelete}
              >
                {deleting ? "Deleting..." : "Yes"}
              </button>


            </div>

          </div>

        </div>

      )}



      {popup && (

        <div className="pem-modal-overlay">

          <div className="pem-modal-card">

            <h3>
              {popup.title}
            </h3>


            <p>
              {popup.message}
            </p>


            <div className="pem-modal-actions">

              <button
                className="btn-primary-dp"
                onClick={() =>
                  setPopup(null)
                }
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


export default ProcessExtractionModel;