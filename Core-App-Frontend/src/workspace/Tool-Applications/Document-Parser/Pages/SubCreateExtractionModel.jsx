import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../../../components/WorkspaceHeader";
import { API_BASE_URL, authFetch } from "../../../config/api";
import { useBasePath } from "../../../utils/useBasePath";
import "../Styles/commonstyle.css";
import "../Styles/subCreateExtractionModel.css";
import { useDPUnsavedChanges } from "../../../context/DP-UnsavedChangesContext";

const EMPTY_FIELD = { fieldName: "", fieldLabel: "", datatype: "string", required: true, aiEnabled: false, prompt: "", aliases: [],};

function getDraftStorageKey() {
  const editModelId = localStorage.getItem("editModelId");
  const tempModelName = (localStorage.getItem("tempModel_modelName") || localStorage.getItem("modelName") || "").trim();
  const tempModelKey = tempModelName || `create-${localStorage.getItem("tempModel_selectModel") || "invoice"}`;

  return editModelId ? `draftExtractionFields:${editModelId}` : `draftExtractionFields:${tempModelKey}`;
}

function saveDraftToStorage(draftState) {
  try {
    localStorage.setItem(getDraftStorageKey(), JSON.stringify(draftState));
  } catch (error) {
    console.warn("Could not save extraction draft:", error);
  }
}

function loadDraftFromStorage() {
  try {
    const stored = localStorage.getItem(getDraftStorageKey());
    if (!stored) return null;
    return JSON.parse(stored);
  } catch (error) {
    console.warn("Could not load extraction draft:", error);
    return null;
  }
}

function clearDraftFromStorage() {
  try {
    const draftKeys = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key && key.startsWith("draftExtractionFields")) {
        draftKeys.push(key);
      }
    }
    draftKeys.forEach((key) => localStorage.removeItem(key));
  } catch (error) {
    console.warn("Could not clear extraction draft:", error);
  }
}

