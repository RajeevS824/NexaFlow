/**
 * workspace/pages/RolePermission.jsx
 * ------------------------------------------------------------
 * Admin-only "Role Permission" page (Manage > Role Permission).
 *
 * Flow:
 *   1. Select a Role from the dropdown (populated from
 *      Manage > Role).
 *   2. The page shows every product this org has purchased.
 *   3. For each product, the admin can toggle individual
 *      permissions (view, create, edit, delete, export, etc.).
 *   4. Save writes the permission set to the backend.
 *
 * Now backed by the real FastAPI + MS SQL backend via apiFetch.
 * ------------------------------------------------------------
 */

import React, { useState, useEffect, useMemo } from "react";
import { FaSave, FaUndo, FaCheckCircle } from "react-icons/fa";

import Header from "../../../components/WorkspaceHeader";
import { useAdminRole } from "../../../context/AdminRoleContext";
import { apiFetch } from "../../../../services/api";
import "../../../styles/manage.css";

// Matches the backend's RoleProductAccess columns exactly (CanView,
// CanEdit, CanExecute) - the previous Create/Delete/Import/Share/Admin
// columns had no corresponding database columns, so toggling them never
// actually persisted anything.
const PERMISSION_KEYS = [
  { key: "view", label: "View" },
  { key: "edit", label: "Edit" },
  { key: "execute", label: "Execute" },
];

export default function RolePermission() {
  const { roles, refresh } = useAdminRole();
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [products, setProducts] = useState([]);
  const [permissionsMap, setPermissionsMap] = useState({}); // { [productId]: { view: true, ... } }
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const selectedRole = useMemo(
    () => roles.find((r) => String(r.id) === String(selectedRoleId)) || null,
    [roles, selectedRoleId]
  );

  useEffect(() => {
    if (!selectedRoleId) {
      setProducts([]);
      setPermissionsMap({});
      return;
    }
    loadPermissions();
  }, [selectedRoleId]);

  async function loadPermissions() {
    if (!selectedRoleId) return;
    setLoading(true);
    setMessage(null);
    try {
      const [productsData, permsData] = await Promise.all([
        apiFetch("/api/admin/products"),
        apiFetch(`/api/admin/roles/${selectedRoleId}/permissions`),
      ]);
      setProducts(productsData || []);
      // permsData is expected to be an array of { product_id, can_view, can_create, ... }
      const map = {};
      for (const p of permsData || []) {
        const perms = {};
        for (const perm of PERMISSION_KEYS) {
          perms[perm.key] = !!p[`can_${perm.key}`];
        }
        map[p.product_id] = perms;
      }
      setPermissionsMap(map);
    } catch (err) {
      console.error("Failed to load permissions:", err);
      setMessage({ type: "error", text: "Failed to load permissions." });
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e) {
    // Guard against a real page reload no matter how this is triggered
    // (a click, a stray Enter-key submit, etc.) - handleSave is always
    // called through this guard so a native form submission can never
    // slip through and refresh the page.
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    if (!selectedRoleId) return;
    setSaving(true);
    setMessage(null);
    try {
      const permissions = products.map((product) => {
        const perms = permissionsMap[product.id] || {};
        const payload = { product_id: product.id };
        for (const perm of PERMISSION_KEYS) {
          payload[`can_${perm.key}`] = !!perms[perm.key];
        }
        return payload;
      });

      await apiFetch(`/api/admin/roles/${selectedRoleId}/permissions`, {
        method: "POST",
        body: JSON.stringify({ permissions }),
      });
      setMessage({ type: "success", text: "Permissions saved successfully." });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({ type: "error", text: err.message || "Failed to save permissions." });
    } finally {
      setSaving(false);
    }
  }

  function togglePermission(productId, key) {
    // Deactivated products (Manage > Products) can't have their
    // permissions edited - CRUD is disabled for them here too.
    const product = products.find((p) => p.id === productId);
    if (product && !product.enabled) return;

    setPermissionsMap((prev) => {
      const current = prev[productId] || {};
      return {
        ...prev,
        [productId]: {
          ...current,
          [key]: !current[key],
        },
      };
    });
  }

  function handleReset() {
    loadPermissions();
  }

  return (
    <>
      <Header
        title="Role Permission"
        description="Configure what each role can do across your purchased products."
        actions={
          <form
            onSubmit={handleSave}
            style={{ display: "flex", gap: 10, alignItems: "center" }}
          >
            <select
              className="manage-select"
              value={selectedRoleId}
              onChange={(e) => setSelectedRoleId(e.target.value)}
              style={{ minWidth: 220 }}
            >
              <option value="">Select a role…</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
            <button type="button" className="btn-secondary-dp" onClick={handleReset} disabled={!selectedRoleId || loading}>
              <FaUndo size={12} style={{ marginRight: 6 }} />
              Reset
            </button>
            <button type="submit" className="btn-primary-dp" disabled={!selectedRoleId || saving || loading}>
              <FaSave size={12} style={{ marginRight: 6 }} />
              {saving ? "Saving…" : "Save"}
            </button>
          </form>
        }
      />

      <main className="main-content">
        <div className="manage-page">
          {!selectedRole ? (
            <div className="manage-card">
              <p className="manage-hint">Select a role above to view and edit its permissions.</p>
            </div>
          ) : loading ? (
            <div className="manage-card">
              <p className="manage-hint">Loading permissions…</p>
            </div>
          ) : (
            <div className="manage-card">
              <div style={{ marginBottom: 18 }}>
                <h2 className="manage-card-heading" style={{ margin: 0 }}>
                  Permissions for "{selectedRole.name}"
                </h2>
                <p className="manage-card-subheading" style={{ marginTop: 6 }}>
                  Toggle the permissions this role has for each product. Changes are saved only when you click Save.
                </p>
              </div>

              {message && (
                <p
                  className="manage-hint"
                  style={{
                    marginBottom: 14,
                    color: message.type === "error" ? "#c0392b" : "#1a7a4c",
                    fontWeight: 600,
                  }}
                >
                  {message.text}
                </p>
              )}

              {products.length === 0 ? (
                <p className="manage-hint">No products purchased yet.</p>
              ) : (
                <div className="manage-table-wrap">
                  <table className="manage-table">
                    <thead>
                      <tr>
                        <th style={{ minWidth: 180 }}>Product</th>
                        {PERMISSION_KEYS.map((perm) => (
                          <th key={perm.key} className="center" style={{ minWidth: 90 }}>
                            {perm.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {products.map((product) => {
                        const perms = permissionsMap[product.id] || {};
                        const disabled = !product.enabled;
                        return (
                          <tr key={product.id} className={disabled ? "row-disabled" : ""}>
                            <td style={{ fontWeight: 600 }}>
                              {product.name}
                              {disabled && (
                                <span className="status-pill inactive" style={{ marginLeft: 8 }}>
                                  Deactivated
                                </span>
                              )}
                            </td>
                            {PERMISSION_KEYS.map((perm) => (
                              <td key={perm.key} className="center">
                                <label
                                  className={`pa-toggle ${disabled ? "disabled" : ""}`}
                                  title={
                                    disabled
                                      ? `${product.name} is deactivated - reactivate it in Manage > Products to edit permissions.`
                                      : `Toggle ${perm.label} permission`
                                  }
                                >
                                  <input
                                    type="checkbox"
                                    checked={!!perms[perm.key]}
                                    disabled={disabled}
                                    onChange={() => togglePermission(product.id, perm.key)}
                                  />
                                  <span className="pa-toggle-track">
                                    <span className="pa-toggle-thumb" />
                                  </span>
                                </label>
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </>
  );
}