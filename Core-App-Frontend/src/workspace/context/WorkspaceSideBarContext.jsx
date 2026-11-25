import React, { createContext, useContext, useState, useCallback } from "react";

const WorkspaceSideBarContext = createContext(null);

export function WorkspaceSideBarProvider({ children }) {
  const [mainExpanded, setMainExpanded] = useState(true);
  const [docExpanded, setDocExpanded] = useState(true);

  const collapseAll = useCallback(() => {
    setMainExpanded(false);
    setDocExpanded(false);
  }, []);

  const expandAll = useCallback(() => {
    setMainExpanded(true);
    setDocExpanded(true);
  }, []);

  const toggleMain = useCallback(() => setMainExpanded((prev) => !prev), []);
  const toggleDoc = useCallback(() => setDocExpanded((prev) => !prev), []);

  const onMainHoverEnter = useCallback(() => {}, []);
  const onMainHoverLeave = useCallback(() => {}, []);
  const onDocHoverEnter = useCallback(() => {}, []);
  const onDocHoverLeave = useCallback(() => {}, []);

  const mainVisible = true;
  const docVisible = true;

  return (
    <WorkspaceSideBarContext.Provider
      value={{
        mainExpanded,
        docExpanded,
        setMainExpanded,
        setDocExpanded,
        mainVisible,
        docVisible,
        collapseAll,
        expandAll,
        toggleMain,
        toggleDoc,
        onMainHoverEnter,
        onMainHoverLeave,
        onDocHoverEnter,
        onDocHoverLeave,
      }}
    >
      {children}
    </WorkspaceSideBarContext.Provider>
  );
}

export function useWorkspaceSideBar() {
  const ctx = useContext(WorkspaceSideBarContext);
  if (!ctx) throw new Error("useWorkspaceSideBar must be inside WorkspaceSideBarProvider");
  return ctx;
}