function SubCreateExtractionModel() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docBase = `${basePath}/document-parser`;
  const [currentMode, setCurrentMode] = useState("form");
  const [activeTable, setActiveTable] = useState(null);
  const [formFields, setFormFields] = useState([]);
  const [tableFields, setTableFields] = useState({});
  const [showPropertyPanel, setShowPropertyPanel] = useState(true);
  const [editIndex, setEditIndex] = useState(null);
  const [fieldDraft, setFieldDraft] = useState({ ...EMPTY_FIELD });
  const [originalField, setOriginalField] = useState(null);
  const [isFieldDirty, setIsFieldDirty] = useState(false);
  const lastSavedModelStateRef = useRef(null);
  const [aliasInput, setAliasInput] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [hasRestoredDraft, setHasRestoredDraft] = useState(false);
  // Use refs to always have access to the latest formFields/tableFields
  // even when a callback is captured in a stale closure.
  const formFieldsRef = useRef(formFields);
  const tableFieldsRef = useRef(tableFields);

  useEffect(() => { formFieldsRef.current = formFields; }, [formFields]);
  useEffect(() => { tableFieldsRef.current = tableFields; }, [tableFields]);

  // Draft Save
  useEffect(() => {
    if (!hasRestoredDraft) return;

    saveDraftToStorage({ formFields, tableFields, currentMode, activeTable, fieldDraft, editIndex, aliasInput, showPropertyPanel });
  }, [formFields, tableFields, currentMode, activeTable, fieldDraft, editIndex, aliasInput, showPropertyPanel, hasRestoredDraft]);

  const {
    isDirty,
    setIsDirty,
    checkUnsavedChanges,
    showPopup,
    onSave,
    onDiscard,
    onCancel,
    setSaveCallback,
    setDiscardCallback,
  } = useDPUnsavedChanges();
  

  useEffect(() => {
    if (isDirty) {
      localStorage.setItem("extractionModelDirty", "true");
    } else {
      localStorage.removeItem("extractionModelDirty");
    }
  }, [isDirty]);

  const [deletePopup, setDeletePopup] = useState(null);
  const [pendingDeleteAction, setPendingDeleteAction] = useState(null);
  const [unsavedChangesPopup, setUnsavedChangesPopup] = useState(null);
  const [tableCreatePopup, setTableCreatePopup] = useState(false);
  const [tableEditPopup, setTableEditPopup] = useState(null);

  const [tableForm, setTableForm] = useState({ tableName: "", required: "true", startRows: [], endRows: [] });
  const [tableFormErrors, setTableFormErrors] = useState({});
  const [startRowInput, setStartRowInput] = useState("");
  const [endRowInput, setEndRowInput] = useState("");
  const [startRowError, setStartRowError] = useState("");
  const [endRowError, setEndRowError] = useState("");
  const [editTableForm, setEditTableForm] = useState({ tableName: "", required: "true", startRows: [], endRows: [] });
  const [editStartRowInput, setEditStartRowInput] = useState("");
  const [editEndRowInput, setEditEndRowInput] = useState("");
  const [editStartRowError, setEditStartRowError] = useState("");
  const [editEndRowError, setEditEndRowError] = useState("");
  const engineTitle = localStorage.getItem("tempModel_modelName") || localStorage.getItem("modelName") || "Extraction Engine";
  const isEditMode = !!localStorage.getItem("editModelId");
  // const [popup, setPopup] = useState(null);
  const [selectedRow, setSelectedRow] = useState(null);

  const [errors, setErrors] = useState({});

  useEffect(() => {
    const handleBrowserBack = () => {
      if (isDirty) {
        window.history.pushState(null, "", window.location.pathname);

        checkUnsavedChanges(() => {
          window.removeEventListener("popstate", handleBrowserBack);
          window.history.back();
        });
      }
    };

    window.history.pushState(null, "", window.location.pathname);

    window.addEventListener("popstate", handleBrowserBack);

    return () => {
      window.removeEventListener("popstate", handleBrowserBack);
    };
  }, [isDirty]);

  useEffect(() => {
    const editModelId = localStorage.getItem("editModelId");
    const savedDraft = loadDraftFromStorage();

    if (savedDraft) {
      setFormFields(savedDraft.formFields || []);
      setTableFields(savedDraft.tableFields || {});
      setCurrentMode(savedDraft.currentMode || "form");
      setActiveTable(savedDraft.activeTable || null);
      setFieldDraft(savedDraft.fieldDraft || { ...EMPTY_FIELD, aliases: [] });
      setEditIndex(savedDraft.editIndex ?? null);
      setAliasInput(savedDraft.aliasInput || "");
      setShowPropertyPanel(savedDraft.showPropertyPanel !== false);
      setHasRestoredDraft(true);
      return;
    }

    if (editModelId) {
      const loadExistingModel = async () => {
        try {
          const response = await authFetch(`${API_BASE_URL}/document/models`);
          const data = await response.json();
          const model = Array.isArray(data?.models)
            ? data.models.find((item) => String(item.id) === String(editModelId))
            : null;

          if (model) {
            const restoredState = {
              formFields: model.formFields || [],
              tableFields: model.tableFields || {},
              currentMode: "form",
              activeTable: null,
              fieldDraft: { ...EMPTY_FIELD, aliases: [] },
              editIndex: null,
              aliasInput: "",
              showPropertyPanel: true,
            };
            setFormFields(restoredState.formFields);
            setTableFields(restoredState.tableFields);
            setCurrentMode(restoredState.currentMode);
            setActiveTable(restoredState.activeTable);
            lastSavedModelStateRef.current = restoredState;
          }
        } catch (error) {
          console.warn("Could not load existing model for editing:", error);
        }
      };

      loadExistingModel();
    } else {
      const initialState = {
        formFields: [],
        tableFields: {},
        currentMode: "form",
        activeTable: null,
        fieldDraft: { ...EMPTY_FIELD, aliases: [] },
        editIndex: null,
        aliasInput: "",
        showPropertyPanel: true,
      };
      setFormFields(initialState.formFields);
      setTableFields(initialState.tableFields);
      setCurrentMode(initialState.currentMode);
      setActiveTable(initialState.activeTable);
      setFieldDraft(initialState.fieldDraft);
      setEditIndex(initialState.editIndex);
      setAliasInput(initialState.aliasInput);
      setShowPropertyPanel(initialState.showPropertyPanel);
      lastSavedModelStateRef.current = initialState;
    }

    setHasRestoredDraft(true);
  }, []);

  // ── mode switching ──────────────────────────────────────────────────────
  const handleAddForm = () => {
    // Reset property panel
    setFieldDraft({ ...EMPTY_FIELD });
    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);
    setIsFieldDirty(false);

    setCurrentMode("form");
    setActiveTable(null);
    setShowPropertyPanel(true);
  };

  const handleAddTable = () => {
    // Reset property panel
    setFieldDraft({ ...EMPTY_FIELD });
    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);
    setIsFieldDirty(false);

    const tables = Object.keys(tableFields);

    if (tables.length === 0) {
      openCreateTablePopup();
      return;
    }

    if (currentMode === "form" || !currentMode) {
      setCurrentMode("table");
      setActiveTable(tables[0]);
      setShowPropertyPanel(true);
      return;
    }

    openCreateTablePopup();
  };

  // ── table create popup ──────────────────────────────────────────────────
  const openCreateTablePopup = () => {
    setTableForm({ tableName: "", required: "true", startRows: [], endRows: [] });
    setStartRowInput(""); setEndRowInput(""); setTableFormErrors({});
    setTableCreatePopup(true);
  };

  const handleSaveTable = () => {
    
    const name = tableForm.tableName.trim();
    if (!name) {
      setTableFormErrors({
        tableName: "Table Name is mandatory.",
      });
      return;
    }

    const isDuplicate = Object.keys(tableFields).some(
      (table) => table.trim().toLowerCase() === name.trim().toLowerCase()
    );

    if (isDuplicate) {
      setTableFormErrors({
        tableName: "Table Name already exists. Please enter a unique Table Name.",
      });
      return;
    }
    const newTable = { tableName: name, startRows: [...tableForm.startRows], endRows: [...tableForm.endRows], required: tableForm.required === "true", fields: [] };
    setTableFields((prev) => ({ ...prev, [name]: newTable }));
    setIsDirty(true);
    setActiveTable(name);
    setCurrentMode("table");
    setShowPropertyPanel(false);
    setTableCreatePopup(false);
  };

  // ── table edit popup ────────────────────────────────────────────────────
  const openEditTablePopup = (tableName) => {
    const td = tableFields[tableName];
    setEditTableForm({ tableName, required: String(td.required), startRows: [...(td.startRows || [])], endRows: [...(td.endRows || [])] });
    setEditStartRowError("");
    setEditEndRowInput("");
    setEditEndRowError("");
    setTableEditPopup(tableName);
  };

  const handleSaveEditTable = () => {
    
    const oldName = tableEditPopup;
    const newName = editTableForm.tableName.trim();
    if (!newName || (tableFields[newName] && newName !== oldName)) return;
    const updated = { tableName: newName, startRows: [...editTableForm.startRows], endRows: [...editTableForm.endRows], required: editTableForm.required === "true", fields: tableFields[oldName].fields };
    setTableFields((prev) => { const copy = { ...prev }; delete copy[oldName]; copy[newName] = updated; return copy; });
    setIsDirty(true);
    setActiveTable(newName);
    setTableEditPopup(null);
  };

  // ── field CRUD ──────────────────────────────────────────────────────────
  const openAddField = () => {
    
    setFieldDraft({ ...EMPTY_FIELD, aliases: [] });
    setOriginalField(null);
    setAliasInput(""); setEditIndex(null); setFieldErrors({});
    setIsFieldDirty(false);
    setShowPropertyPanel(true);
  };

  const openEditField = (index) => {
    const data =
      currentMode === "form"
        ? formFields
        : (tableFields[activeTable]?.fields ?? []);

    const f = data[index];
    if (!f) return;
    const copy = {
      ...f,
      aliases: [...f.aliases],
    };

    setOriginalField(copy);      // Store original data
    setFieldDraft(copy);

    setAliasInput("");
    setEditIndex(index);
    setFieldErrors({});
    setIsFieldDirty(false);
    setShowPropertyPanel(true);
  };

  const requestEditField = (index, event) => {
    if (event) {
      event.stopPropagation();
    }

    if (hasPendingFieldDraft()) {
      setUnsavedChangesPopup({ type: "edit-field", index });
      return;
    }

    openEditField(index);
  };

  const requestSwitchMode = (mode) => {
    if (hasPendingFieldDraft()) {
      setUnsavedChangesPopup({ type: "switch-mode", mode });
      return;
    }

    if (mode === "form") {
      handleAddForm();
    } else {
      handleAddTable();
    }
  };

  const requestSwitchToTable = (tableName) => {
    if (hasPendingFieldDraft()) {
      setUnsavedChangesPopup({ type: "switch-table", targetTable: tableName });
      return;
    }

    switchToTable(tableName);
  };

  const normalizeFieldSnapshot = (field = {}) => ({
    fieldName: (field.fieldName || "").trim(),
    fieldLabel: (field.fieldLabel || "").trim(),
    datatype: (field.datatype || "string").toLowerCase(),
    required: !!field.required,
    aiEnabled: !!field.aiEnabled,
    prompt: (field.prompt || "").trim(),
    aliases: Array.isArray(field.aliases)
      ? field.aliases.map((alias) => String(alias).trim()).filter(Boolean)
      : [],
  });

  const getCurrentModelSnapshot = () => ({
    formFields,
    tableFields,
    currentMode,
    activeTable,
    fieldDraft: {
      ...fieldDraft,
      aliases: [...(fieldDraft.aliases || [])],
    },
    editIndex,
    aliasInput,
    showPropertyPanel,
  });

  const hasPendingFieldDraft = () => isFieldDirty;

  useEffect(() => {
    const baseline = editIndex !== null && originalField
      ? normalizeFieldSnapshot(originalField)
      : normalizeFieldSnapshot(EMPTY_FIELD);
    const current = normalizeFieldSnapshot(fieldDraft);

    setIsFieldDirty(JSON.stringify(current) !== JSON.stringify(baseline));
  }, [fieldDraft, editIndex, originalField]);

  const handleSaveField = () => {
  
    const errs = {};
    if (!fieldDraft.fieldName.trim()) errs.fieldName = true;
    if (!fieldDraft.fieldLabel.trim()) errs.fieldLabel = true;
    if (fieldDraft.aiEnabled && !fieldDraft.prompt.trim()) errs.prompt = true;
    if (Object.keys(errs).length) { setFieldErrors(errs); return { success: false }; }

    const duplicateName = currentFields.some(
      (field, index) =>
        index !== editIndex &&
        field.fieldName.trim().toLowerCase() ===
          fieldDraft.fieldName.trim().toLowerCase()
    );

    const duplicateLabel = currentFields.some(
      (field, index) =>
        index !== editIndex &&
        field.fieldLabel.trim().toLowerCase() ===
          fieldDraft.fieldLabel.trim().toLowerCase()
    );

    if (duplicateName || duplicateLabel) {
      setFieldErrors((prev) => ({
        ...prev,
        fieldName: duplicateName
          ? currentMode === "form"
            ? "Field Name already exists. Please enter a unique Field Name."
            : "Column Name already exists. Please enter a unique Column Name."
          : "",

        fieldLabel: duplicateLabel
          ? currentMode === "form"
            ? "Field Label already exists. Please enter a unique Field Label."
            : "Column Label already exists. Please enter a unique Column Label."
          : "",
      }));

      return { success: false };
    }

    let nextFormFields = formFields;
    let nextTableFields = tableFields;

    // Save field
    if (currentMode === "form") {
      nextFormFields = [...formFields];

      if (editIndex !== null) {
        nextFormFields[editIndex] = { ...fieldDraft };
      } else {
        nextFormFields.push({ ...fieldDraft });
      }

      setFormFields(nextFormFields);
    } else {
      nextTableFields = { ...tableFields };
      if (!nextTableFields[activeTable]) {
        return { success: false };
      }

      const fields = [...(nextTableFields[activeTable].fields || [])];

      if (editIndex !== null) {
        fields[editIndex] = { ...fieldDraft };
      } else {
        fields.push({ ...fieldDraft });
      }

      nextTableFields[activeTable] = {
        ...nextTableFields[activeTable],
        fields,
      };

      setTableFields(nextTableFields);
    }
    // Reset form after successful Add/Update
    setFieldDraft({ ...EMPTY_FIELD });
    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);
    setOriginalField(null);

    lastSavedModelStateRef.current = {
      formFields: nextFormFields,
      tableFields: nextTableFields,
      currentMode,
      activeTable,
      fieldDraft: { ...EMPTY_FIELD, aliases: [] },
      editIndex: null,
      aliasInput: "",
      showPropertyPanel: true,
    };

    // Keep page dirty until Save & Close
    setIsDirty(true);

    // Keep the property panel open for adding the next field
    setShowPropertyPanel(true);
    setShowPropertyPanel(true);
    setIsFieldDirty(false);

    return { success: true, formFields: nextFormFields, tableFields: nextTableFields };
  };

  
  const handleCancelField = () => {
    

    if (editIndex !== null && originalField) {
      // Editing -> restore original field
      setFieldDraft({
        ...originalField,
        aliases: [...originalField.aliases],
      });

      setAliasInput("");
      setFieldErrors({});

      // Keep dirty if any form/table data already exists
      const hasUnsavedData =
        formFields.length > 0 ||
        Object.keys(tableFields).length > 0;

      setIsDirty(hasUnsavedData);

      localStorage.removeItem("fieldDirty");
      return;
    }

    // Add mode -> clear current field
    setFieldDraft({ ...EMPTY_FIELD });
    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);

    // Keep dirty if any form/table data already exists
    const hasUnsavedData =
      formFields.length > 0 ||
      Object.keys(tableFields).length > 0;

    setIsDirty(hasUnsavedData);

    localStorage.removeItem("fieldDirty");
  };

  const handleDiscard = () => {
    setFieldDraft({ ...EMPTY_FIELD });

    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);
    setIsFieldDirty(false);

    setFormFields([]);
    setTableFields({});
    setCurrentMode("form");
    setActiveTable(null);
    setShowPropertyPanel(false);
    setIsDirty(false);
    localStorage.removeItem("fieldDirty");
    clearDraftFromStorage();
  };

  const handleSaveCloseRequest = () => {
    // Only show popup when the current property panel has unsaved changes.
    if (hasPendingFieldDraft()) {
      setUnsavedChangesPopup({ type: "save-close" });
      return;
    }

    handleSubmit();
  };

  const switchToTable = (tableName) => {
    if (!tableName || tableName === activeTable) return;

    setActiveTable(tableName);
    setCurrentMode("table");
    setFieldDraft({ ...EMPTY_FIELD, aliases: [] });
    setAliasInput("");
    setFieldErrors({});
    setEditIndex(null);
    setOriginalField(null);
    setIsFieldDirty(false);
    setShowPropertyPanel(true);
  };

  const handleUnsavedChangesPopupAction = (action) => {
    const popup = unsavedChangesPopup;

    if (action === "save") {
      const saved = handleSaveField();
      if (!saved?.success) return;
      setUnsavedChangesPopup(null);
      if (popup?.type === "save-close") {
        handleSubmit(saved.formFields, saved.tableFields);
      } else if (popup?.type === "close") {
        navigate(`${docBase}/create-process-model`);
      } else if (popup?.type === "switch-table") {
        switchToTable(popup.targetTable);
      } else if (popup?.type === "edit-field") {
        openEditField(popup.index);
      } else if (popup?.type === "switch-mode") {
        if (popup.mode === "form") {
          handleAddForm();
        } else {
          handleAddTable();
        }
      }
      return;
    }

    if (action === "discard") {
      const savedState = lastSavedModelStateRef.current;
      if (savedState) {
        setFormFields(savedState.formFields || []);
        setTableFields(savedState.tableFields || {});
        setCurrentMode(savedState.currentMode || "form");
        setActiveTable(savedState.activeTable || null);
        setFieldDraft(savedState.fieldDraft || { ...EMPTY_FIELD, aliases: [] });
        setEditIndex(savedState.editIndex ?? null);
        setAliasInput(savedState.aliasInput || "");
        setShowPropertyPanel(savedState.showPropertyPanel !== false);
        setFieldErrors({});
        setOriginalField(null);
        setIsFieldDirty(false);
        setIsDirty(false);
      } else {
        setFieldDraft({ ...EMPTY_FIELD, aliases: [] });
        setAliasInput("");
        setFieldErrors({});
        setEditIndex(null);
        setOriginalField(null);
        setIsFieldDirty(false);
        setIsDirty(false);
      }
      setUnsavedChangesPopup(null);
      if (popup?.type === "save-close") {
        handleSubmit(savedState?.formFields || formFields, savedState?.tableFields || tableFields);
      } else if (popup?.type === "close") {
        navigate(`${docBase}/create-process-model`);
      } else if (popup?.type === "switch-table") {
        switchToTable(popup.targetTable);
      } else if (popup?.type === "edit-field") {
        openEditField(popup.index);
      } else if (popup?.type === "switch-mode") {
        if (popup.mode === "form") {
          handleAddForm();
        } else {
          handleAddTable();
        }
      }
      return;
    }

    setUnsavedChangesPopup(null);
  };

  const addAlias = () => {
    const alias = aliasInput.trim();

    if (!alias) return;

    // Check current field
    if (
      fieldDraft.aliases.some(
        (a) => a.toLowerCase() === alias.toLowerCase()
      )
    ) {
      setFieldErrors((prev) => ({
        ...prev,
        alias: "Alias already exists. Please enter a unique alias.",
      }));


      return;
    }
    setIsDirty(true);

    setFieldDraft((prev) => ({
      ...prev,
      aliases: [...prev.aliases, alias],
    }));

    setAliasInput("");
  };





 

 

  const handleDeleteField = (index) => {
    setDeletePopup({ type: "field", index });
  };

  const handleDeleteTable = (tableName) => {
    setDeletePopup({ type: "table", tableName });
  };

  const confirmDelete = () => {
    if (!deletePopup) return;

    if (deletePopup.type === "field") {
      // Reset property panel state so it doesn't show deleted field's data
      setFieldDraft({ ...EMPTY_FIELD, aliases: [] });
      setAliasInput("");
      setFieldErrors({});
      setEditIndex(null);
      setOriginalField(null);
      setIsFieldDirty(false);
      setSelectedRow(null);

      if (currentMode === "form") {
        setFormFields(prev =>
          prev.filter((_, i) => i !== deletePopup.index)
        );
      } else {
        setTableFields(prev => {
          if (!prev[activeTable]) return prev;

          return {
            ...prev,
            [activeTable]: {
              ...prev[activeTable],
              fields: prev[activeTable].fields.filter(
                (_, i) => i !== deletePopup.index
              ),
            },
          };
        });
      }
    } else {
      setTableFields(prev => {
        const copy = { ...prev };

        delete copy[deletePopup.tableName];

        const remainingTables = Object.keys(copy);

        if (remainingTables.length > 0) {
          setActiveTable(remainingTables[0]);
          setCurrentMode("table");
        } else {
          setActiveTable(null);
          setCurrentMode("form");
        }

        return copy;
      });
    }

    setDeletePopup(null);
    setPendingDeleteAction(null);
    setIsDirty(true);
    };
  // Register saveCallback so the unsaved changes popup's Save button
  // persists all field data before navigating to the user's intended page.
  useEffect(() => {
    setSaveCallback(() => async () => {
      try {
        await handleSubmit(formFieldsRef.current, tableFieldsRef.current, true);
        return true;
      } catch {
        return false;
      }
    });
  }, []);

  // ── submit / close ──────────────────────────────────────────────────────
  const handleSubmit = async (nextFormFields = formFields, nextTableFields = tableFields, skipNavigation = false) => {
    
    const today = new Date();
    const formattedDate = [String(today.getDate()).padStart(2,"0"), String(today.getMonth()+1).padStart(2,"0"), today.getFullYear()].join("-");
    const docTypeRaw = localStorage.getItem("tempModel_documentType") || "invoice";
    const docType = docTypeRaw.charAt(0).toUpperCase() + docTypeRaw.slice(1);
    const modelName = localStorage.getItem("tempModel_modelName") || "Unnamed Model";
    const editModelId = localStorage.getItem("editModelId");
    // Normalize fields to the backend schema: booleans for `required`,
    // consistent datatype casing, and ensure aliases is an array.
    const normalizeField = (f) => ({
      fieldName: (f.fieldName || "").trim(),
      fieldLabel: (f.fieldLabel || "").trim(),
      datatype: (f.datatype || "string").toLowerCase(),
      required: typeof f.required === "boolean" ? f.required : String(f.required).toLowerCase() === "required" || String(f.required).toLowerCase() === "true",
      aiEnabled: !!f.aiEnabled,
      prompt: f.prompt || "",
      aliases: Array.isArray(f.aliases) ? f.aliases : [],
    });

    const normalizedFormFields = (nextFormFields || []).map(normalizeField);

    const normalizedTableFields = Object.fromEntries(
      Object.entries(nextTableFields || {}).map(([tname, t]) => [
        tname,
        {
          tableName: t.tableName || tname,
          required: !!t.required,
          startRows: Array.isArray(t.startRows) ? t.startRows : [],
          endRows: Array.isArray(t.endRows) ? t.endRows : [],
          fields: (t.fields || []).map(normalizeField),
        },
      ])
    );

    const modelPayload = {
      id: editModelId || undefined,
      name: modelName,
      engine: localStorage.getItem("tempModel_selectModel") || "OCR",
      description: localStorage.getItem("tempModel_description") || "",
      documentType: docType,
      language: localStorage.getItem("tempModel_language") || "en",
      formFields: normalizedFormFields,
      tableFields: normalizedTableFields,
      created: formattedDate,
      updated: formattedDate,
    };

    try {
      const response = await authFetch(`${API_BASE_URL}/document/models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modelPayload),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Unable to save model.");
      }

      const savedModel = result.model || modelPayload;
      localStorage.setItem("extractionModels", JSON.stringify([savedModel]));
    } catch (error) {
      console.error("Model save failed:", error);
      window.alert(error.message || "Unable to save model. Please try again.");
      return;
    }

    clearDraftFromStorage();
    ["tempModel_selectModel", "tempModel_modelName", "tempModel_description", "tempModel_documentType", "tempModel_language", "modelName", "editModelId"].forEach((k) => localStorage.removeItem(k));

    setIsDirty(false);
    lastSavedModelStateRef.current = {
      formFields: nextFormFields,
      tableFields: nextTableFields,
      currentMode,
      activeTable,
      fieldDraft: { ...EMPTY_FIELD, aliases: [] },
      editIndex: null,
      aliasInput: "",
      showPropertyPanel,
    };
    if (!skipNavigation) {
      navigate(`${docBase}/document-process-model`);
    }
  };

  const handleClose = () => {
    navigate(`${docBase}/create-process-model`);
  };
  
  const currentFields = currentMode === "form" ? formFields : currentMode === "table" && activeTable ? tableFields[activeTable]?.fields || [] : [];
  useEffect(() => {
    if (
      currentMode === "table" &&
      activeTable &&
      !tableFields[activeTable]
    ) {
      const tables = Object.keys(tableFields);

      if (tables.length > 0) {
        setActiveTable(tables[0]);
      } else {
        setCurrentMode("form");
        setActiveTable(null);
      }
    }
  }, [tableFields, activeTable, currentMode]);
  const tableNames = Object.keys(tableFields);
  const tableHeaders = currentMode === "form" ? ["Field Name","Field Label","Datatype","Aliases","Action"] : ["Column Name","Column Label","Datatype","Aliases","Action"];

  return (
    <div className="sub-page">

      {/* ── LAYER 1: Global Header — title + Submit/Close buttons ── */}
      <Header
      title={`${engineTitle || "Engine"} ${isEditMode ? "- Edit Process Fields" : "- Create Process Fields"}`}
       description={engineTitle} 
        actions={
          <>
            <button
            className="btn-primary-dp"
            onClick={handleSaveCloseRequest}
          >
            Save & Close
          </button>
            <button
              className="btn-icon-close"
              onClick={handleClose}
              title="Close"
            >
              ✕
            </button>
          </>
        }
      />

      {/* ── LAYER 2: Sticky toolbar — Add Form / Add Table + table dropdown ── */}
      <div className="sub-toolbar">
        <div className="sub-toolbar-row">
          <button
            className={`top-toggle-btn${currentMode === "form" ? " active-top-btn" : ""}`}
            onClick={() => requestSwitchMode("form")}
          >
            + Add Form
          </button>
          <button
            className={`top-toggle-btn${currentMode === "table" ? " active-top-btn" : ""}`}
            onClick={() => requestSwitchMode("table")}
          >
            + Add Table
          </button>
        

        {currentMode === "table" && tableNames.length > 0 && (
          <div className="table-tabs">
            <select
              className={`table-dropdown${tableNames.length === 1 ? " single-table-dropdown" : ""}`}
              value={activeTable || ""}
              onChange={(e) => {
                const targetTable = e.target.value;

                if (targetTable !== activeTable) {
                  requestSwitchToTable(targetTable);
                  return;
                }
              }}
            >
              {tableNames.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button
              className="edit-table-btn"
              onClick={() => {
                if (activeTable) {
                  openEditTablePopup(activeTable);
                }
              }}
          >✎</button>
            <button
              className="delete-table-btn"
              onClick={() => {
                if (activeTable) {
                  handleDeleteTable(activeTable);
                }
              }}
          >🗑</button>
          </div>

        )}
      </div>
      </div>

      {/* ── LAYER 3: Scrollable body — field list + property panel ── */}
      <div className="sub-body">
        {currentMode && (
          <div className="field-main-section">

            {/* LEFT — field list */}
            <div className="field-list-card">
              <div className="card-header">
                <h3>{currentMode === "form" ? "Form Fields" : `${activeTable || ""} Fields`}</h3>
                <div className="card-actions">
                  {/* <button className="sub-primary-btn" onClick={openAddField}>Add</button>
                  <button className="sub-secondary-btn" onClick={() => { setCurrentMode(null); setActiveTable(null); setShowPropertyPanel(false); }}>Cancel</button> */}
                </div>
              </div>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>{tableHeaders.map((h) => <th key={h}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {currentFields.length === 0 ? (
                      <tr><td colSpan={6} className="no-fields-message">No fields yet. Click Add.</td></tr>
                    ) : (
                      currentFields.map((f, i) => (
                        <tr
                          key={i}
                          className={selectedRow === i ? "selected-row" : ""}
                          onClick={() => {
                            setSelectedRow(i);
                          }}
                        >
                          <td>{f.fieldName}</td>
                          <td>{f.fieldLabel}</td>
                          <td>{f.datatype}</td>
                          {/* <td>{f.aiEnabled ? "True" : "False"}</td> */}
                          <td>{f.aliases.length}</td>
                          <td>
                            <div className="action-btn-group">
                              <button
                                className="editBtn"
                                onClick={(e) => requestEditField(i, e)}
                            >✎</button>
                              <button
                                className="deleteBtn"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteField(i);
                                }}
                            >🗑</button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* RIGHT — property panel */}
           
              <div className="field-property-card">
                <h3>
                  {currentMode === "form"
                    ? editIndex !== null
                      ? "Edit Form Field Properties"
                      : "Form Field Properties"
                    : editIndex !== null
                      ? "Edit Table Field Properties"
                      : "Table Field Properties"}
                </h3>

                <div className="input-group">
                  <label>
                    {currentMode === "form" ? "Field Name" : "Column Name"}
                  </label>

                  <input
                    type="text"
                    className={fieldErrors.fieldName ? "error-input" : ""}
                    value={fieldDraft.fieldName}
                    onChange={(e) => {
                      setIsDirty(true);
                      // localStorage.setItem("fieldDirty", "true");

                      setFieldDraft((p) => ({
                        ...p,
                        fieldName: e.target.value,
                      }));

                      setFieldErrors((p) => ({
                        ...p,
                        fieldName: false,
                      }));
                    }}
                  />

                  {fieldErrors.fieldName && (
                    <span className="mandatory-error">
                      {fieldErrors.fieldName === true
                        ? currentMode === "form"
                          ? "This is mandatory field name"
                          : "This is mandatory column name"
                        : fieldErrors.fieldName}
                    </span>
                  )}
                </div>

                <div className="input-group">
                  <label>
                    {currentMode === "form" ? "Field Label" : "Column Label"}
                  </label>

                  <input
                    type="text"
                    className={fieldErrors.fieldLabel ? "error-input" : ""}
                    value={fieldDraft.fieldLabel}
                    onChange={(e) => {
                      setIsDirty(true);
                      // localStorage.setItem("fieldDirty", "true");

                      setFieldDraft((p) => ({
                        ...p,
                        fieldLabel: e.target.value,
                      }));

                      setFieldErrors((p) => ({
                        ...p,
                        fieldLabel: false,
                      }));
                    }}
                  />

                  {fieldErrors.fieldLabel && (
                    <span className="mandatory-error">
                      {fieldErrors.fieldLabel === true
                        ? currentMode === "form"
                          ? "This is mandatory field label"
                          : "This is mandatory column label"
                        : fieldErrors.fieldLabel}
                    </span>
                  )}
                </div>

                <div className="input-group">
                  <label>Datatype</label>
                  <select value={fieldDraft.datatype} onChange={(e) => {
                    setIsDirty(true);
                    // localStorage.setItem("fieldDirty", "true");
                    setFieldDraft((p) => ({
                        ...p,
                        datatype: e.target.value
                    }));
                }}>
                    <option>String</option><option>Number</option><option>Date</option>
                  </select>
                </div>

                

                {/* <span className="section-label">Required Field</span> */}
                <div className="required-wrapper">
                  {/* {["Required","Optional"].map((v) => (
                    <label key={v}><input type="radio" name="required" value={v} checked={fieldDraft.required === v} onChange={(e) => setFieldDraft((p) => ({ ...p, required: e.target.value }))} />{v}</label>
                  ))} */}
                  
                  <input
                  type="checkbox"
                  checked={
                    fieldDraft.required === true ||
                    fieldDraft.required === "Required"
                  }
                  onChange={(e)=>{

                    setIsDirty(true);
                    // localStorage.setItem("fieldDirty", "true");
                    setFieldDraft(p=>({
                        ...p,
                        required: e.target.checked
                    }));

                }}
              />
              <span className="section-label">Required Field</span>
                </div>

                
                <div className="required-wrapper">
                  {/* <label><input type="radio" name="aiOption" value="false" checked={!fieldDraft.aiEnabled} onChange={() => setFieldDraft((p) => ({ ...p, aiEnabled: false, prompt: "" }))} />AI False</label>
                  <label><input type="radio" name="aiOption" value="true"  checked={fieldDraft.aiEnabled}  onChange={() => setFieldDraft((p) => ({ ...p, aiEnabled: true }))} />AI True</label> */}
                  {/* <input
                    type="checkbox"
                    checked={fieldDraft.aiEnabled}
                    onChange={(e)=>{

                      setIsDirty(true);
                      // localStorage.setItem("fieldDirty", "true");
                      setFieldDraft(p=>({
                          ...p,
                          aiEnabled:e.target.checked
                      }));

                  }}

                /> */}
                {/* <span className="section-label">AI</span> */}
                
                </div>

                {fieldDraft.aiEnabled && (
                  <div className="input-group">
                    <label>Prompt</label>

                    <input
                      type="text"
                      placeholder="Enter AI Prompt"
                      className={fieldErrors.prompt ? "error-input" : ""}
                      value={fieldDraft.prompt}
                      onChange={(e) => {
                        setIsDirty(true);
                        // localStorage.setItem("fieldDirty", "true");

                        setFieldDraft((p) => ({
                          ...p,
                          prompt: e.target.value
                        }));

                        setFieldErrors((p) => ({
                          ...p,
                          prompt: false
                        }));
                      }}
                    />

                    {fieldErrors.prompt && (
                      <span className="mandatory-error">
                        This is mandatory AI prompt
                      </span>
                    )}
                  </div>
                )}

                <div className="alias-section">
                  <label>Aliases</label>
                  <div className="alias-input-box">
                    <input
                      type="text"
                      value={aliasInput}
                      className={fieldErrors.alias ? "error-input" : ""}
                      onChange={(e) => {
                        setIsDirty(true);
                        setAliasInput(e.target.value);

                        setFieldErrors((prev) => ({
                          ...prev,
                          alias: "",
                        }));
                      }}
                    />

                    
                    <button
                      className="sub-primary-btn"
                      onClick={addAlias}
                    >
                      Add
                    </button>
                  </div>

                  {fieldErrors.alias && (
                      <span className="mandatory-error">
                        {fieldErrors.alias}
                      </span>
                    )}
                    
                  <div className="alias-list">
                    {fieldDraft.aliases.map((a, i) => (
                      <div key={i} className="alias-chip">{a}<span onClick={() => {

                        setIsDirty(true);
                        // localStorage.setItem("fieldDirty", "true");
                        setFieldDraft((p) => ({
                            ...p,
                            aliases: p.aliases.filter((_, j) => j !== i)
                        }));

                    }} >✕</span></div>
                    ))}
                  </div>
                </div>
{/* --------------------------------------------------- */}
                <div className="save-wrapper">
                  <button
                    className="sub-primary-btn"
                    onClick={handleSaveField}
                  >
                    {editIndex !== null ? "Update" : "Add"}
                  </button>

                  <button
                    className="sub-secondary-btn"
                    onClick={handleCancelField}
                  >
                    Reset
                  </button>
                </div>
              </div>
          
          </div>
        )}
      </div>

      {/* ── POPUPS ── */}

      {pendingDeleteAction && (
        <div className="delete-popup">
          <div className="delete-popup-card">
            <h3>Unsaved Changes</h3>
            <p>You have unsaved field changes. Do you want to save them before deleting?</p>
            <div className="delete-popup-actions">
              <button className="sub-secondary-btn" onClick={() => setPendingDeleteAction(null)}>Cancel</button>
              <button className="sub-secondary-btn" onClick={() => {
                const saved = handleSaveField();
                if (!saved) return;
                setPendingDeleteAction(null);
                setDeletePopup(pendingDeleteAction);
              }}>Save</button>
              <button className="danger-btn popup-danger-btn" onClick={() => {
                setFieldDraft({ ...EMPTY_FIELD, aliases: [] });
                setAliasInput("");
                setFieldErrors({});
                setEditIndex(null);
                setOriginalField(null);
                setPendingDeleteAction(null);
                setDeletePopup(pendingDeleteAction);
              }}>Discard</button>
            </div>
          </div>
        </div>
      )}

      {unsavedChangesPopup && (
        <div className="delete-popup">
          <div className="delete-popup-card">
            <h3>Unsaved Changes</h3>
            <p className="popup-preline">
              {unsavedChangesPopup.type === "switch-table"
                ? "You have unsaved changes in the current table.\n\nWhat would you like to do?"
                : "You have unsaved changes.\n\nWhat would you like to do?"}
            </p>
            <div className="delete-popup-actions">
              <button className="sub-secondary-btn" onClick={() => handleUnsavedChangesPopupAction("cancel")}>Cancel</button>
              <button className="sub-secondary-btn" onClick={() => handleUnsavedChangesPopupAction("save")}>Save</button>
              <button className="danger-btn popup-danger-btn" onClick={() => handleUnsavedChangesPopupAction("discard")}>Discard</button>
            </div>
          </div>
        </div>
      )}

      {deletePopup && (
        <div className="delete-popup">
          <div className="delete-popup-card">
            <h3>Delete</h3>
            <p>{deletePopup.type === "field" ? "Are you sure you want to delete this field?" : `Are you sure you want to delete ${deletePopup.tableName}?`}</p>
            <div className="delete-popup-actions">
              <button className="sub-secondary-btn" onClick={() => setDeletePopup(null)}>Cancel</button>
              <button className="danger-btn popup-danger-btn" onClick={confirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {tableCreatePopup && (
        <div className="delete-popup">
          <div className="delete-popup-card">
            <h3>Create Table</h3>
            <div className="input-group">
              <label>Table Name</label>
              <input type="text" className={tableFormErrors.tableName ? "error-input" : ""} placeholder="Enter table name" value={tableForm.tableName} onChange={(e) => { setIsDirty(true); setTableForm((p) => ({ ...p, tableName: e.target.value })); setTableFormErrors({}); }} />
              {tableFormErrors.tableName && (
                <span className="mandatory-error">
                  {tableFormErrors.tableName}
                </span>
              )}
            </div>
            <TableRowsInput label="Table Start Identifier" rows={tableForm.startRows} inputValue={startRowInput} onInputChange={(value) => {
                setStartRowInput(value);
                setStartRowError("");
              }} 
              onAdd={() => {
                const value = startRowInput.trim();

                if (!value) return;

                if (
                  tableForm.startRows.some(
                    row => row.trim().toLowerCase() === value.toLowerCase()
                  )
                ) {
                  setStartRowError(
                    "Start Identifier already exists. Please enter a unique identifier."
                  );
                  return;
                }

                setTableForm((p) => ({
                  ...p,
                  startRows: [...p.startRows, value]
                }));

                setStartRowInput("");
                setStartRowError("");
              }}
              onRemove={(i) => setTableForm((p) => ({ ...p, startRows: p.startRows.filter((_, j) => j !== i) }))} 
              error={startRowError} />
            <TableRowsInput label="Table End Identifier" rows={tableForm.endRows} inputValue={endRowInput} onInputChange={(value)=>{
                  setEndRowInput(value);
                  setEndRowError("");
              }} 
              onAdd={() => {
                const value = endRowInput.trim();

                if (!value) return;

                if (
                  tableForm.endRows.some(
                    row => row.trim().toLowerCase() === value.toLowerCase()
                  )
                ) {
                  setEndRowError(
                    "End Identifier already exists. Please enter a unique identifier."
                  );
                  return;
                }

                setTableForm((p) => ({
                  ...p,
                  endRows: [...p.endRows, value]
                }));

                setEndRowInput("");
                setEndRowError("");
              }}
              onRemove={(i) => setTableForm((p) => ({ ...p, endRows:   p.endRows.filter((_, j) => j !== i) }))} 
              error={endRowError} />
            <div className="required-wrapper table-required-wrapper">
              <input
                type="checkbox"
                checked={tableForm.required === "true"}
                onChange={(e) => {
                  setTableForm((p) => ({
                    ...p,
                    required: e.target.checked ? "true" : "false",
                  }));
                }}
              />
              <span className="section-label">Required Table</span>
            </div>
            <div className="delete-popup-actions">
              <button
                className="sub-secondary-btn"
                onClick={() => setTableCreatePopup(false)}
            >Cancel</button>
              <button className="sub-primary-btn" onClick={handleSaveTable}>Save</button>
            </div>
          </div>
        </div>
      )}

      {tableEditPopup && (
        <div className="delete-popup">
          <div className="delete-popup-card">
            <h3>Edit Table</h3>
            <div className="input-group">
              <label>Table Name</label>
              <input type="text" value={editTableForm.tableName} onChange={(e) =>{ setIsDirty(true); setEditTableForm((p) => ({ ...p, tableName: e.target.value }))}} />
            </div>
            <TableRowsInput label="Table Start Identifier" rows={editTableForm.startRows} inputValue={editStartRowInput} onInputChange={(value)=>{
                  setEditStartRowInput(value);
                  setEditStartRowError("");
              }} onAdd={() => {
              const value = editStartRowInput.trim();
              if (!value) return;

              if (
                editTableForm.startRows.some(
                  (row) => row.trim().toLowerCase() === value.toLowerCase()
                )
              ) {
                setEditStartRowError(
                    "Start Identifier already exists. Please enter a unique identifier."
                );
                return;
              }

              setEditTableForm((p) => ({
                ...p,
                startRows: [...p.startRows, value],
              }));

              setEditStartRowInput("");
              setEditStartRowError("");
            }} onRemove={(i) => setEditTableForm((p) => ({ ...p, startRows: p.startRows.filter((_, j) => j !== i) }))} 
            error={editStartRowError} />
            <TableRowsInput label="Table End Identifier" rows={editTableForm.endRows} inputValue={editEndRowInput} 
                onInputChange={(value) => {
                  setEditEndRowInput(value);
                  setEditEndRowError("");
                }} 
                onAdd={() => {
                  const value = editEndRowInput.trim();
                  if (!value) return;

                  if (
                    editTableForm.endRows.some(
                      (row) => row.trim().toLowerCase() === value.toLowerCase()
                    )
                  ) {
                    setEditEndRowError(
                        "End Identifier already exists. Please enter a unique identifier."
                    );
                    return;
                  }

                  setEditTableForm((p) => ({
                    ...p,
                    endRows: [...p.endRows, value],
                  }));

                  setEditEndRowInput("");
                  setEditEndRowError("");
                  
                }} onRemove={(i) => setEditTableForm((p) => ({ ...p, endRows:   p.endRows.filter((_, j) => j !== i) }))} 
                error={editEndRowError} />
            <div className="required-wrapper table-required-wrapper">
              <input
                type="checkbox"
                checked={editTableForm.required === "true"}
                onChange={(e) => {
                  setEditTableForm((p) => ({
                    ...p,
                    required: e.target.checked ? "true" : "false",
                  }));
                }}
              />
              <span className="section-label">Required Table</span>
            </div>
            <div className="delete-popup-actions">
              <button
                className="sub-secondary-btn"
                onClick={() => setTableEditPopup(null)}
            >Cancel</button>
              <button className="sub-primary-btn" onClick={handleSaveEditTable}>Save</button>
            </div>
          </div>
        </div>
      )}
        {showPopup && (
          <div className="delete-popup">
            <div className="delete-popup-card">

              <h3>Unsaved Changes</h3>

              <p>
                You have unsaved changes.
                <br />
                Do you want to save them before continuing?
              </p>

              <div className="delete-popup-actions">

                <button
                  className="sub-primary-btn"
                  onClick={onSave}
                >
                  Save
                </button>

                <button
                  className="danger-btn"
                  onClick={onDiscard}
                >
                  Discard
                </button>

                <button
                  className="sub-secondary-btn"
                  onClick={onCancel}
                >
                  Cancel
                </button>

            </div>

            </div>
          </div>
        )}

    </div>
  );
}

function TableRowsInput({ label, rows, inputValue, onInputChange, onAdd, onRemove, error, }) {
  return (
    <div className="alias-section table-rows-section">
      <label>{label}</label>
      <div className="alias-input-box">
        <input
          type="text"
          className={error ? "error-input" : ""}
          placeholder={
            label === "Table Start Identifier"
              ? "Enter the text or heading where the table starts"
              : label === "Table End Identifier"
              ? "Enter the text or heading where the table ends"
              : `Enter ${label.toLowerCase()}`
          }
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onAdd();
          }}
        />
        <button className="sub-primary-btn" type="button" onClick={onAdd}>Add</button>
      </div>
      {error && (
          <span className="mandatory-error">
              {error}
          </span>
      )}
      <div className="alias-list">
        {rows.map((r, i) => (
          <div key={i} className="alias-chip">{r}<span onClick={() => onRemove(i)}>✕</span></div>
        ))}
      </div>
    </div>
  );
}

export default SubCreateExtractionModel;
