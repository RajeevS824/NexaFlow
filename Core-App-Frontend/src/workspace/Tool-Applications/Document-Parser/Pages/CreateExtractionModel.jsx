import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../../../components/WorkspaceHeader";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import "../Styles/commonstyle.css";
import "../Styles/createExtractionModel.css";

function CreateExtractionModel() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;

  const [form, setForm] = useState({
    selectModel: "invoice",
    modelName: "",
    modelDescription: "",
    documentType: "invoice",
    language: "en",
  });
  const [errors, setErrors] = useState({});
  const [isEditMode, setIsEditMode] = useState(false);

  useEffect(() => {
    const editModelId = localStorage.getItem("editModelId");

    if (!editModelId) {
      setIsEditMode(false);
      const tempData = {
        selectModel: localStorage.getItem("tempModel_selectModel") || "invoice",
        modelName: localStorage.getItem("tempModel_modelName") || "",
        modelDescription: localStorage.getItem("tempModel_description") || "",
        documentType: localStorage.getItem("tempModel_documentType") || "invoice",
        language: localStorage.getItem("tempModel_language") || "en",
      };
      setForm(tempData);
      return;
    }

    setIsEditMode(true);

    const loadModel = async () => {
      try {
        const response = await authFetch(`${API_BASE_URL}/document/models`);
        const data = await response.json();
        const model = Array.isArray(data?.models) ? data.models.find((item) => String(item.id) === String(editModelId)) : null;

        if (model) {
          setForm({
            selectModel: localStorage.getItem("tempModel_selectModel") || (model.engine === "OCR" || model.engine === "invoice" ? "invoice" : "receipt"),
            modelName: localStorage.getItem("tempModel_modelName") || model.name || "",
            modelDescription: localStorage.getItem("tempModel_description") || model.description || "",
            documentType: (localStorage.getItem("tempModel_documentType") || model.documentType || model.documenttype || "invoice").toLowerCase(),
            language: localStorage.getItem("tempModel_language") || model.language || "en",
          });
        }
      } catch (error) {
        console.warn("Could not load model for edit mode:", error);
      }
    };

    loadModel();
  }, []);


  const handleChange = (e) => {
   

    const { name, value } = e.target;

    if (name === "modelName") {
      // Allow only letters, numbers, spaces, underscores and hyphens
      if (!/^[A-Za-z0-9 _-]*$/.test(value)) {
        return;
      }
    }

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));

    setErrors((prev) => ({
      ...prev,
      [name]: "",
    }));
  };

  const validate = () => {
    const errs = {};

    if (!form.selectModel) {
      errs.selectModel = "Select Model is required";
    }

    const modelName = form.modelName.trim();

    if (!modelName) {
      errs.modelName = "Model Name is required";
    } else if (modelName.length < 3) {
      errs.modelName = "Model Name must be at least 3 characters long";
    } else if (modelName.length > 30) {
      errs.modelName = "Model Name cannot exceed 30 characters";
    } else if (!/^[A-Za-z0-9 _-]+$/.test(modelName)) {
      errs.modelName =
        "Model Name can contain only letters, numbers, spaces, underscores (_) and hyphens (-)";
    } else if ((modelName.match(/[_-]/g) || []).length > 2) {
      errs.modelName =
        "Model Name can contain a maximum of 2 underscores (_) or hyphens (-).";
    } else if (modelName.replace(/[^A-Za-z0-9]/g, "").length < 3) {
      errs.modelName =
        "Model Name must contain at least 3 letters or numbers.";
    } else if (
      form.modelName.startsWith(" ") ||
      form.modelName.endsWith(" ")
    ) {
      errs.modelName =
        "Model Name cannot start or end with a space";
    }

    if (!form.documentType) {
      errs.documentType = "Document Type is required";
    }

    const description = form.modelDescription;

    if (description) {
      if (!description.trim()) {
        errs.modelDescription = "Description cannot contain only spaces.";
      } else if (description.length > 100) {
        errs.modelDescription = "Description cannot exceed 100 characters.";
      } else if (/^(.)\1+$/.test(description.replace(/\s/g, ""))) {
        errs.modelDescription = "Please enter a meaningful description.";
      } else if (/(.)\1{3,}/i.test(description.replace(/[\s_-]/g, ""))) {
        errs.modelDescription =
          "Please enter a meaningful description.";
      }
    }

    if (!form.language) {
      errs.language = "Language is required";
    }
    return errs;
  };

  const handleSaveAndNext = async () => {
   

    const validationErrors = validate();

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    try {
      const response = await authFetch(`${API_BASE_URL}/document/models`);
      const data = await response.json();
      const serverModels = data?.models || [];
      const duplicateServerModel = serverModels.find(
        (m) => m.name?.trim().toLowerCase() === form.modelName.trim().toLowerCase() && String(m.id) !== String(localStorage.getItem("editModelId"))
      );
      if (duplicateServerModel) {
        setErrors((prev) => ({ ...prev, modelName: "Already model created. Type another name." }));
        return;
      }
    } catch (error) {
      console.warn("Could not verify duplicate models on backend:", error);
    }
    localStorage.setItem("modelName", form.modelName);
    localStorage.setItem("tempModel_selectModel", form.selectModel);
    localStorage.setItem("tempModel_modelName", form.modelName);
    localStorage.setItem("tempModel_description", form.modelDescription);
    localStorage.setItem("tempModel_documentType", form.documentType);
    localStorage.setItem("tempModel_language", form.language);
    // New model - clear any old draft
    if (!isEditMode) {
      localStorage.removeItem("draftExtractionFields");
    }
    localStorage.setItem("fieldMode", "create");

    navigate(`${docBase}/create-process-model/create-process-field`);
  };

  const clearTempModelData = () => {
    localStorage.removeItem("tempModel_selectModel");
    localStorage.removeItem("tempModel_modelName");
    localStorage.removeItem("tempModel_description");
    localStorage.removeItem("tempModel_documentType");
    localStorage.removeItem("tempModel_language");
  };

  const handleCancel = () => {
    clearTempModelData();

    localStorage.removeItem("editModelId");

    const backPage =
      localStorage.getItem("fromProcessModel") ||
      docBase;

    localStorage.removeItem("fromProcessModel");

    navigate(backPage);
      };

  return (
    <div className="cem-page">

      {/* ── Global Header with page title + action buttons ── */}
      <Header
        title={isEditMode ? "Edit Process Model" : "Create Process Model"}

        actions={
          <>
            <button className="btn-primary-dp" onClick={handleSaveAndNext}>
              Next
            </button>
            <button className="btn-secondary-dp" 
            onClick={handleCancel}
            >
              Back
            </button>
            
          </>
        }
      />

      {/* ── Scrollable form body ── */}
      <div className="cem-body">
        <div className="cem-card">
          {!form.modelName.trim() && (
            <p className="cem-card-note">
              {/* Select a model and fill in the required information */}
              Enter a model name and select the appropriate options to create a new extraction model.
            </p>
          )}

          <div className="cem-field">
            <label className="cem-label">Select Model</label>
            <select
              className={`cem-select${errors.selectModel ? " error" : ""}`}
              name="selectModel"
              value={form.selectModel}
              
              onChange={handleChange}
            >
              <option value="invoice">OCR</option>
              <option value="receipt">LLM</option>
            </select>
            <span className="cem-error">{errors.selectModel || ""}</span>
          </div>

          <div className="cem-field">
            <label className="cem-label">Model Name</label>
              <input
                className={`cem-input${errors.modelName ? " error" : ""}`}
                type="text"
                name="modelName"
                placeholder="Enter model name"
                value={form.modelName}
                maxLength={30}
                
                onChange={handleChange}
              />
            <span className="cem-error">{errors.modelName || ""}</span>
          </div>

          <div className="cem-field">
            <label className="cem-label">
              Description
              <span className="cem-optional"> (Optional) Maximum 100 characters.</span>
            </label>

            <textarea
              className="cem-textarea"
              name="modelDescription"
              placeholder="Enter model description"
              rows={1}
              maxLength={100}
              value={form.modelDescription}
              
              onChange={handleChange}
            />
            <span className="cem-error">{errors.modelDescription || ""}</span>
          </div>

          <div className="cem-field">
            <label className="cem-label">Document Type</label>
            <select
              className={`cem-select${errors.documentType ? " error" : ""}`}
              name="documentType"
              value={form.documentType}
            
              onChange={handleChange}
            >
              <option value="invoice">Invoice</option>
              <option value="receipt">Receipt</option>
              <option value="contract">Contract</option>
              <option value="other">Other</option>
            </select>
            <span className="cem-error">{errors.documentType || ""}</span>
          </div>

          <div className="cem-field">
            <label className="cem-label">Language</label>
            <select
              className={`cem-select${errors.language ? " error" : ""}`}
              name="language"
              value={form.language}
              
              onChange={handleChange}
            >
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="zh">Chinese</option>
              <option value="japan">Japanese</option>
              <option value="korean">Korean</option>
              <option value="it">Italian</option>
              <option value="hi">Hindi</option>
            </select>
            <span className="cem-error">{errors.language || ""}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateExtractionModel;