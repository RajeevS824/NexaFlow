/**
 * workspace/pages/RoleManagement.jsx
 * ------------------------------------------------------------
 * Admin-only "Role" page (Manage > Role) — "Role Groups".
 *
 * Default view is a searchable, filterable Role Groups table
 * (ID / Role Group / Description / Employees / Status / Actions)
 * with a "+ Create Role Group" button that opens a modal form
 * (name, description, status). Editing a row reuses the same
 * modal, pre-filled. Frontend-only demo: state lives in
 * AdminRoleContext so the Employees page can read the same role
 * groups and an accurate, live "Employees" count.
 * ------------------------------------------------------------
 */

import React, { useMemo, useState } from "react";
import { FaUserShield, FaUsers, FaSearch, FaPen, FaTrashAlt, FaEye, FaPlus, FaTimes } from "react-icons/fa";

import Header from "../../../components/WorkspaceHeader";
import { useAdminRole } from "../../../context/AdminRoleContext";
import "../../../styles/manage.css";

const EMPTY_FORM = { name: "", description: "", status: "active" };

export default function RoleManagement() {
  const { roles, addRole, updateRole, deleteRole, getAssignedCount, getAssignedUsers } = useAdminRole();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  const [viewingRoleId, setViewingRoleId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  // Derived live from `roles` every render (rather than a snapshot
  // captured on click) so if a role's name/description/status changes
  // while this modal happens to be open, it reflects the update
  // instead of showing stale data.
  const viewingRole = roles.find((r) => r.id === viewingRoleId) || null;

  const filteredRoles = useMemo(() => {
    const q = search.trim().toLowerCase();
    return roles.filter((r) => {
      const matchesSearch =
        !q || r.name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "all" || r.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [roles, search, statusFilter]);

  function openCreateModal() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setErrors({});
    setModalOpen(true);
  }

  function openEditModal(role) {
    setEditingId(role.id);
    setForm({ name: role.name, description: role.description, status: role.status });
    setErrors({});
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const nextErrors = {};
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      nextErrors.name = "Please enter a role group name.";
    } else if (
      roles.some((r) => r.id !== editingId && r.name.trim().toLowerCase() === trimmedName.toLowerCase())
    ) {
      // Users are linked to a role by NAME (see AdminRoleContext), so two
      // role groups sharing a name would silently merge in every
      // Role dropdown and filter on the Users page - block it here.
      nextErrors.name = "A role group with this name already exists.";
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    if (editingId) {
      updateRole(editingId, {
        name: trimmedName,
        description: form.description.trim(),
        status: form.status,
      });
    } else {
      addRole(trimmedName, form.description.trim(), form.status);
    }
    setModalOpen(false);
  }

  function confirmDelete() {
    if (confirmDeleteId) {
      deleteRole(confirmDeleteId);
      setConfirmDeleteId(null);
    }
  }

  const roleToDelete = roles.find((r) => r.id === confirmDeleteId);

  return (
    <>
      <Header
        title="Role Groups"
        description="Define the role groups your team can be assigned, and what each one is for."
      />
      <main className="main-content">
        <div className="manage-page" style={{ maxWidth: 1120 }}>
          <div className="manage-card">
            <div className="rg-toolbar-heading">
              <div>
                <h2 className="manage-card-heading">
                  <span className="rg-icon-chip">
                    <FaUsers size={16} />
                  </span>
                  Role Groups
                </h2>
                <p className="manage-card-subheading" style={{ margin: 0 }}>
                  Create and manage the role groups users can be assigned to.
                </p>
              </div>
              <button type="button" className="btn-primary-dp rg-create-btn" onClick={openCreateModal}>
                <FaPlus size={12} /> Create Role Group
              </button>
            </div>

            <div className="rg-toolbar">
              <div className="rg-search">
                <FaSearch className="rg-search-icon" size={13} />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search role groups..."
                />
              </div>
              <div className="rg-status-filter">
                <label htmlFor="rg-status-select">Status:</label>
                <select
                  id="rg-status-select"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>

            <div className="manage-table-wrap" style={{ marginTop: 16 }}>
              <table className="manage-table">
                <thead>
                  <tr>
                    <th style={{ width: 56 }}>ID</th>
                    <th>Role Group</th>
                    <th>Description</th>
                    <th className="center">Users</th>
                    <th className="center">Status</th>
                    <th className="center" style={{ width: 140 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRoles.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", color: "#8a97ab", padding: "28px 16px" }}>
                        No role groups match your search.
                      </td>
                    </tr>
                  )}
                  {filteredRoles.map((r, i) => (
                    <tr key={r.id}>
                      <td>{i + 1}</td>
                      <td style={{ fontWeight: 600 }}>{r.name}</td>
                      <td>{r.description || "—"}</td>
                      <td className="center">{getAssignedCount(r.name)}</td>
                      <td className="center">
                        <span className={`status-pill ${r.status}`}>{r.status === "active" ? "Active" : "Inactive"}</span>
                      </td>
                      <td className="center">
                        <div className="rg-row-actions">
                          <button type="button" className="rg-icon-btn edit" title="Edit" onClick={() => openEditModal(r)}>
                            <FaPen size={12} />
                          </button>
                          <button
                            type="button"
                            className="rg-icon-btn delete"
                            title="Delete"
                            onClick={() => setConfirmDeleteId(r.id)}
                          >
                            <FaTrashAlt size={12} />
                          </button>
                          <button type="button" className="rg-icon-btn view" title="View" onClick={() => setViewingRoleId(r.id)}>
                            <FaEye size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      {/* Create / Edit modal */}
      {modalOpen && (
        <div className="rg-modal-overlay" onClick={closeModal}>
          <div className="rg-modal" onClick={(e) => e.stopPropagation()}>
            <div className="rg-modal-header">
              <span className="rg-icon-chip">
                <FaUserShield size={16} />
              </span>
              <h2>{editingId ? "Edit Role Group" : "Create Role Group"}</h2>
              <button type="button" className="rg-modal-close" onClick={closeModal} aria-label="Close">
                <FaTimes size={14} />
              </button>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <div className="manage-field">
                <label htmlFor="rg-name">
                  Role Group Name<span className="required-dot">*</span>
                </label>
                <input
                  id="rg-name"
                  className="manage-input"
                  type="text"
                  placeholder="Enter role group name"
                  value={form.name}
                  onChange={(e) => {
                    setForm((f) => ({ ...f, name: e.target.value }));
                    setErrors((prev) => ({ ...prev, name: null }));
                  }}
                />
                {errors.name && <p className="manage-error">{errors.name}</p>}
              </div>

              <div className="manage-field">
                <label htmlFor="rg-description">Description</label>
                <textarea
                  id="rg-description"
                  className="manage-textarea"
                  placeholder="Enter description"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>

              <div className="manage-field" style={{ marginBottom: 8 }}>
                <label>Status</label>
                <div className="rg-radio-group">
                  <label className="rg-radio">
                    <input
                      type="radio"
                      name="rg-status"
                      checked={form.status === "active"}
                      onChange={() => setForm((f) => ({ ...f, status: "active" }))}
                    />
                    Active
                  </label>
                  <label className="rg-radio">
                    <input
                      type="radio"
                      name="rg-status"
                      checked={form.status === "inactive"}
                      onChange={() => setForm((f) => ({ ...f, status: "inactive" }))}
                    />
                    Inactive
                  </label>
                </div>
              </div>

              <div className="rg-modal-actions">
                <button type="button" className="btn-secondary-dp" onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary-dp">
                  {editingId ? "Save Changes" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* View modal - shows the users assigned to this role in table format */}
      {viewingRole && (
        <div className="rg-modal-overlay" onClick={() => setViewingRoleId(null)}>
          <div className="rg-modal rg-modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="rg-modal-header">
              <span className="rg-icon-chip">
                <FaUsers size={16} />
              </span>
              <h2>{viewingRole.name}</h2>
              <button
                type="button"
                className="rg-modal-close"
                onClick={() => setViewingRoleId(null)}
                aria-label="Close"
              >
                <FaTimes size={14} />
              </button>
            </div>
            <div className="rg-view-body">
              <div className="rg-view-row">
                <span>Description</span>
                <strong>{viewingRole.description || "—"}</strong>
              </div>
              <div className="rg-view-row">
                <span>Status</span>
                <span className={`status-pill ${viewingRole.status}`}>
                  {viewingRole.status === "active" ? "Active" : "Inactive"}
                </span>
              </div>
            </div>

            <div style={{ margin: "4px 0 18px" }}>
              <h3 className="manage-card-heading" style={{ fontSize: 13, margin: "0 0 10px" }}>
                Users in this role
                <span className="type-count-chip" style={{ marginLeft: 8 }}>
                  {getAssignedCount(viewingRole.name)} total
                </span>
              </h3>
              <div className="manage-table-wrap">
                <table className="manage-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getAssignedUsers(viewingRole.name).length === 0 && (
                      <tr>
                        <td colSpan={2} style={{ textAlign: "center", color: "#a3aebf", padding: "22px 16px" }}>
                          No users are assigned to this role yet.
                        </td>
                      </tr>
                    )}
                    {getAssignedUsers(viewingRole.name).map((u) => (
                      <tr key={u.id}>
                        <td>{u.full_name}</td>
                        <td>{u.email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rg-modal-actions">
              <button type="button" className="btn-primary-dp" onClick={() => setViewingRoleId(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {confirmDeleteId && (
        <div className="rg-modal-overlay" onClick={() => setConfirmDeleteId(null)}>
          <div className="rg-modal rg-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Delete role group?</h2>
            <p className="manage-card-subheading" style={{ marginBottom: 20 }}>
              This will permanently remove <strong>{roleToDelete?.name}</strong> and unassign every
              user mapped to it. This can't be undone.
            </p>
            <div className="rg-modal-actions">
              <button type="button" className="btn-secondary-dp" onClick={() => setConfirmDeleteId(null)}>
                Cancel
              </button>
              <button type="button" className="btn-danger-dp" onClick={confirmDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
