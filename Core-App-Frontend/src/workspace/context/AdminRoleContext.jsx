/**
 * workspace/context/AdminRoleContext.jsx
 * ------------------------------------------------------------
 * Holds the list of Roles an admin has created (Manage > Role)
 * plus which users are assigned to each one (Manage > Users),
 * so both admin screens read/write the same shared state instead
 * of drifting apart.
 *
 * Now backed by the real FastAPI + MS SQL backend via apiFetch.
 *
 * NOTE: The backend stores Role.status as a boolean, while the UI
 * uses the strings "active"/"inactive". All conversions happen here
 * so the rest of the app keeps using string statuses.
 * ------------------------------------------------------------
 */

import { createContext, useContext, useState, useCallback, useEffect } from "react";

import { apiFetch } from "../../services/api";
import { useAuth } from "../../context/AuthContext.jsx";

const AdminRoleContext = createContext(null);

/** Convert a backend status (boolean or string) to the UI string status. */
function toUiStatus(status) {
  if (typeof status === "string") {
    return status.toLowerCase() === "inactive" ? "inactive" : "active";
  }
  return status ? "active" : "inactive";
}

/** Convert a UI string status ("active"/"inactive") to a boolean for the backend. */
function toBackendStatus(status) {
  return status !== "inactive";
}

export function AdminRoleProvider({ children }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [roles, setRoles] = useState([]);
  const [usersCache, setUsersCache] = useState([]);
  const [loading, setLoading] = useState(isAdmin);

  const loadRoles = useCallback(async () => {
    if (!isAdmin) {
      setRoles([]);
      setLoading(false);
      return;
    }
    try {
      const data = await apiFetch("/api/admin/roles");
      // Backend returns status as a boolean; UI expects "active"/"inactive".
      setRoles(
        (data || []).map((r) => ({
          ...r,
          status: toUiStatus(r.status),
        }))
      );
    } catch (err) {
      console.error("Failed to load roles:", err);
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  const loadUsers = useCallback(async () => {
    if (!isAdmin) {
      setUsersCache([]);
      return;
    }
    try {
      const data = await apiFetch("/api/admin/users");
      setUsersCache(data || []);
    } catch (err) {
      console.error("Failed to load users:", err);
    }
  }, [isAdmin]);

  // Load roles and users from backend on mount only when signed in as an admin
  useEffect(() => {
    if (!isAdmin) {
      setRoles([]);
      setUsersCache([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    loadRoles();
    loadUsers();
  }, [isAdmin, loadRoles, loadUsers]);

  async function addRole(name, description, status = "active") {
    const payload = {
      name,
      description,
      status: toBackendStatus(status), // string -> boolean
    };
    const data = await apiFetch("/api/admin/roles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await loadRoles();
    return data;
  }

  async function updateRole(id, patch) {
    const payload = {};
    if (patch.name !== undefined) payload.name = patch.name;
    if (patch.description !== undefined) payload.description = patch.description;
    if (patch.status !== undefined) payload.status = toBackendStatus(patch.status); // string -> boolean

    await apiFetch(`/api/admin/roles/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    await loadRoles();
  }

  async function deleteRole(id) {
    await apiFetch(`/api/admin/roles/${id}`, { method: "DELETE" });
    setRoles((prev) => prev.filter((r) => r.id !== id));
    // The backend cascade-deletes UserRole rows for this role, so refresh
    // the users cache from the server instead of guessing the new state.
    await loadUsers();
  }

const getAssignedCount = useCallback(
    (roleName) => {
      // Prefer the backend's authoritative per-role assigned count
      // (computed in list_roles via a SQL subquery on UserRole). This
      // avoids depending on the client-side usersCache which may not
      // reliably carry the role name in every user object.
      const role = roles.find((r) => r.name === roleName);
      if (role && typeof role.assigned_count === "number") {
        return role.assigned_count;
      }
      // Fallback: count from the users cache by matching role name.
      // NOTE: the backend returns each user's role name as `role_group`
      // (snake_case) - not `roleGroup` - this must match that field.
      return usersCache.filter((u) => u.role !== "admin" && u.role_group === roleName).length;
    },
    [roles, usersCache]
  );

  const getAssignedUsers = useCallback(
    (roleName) => {
      return usersCache.filter((u) => u.role !== "admin" && u.role_group === roleName);
    },
    [usersCache]
  );

  return (
    <AdminRoleContext.Provider
      value={{
        roles,
        usersCache,
        loading,
        addRole,
        updateRole,
        deleteRole,
        getAssignedCount,
        getAssignedUsers,
        setUsersCache,
        refresh: () => {
          loadRoles();
          loadUsers();
        },
      }}
    >
      {children}
    </AdminRoleContext.Provider>
  );
}

export function useAdminRole() {
  return useContext(AdminRoleContext);
}
