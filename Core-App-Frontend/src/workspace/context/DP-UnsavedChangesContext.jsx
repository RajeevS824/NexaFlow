import { createContext, useContext, useState } from "react";

const DPUnsavedChangesContext = createContext();

export const DPUnsavedChangesProvider = ({ children }) => {
  const [isDirty, setIsDirty] = useState(false);
  const [showPopup, setShowPopup] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [saveCallback, setSaveCallback] = useState(null);
  const [discardCallback, setDiscardCallback] = useState(null);

  const checkUnsavedChanges = (action) => {
    if (isDirty) {
      setPendingAction(() => action);
      setShowPopup(true);
      return;
    }
    action();
  };

  const onSave = async () => {
    let saveSuccess = true;
    if (saveCallback) {
      const result = saveCallback();
      if (result instanceof Promise) {
        saveSuccess = await result;
      } else if (result !== undefined) {
        saveSuccess = result;
      }
    }

    setIsDirty(false);
    setShowPopup(false);

    // Navigate to the user's intended page after a successful save.
    // The save callback should return false to prevent navigation on failure.
    if (saveSuccess && pendingAction) {
      pendingAction();
    }
    setPendingAction(null);
  };

  const onDiscard = () => {
    if (discardCallback) discardCallback();

    setIsDirty(false);
    setShowPopup(false);

    if (pendingAction) pendingAction();

    setPendingAction(null);
  };

  const onCancel = () => {
    setShowPopup(false);
    setPendingAction(null);
  };

  return (
    <DPUnsavedChangesContext.Provider
      value={{
        isDirty,
        setIsDirty,
        checkUnsavedChanges,
        showPopup,
        onSave,
        onDiscard,
        onCancel,
        setSaveCallback,
        setDiscardCallback,
      }}
    >
      {children}
    </DPUnsavedChangesContext.Provider>
  );
};

export const useDPUnsavedChanges = () => useContext(DPUnsavedChangesContext);