/**
 * workspace/pages/Users.jsx
 * ------------------------------------------------------------
 * Admin-only "Users" page (Manage > User Management > Users).
 *
 * Flow:
 *   1. "Create User" adds a person (name, email, password). They
 *      appear in the Users table below immediately - a Role is
 *      assigned afterward, from here.
 *   2. Every user created through this page shows up in the
 *      Users table - that's the whole dataflow.
 *   3. Above the table: a Role dropdown (populated live from
 *      Manage > Role) plus a filter dropdown (All users /
 *      Assigned / Unassigned).
 *        - "Unassigned" always means "has no role at all",
 *          regardless of which Role is selected - so there's
 *          always a well-defined candidate pool to assign.
 *        - "Assigned" means "is in the selected Role" when a
 *          Role is chosen, or "has any Role" when it isn't.
 *      Tick checkboxes in the table, then use "Assign Selected"
 *      (needs a Role chosen) or "Unassign Selected" (works
 *      regardless of the Role dropdown) below the table.
 *
 * Now backed by the real FastAPI + MS SQL backend via apiFetch.
 * ------------------------------------------------------------
 */

import React, { useMemo, useState, useEffect } from "react";
import {
  FaUserFriends,
  FaUsers,
  FaTimes,
  FaTrashAlt,
  FaEdit,
  FaEye,
  FaEyeSlash,
  FaSearch,
  FaUserPlus,
  FaChevronLeft,
  FaChevronRight,
  FaInfoCircle,
} from "react-icons/fa";

import Header from "../../../components/WorkspaceHeader";
import { useAdminRole } from "../../../context/AdminRoleContext";
import { apiFetch } from "../../../../services/api";
import { validateFullName, validateEmail, validatePassword } from "../../../../utils/validators.js";
import "../../../styles/manage.css";

const AVATAR_COLORS = ["#1B3A4B", "#7C3AED", "#0EA5E9", "#B45309", "#059669", "#DB2777", "#4338CA", "#B91C1C"];
function avatarColor(seed) {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
function initialsFor(name) {
  return (name || "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || "")
    .join("");
}

const EMPTY_CREATE_FORM = {
  fullName: "",
  email: "",
  password: "",
};

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50];

export default function Users() {
  const { roles, usersCache, setUsersCache, refresh } = useAdminRole();

  const [refreshTick, setRefreshTick] = useState(0);
  const allUsers = usersCache;
  function refreshUsers() {
    setRefreshTick((t) => t + 1);
    refresh();
  }

  // Every user created via "Create User" on this page - regardless of
  // Role - shows up here. This is the "created user list" dataflow.
  const createdUsers = useMemo(() => allUsers.filter((u) => u.created_via_admin), [allUsers]);

  /* ---------------- Role dropdown + Assigned/Unassigned filter ---------------- */
  const [selectedRole, setSelectedRole] = useState(""); // "" = All Roles
  const [assignmentFilter, setAssignmentFilter] = useState("all"); // all | assigned | unassigned

  const [userSearch, setUserSearch] = useState("");
  const [selectedUserIds, setSelectedUserIds] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // "Unassigned" is always "no role at all" - well-defined on its own,
  // so picking a Role never makes it show a contradictory empty list.
  // "Assigned" narrows to the selected Role when one is chosen, or
  // "has any role" when it isn't.
  const filteredUsers = createdUsers.filter((u) => {
    const matchesSearch = `${u.full_name} ${u.email}`.toLowerCase().includes(userSearch.trim().toLowerCase());

    let matchesAssignment = true;
    if (assignmentFilter === "assigned") {
      matchesAssignment = selectedRole ? u.role_group === selectedRole : !!u.role_group;
    } else if (assignmentFilter === "unassigned") {
      matchesAssignment = !u.role_group;
    }

    return matchesSearch && matchesAssignment;
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [userSearch, selectedRole, assignmentFilter, rowsPerPage]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / rowsPerPage));
  // Clamp the page whenever the filtered/total count shrinks out from
  // under the current page (e.g. after bulk-assigning everyone on the
  // last page away) so the table never renders a blank page.
  useEffect(() => {
    setCurrentPage((p) => Math.min(p, totalPages));
  }, [totalPages]);
  const pageStart = (currentPage - 1) * rowsPerPage;
  const pagedUsers = filteredUsers.slice(pageStart, pageStart + rowsPerPage);

  const allOnPageSelected = pagedUsers.length > 0 && pagedUsers.every((u) => selectedUserIds.includes(u.id));

  function toggleUser(id) {
    setSelectedUserIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }
  function toggleSelectAllOnPage() {
    if (allOnPageSelected) {
      setSelectedUserIds((prev) => prev.filter((id) => !pagedUsers.some((u) => u.id === id)));
    } else {
      setSelectedUserIds((prev) => [...new Set([...prev, ...pagedUsers.map((u) => u.id)])]);
    }
  }

  const [assignBanner, setAssignBanner] = useState(null);

  async function handleAssignSelected() {
    if (!selectedRole || selectedUserIds.length === 0) return;
    const role = roles.find((r) => r.name === selectedRole);
    if (!role) return;

    for (const userId of selectedUserIds) {
      await apiFetch(`/api/admin/users/${userId}/assign-role`, {
        method: "POST",
        body: JSON.stringify({ role_name: selectedRole }),
      });
    }
    setAssignBanner(`${selectedUserIds.length} user(s) assigned to ${selectedRole}.`);
    setSelectedUserIds([]);
    refreshUsers();
    setTimeout(() => setAssignBanner(null), 3000);
  }

  async function handleUnassignSelected() {
    if (selectedUserIds.length === 0) return;
    for (const userId of selectedUserIds) {
      await apiFetch(`/api/admin/users/${userId}/unassign-role`, { method: "DELETE" });
    }
    setAssignBanner(`${selectedUserIds.length} user(s) unassigned.`);
    setSelectedUserIds([]);
    refreshUsers();
    setTimeout(() => setAssignBanner(null), 3000);
  }

  /* ---------------- Create User modal ---------------- */
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_CREATE_FORM);
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function openCreateModal() {
    setForm(EMPTY_CREATE_FORM);
    setErrors({});
    setShowPassword(false);
    setModalOpen(true);
  }
  function closeModal() {
    if (isSaving) return;
    setModalOpen(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const nextErrors = {};
    const nameErr = validateFullName(form.fullName);
    if (nameErr) nextErrors.fullName = nameErr;

    const emailErr = validateEmail(form.email);
    if (emailErr) nextErrors.email = emailErr;

    const passwordErr = validatePassword(form.password);
    if (passwordErr) nextErrors.password = passwordErr;

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setIsSaving(true);
    try {
      const data = await apiFetch("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: form.fullName.trim(),
          email: form.email.trim().toLowerCase(),
          password: form.password,
        }),
      });
      setUsersCache((prev) => [...prev, data]);
      setModalOpen(false);
      refreshUsers();
    } catch (err) {
      setErrors({ form: err.message || "Failed to create user." });
    } finally {
      setIsSaving(false);
    }
  }

  /* ---------------- Edit modal (name / email / role) ---------------- */
  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [editErrors, setEditErrors] = useState({});
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  function openEditModal(user) {
    setEditingUser(user);
    setEditForm({
      fullName: user.full_name,
      email: user.email,
      roleGroup: user.role_group || "",
    });
    setEditErrors({});
  }
  function closeEditModal() {
    if (isSavingEdit) return;
    setEditingUser(null);
    setEditForm(null);
  }
  async function handleEditSubmit(e) {
    e.preventDefault();
    const nameErr = validateFullName(editForm.fullName);
    const emailErr = validateEmail(editForm.email);
    if (nameErr || emailErr) {
      setEditErrors({ form: nameErr || emailErr });
      return;
    }

    setIsSavingEdit(true);
    setEditErrors({});
    try {
      // 1) Persist name/email.
      await apiFetch(`/api/admin/users/${editingUser.id}`, {
        method: "PUT",
        body: JSON.stringify({
          full_name: editForm.fullName.trim(),
          email: editForm.email.trim().toLowerCase(),
        }),
      });

      // 2) Persist the role change, if any - the name/email endpoint above
      //    doesn't touch role assignment, so this has to be a separate call.
      const nextRoleGroup = editForm.roleGroup || "";
      const previousRoleGroup = editingUser.role_group || "";
      if (nextRoleGroup !== previousRoleGroup) {
        if (nextRoleGroup) {
          await apiFetch(`/api/admin/users/${editingUser.id}/assign-role`, {
            method: "POST",
            body: JSON.stringify({ role_name: nextRoleGroup }),
          });
        } else {
          await apiFetch(`/api/admin/users/${editingUser.id}/unassign-role`, { method: "DELETE" });
        }
      }

      setUsersCache((prev) =>
        prev.map((u) =>
          u.id === editingUser.id
            ? {
                ...u,
                full_name: editForm.fullName.trim(),
                email: editForm.email.trim().toLowerCase(),
                role_group: nextRoleGroup || null,
              }
            : u
        )
      );
      refreshUsers();
      setEditingUser(null);
      setEditForm(null);
    } catch (err) {
      setEditErrors({ form: err.message || "Failed to save changes. Please try again." });
    } finally {
      setIsSavingEdit(false);
    }
  }

  /* ---------------- Delete confirmation ---------------- */
  const [confirmRemove, setConfirmRemove] = useState(null);
  async function handleRemove() {
    if (!confirmRemove) return;
    await apiFetch(`/api/admin/users/${confirmRemove.id}`, { method: "DELETE" });
    setUsersCache((prev) => prev.filter((u) => u.id !== confirmRemove.id));
    setSelectedUserIds((prev) => prev.filter((id) => id !== confirmRemove.id));
    setConfirmRemove(null);
    refreshUsers();
  }

  return (
    <>
      <Header
        title="Users"
        description="Create, manage and assign users efficiently."
        actions={
          <button type="button" className="btn-primary-dp" onClick={openCreateModal}>
            <FaUserPlus size={13} style={{ marginRight: 8 }} /> Create User
          </button>
        }
      />

      <main className="main-content">
        <div className="manage-page" style={{ maxWidth: 1180 }}>
          {/* ---------------- Users table (Role + filter live in this same section) ---------------- */}
          <div className="manage-card">
            <div className="users-emp-toolbar">
              <div>
                <h3 className="manage-card-heading" style={{ margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
                  Users
                  <span className="type-count-chip">{filteredUsers.length} total</span>
                </h3>
              </div>
              <div className="users-emp-controls">
                <div className="rg-search">
                  <FaSearch className="rg-search-icon" size={12} />
                  <input
                    type="text"
                    placeholder="Search users..."
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="users-role-assign-grid">
              <div>
                <label htmlFor="users-role-select" style={{ fontWeight: 700, fontSize: 13, color: "#10202b", display: "block", marginBottom: 8 }}>
                  Role
                </label>
                <div className="emp-select-wrap">
                  <FaUsers className="emp-select-icon" size={13} />
                  <select
                    id="users-role-select"
                    className="manage-select"
                    style={{ paddingLeft: 36 }}
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value)}
                  >
                    <option value="">All Roles</option>
                    {roles.map((r) => (
                      <option key={r.id} value={r.name}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="users-assign-filter" style={{ fontWeight: 700, fontSize: 13, color: "#10202b", display: "block", marginBottom: 8 }}>
                  Filter
                </label>
                <div className="rg-status-filter" style={{ width: "100%" }}>
                  <select
                    id="users-assign-filter"
                    style={{ width: "100%" }}
                    value={assignmentFilter}
                    onChange={(e) => setAssignmentFilter(e.target.value)}
                  >
                    <option value="all">All users</option>
                    <option value="assigned">Assigned</option>
                    <option value="unassigned">Unassigned</option>
                  </select>
                </div>
              </div>
            </div>

            {selectedRole ? (
              <div className="users-assign-info-banner">
                <FaInfoCircle size={13} />
                {assignmentFilter === "unassigned"
                  ? ` Showing users with no role yet - select some below, then "Assign Selected" to add them to "${selectedRole}".`
                  : assignmentFilter === "assigned"
                    ? ` Showing current members of "${selectedRole}" - select users below, then "Unassign Selected" to remove them.`
                    : ` Select users below, then "Assign Selected" to add them to "${selectedRole}", or "Unassign Selected" to clear their role.`}
              </div>
            ) : (
              <p className="manage-hint" style={{ marginTop: 12, marginBottom: 0 }}>
                Pick a Role above, then use the filter to find users to assign or unassign.
              </p>
            )}

            {assignBanner && (
              <p className="manage-hint" style={{ marginTop: 10, marginBottom: 0, color: "#1a7a4c", fontWeight: 600 }}>
                {assignBanner}
              </p>
            )}

            <div className="manage-table-wrap" style={{ marginTop: 18 }}>
              <table className="manage-table">
                <thead>
                  <tr>
                    <th className="center" style={{ width: 40 }}>
                      <input type="checkbox" checked={allOnPageSelected} onChange={toggleSelectAllOnPage} disabled={pagedUsers.length === 0} />
                    </th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th className="center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedUsers.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", color: "#a3aebf", padding: "26px 16px" }}>
                        {createdUsers.length === 0
                          ? 'No users created yet. Use "Create User" above to add one.'
                          : "No users match this search/filter."}
                      </td>
                    </tr>
                  )}
                  {pagedUsers.map((u) => (
                    <tr key={u.id}>
                      <td className="center">
                        <input type="checkbox" checked={selectedUserIds.includes(u.id)} onChange={() => toggleUser(u.id)} />
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <Avatar name={u.full_name} />
                          {u.full_name}
                        </div>
                      </td>
                      <td>{u.email}</td>
                      <td>{u.role_group || <span style={{ color: "#a3aebf" }}>Unassigned</span>}</td>
                      <td className="center">
                        <div className="rg-row-actions">
                          <button type="button" className="rg-icon-btn edit" title="Edit" onClick={() => openEditModal(u)}>
                            <FaEdit size={12} />
                          </button>
                          <button type="button" className="rg-icon-btn delete" title="Remove" onClick={() => setConfirmRemove(u)}>
                            <FaTrashAlt size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="users-table-footer">
              <span className="users-selected-count">
                {selectedUserIds.length > 0 ? `${selectedUserIds.length} user(s) selected` : ""}
              </span>

              <div className="users-pagination">
                <label>
                  Rows per page:{" "}
                  <select value={rowsPerPage} onChange={(e) => setRowsPerPage(Number(e.target.value))}>
                    {ROWS_PER_PAGE_OPTIONS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <span>
                  {filteredUsers.length === 0 ? 0 : pageStart + 1}-{Math.min(pageStart + rowsPerPage, filteredUsers.length)} of {filteredUsers.length}
                </span>
                <button type="button" className="rg-icon-btn edit" onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={currentPage === 1}>
                  <FaChevronLeft size={11} />
                </button>
                <button
                  type="button"
                  className="rg-icon-btn edit"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  <FaChevronRight size={11} />
                </button>
              </div>

              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  className="btn-secondary-dp"
                  onClick={handleUnassignSelected}
                  disabled={selectedUserIds.length === 0}
                >
                  Unassign Selected {selectedUserIds.length > 0 ? `(${selectedUserIds.length})` : ""}
                </button>
                <button
                  type="button"
                  className="btn-primary-dp"
                  onClick={handleAssignSelected}
                  disabled={!selectedRole || selectedUserIds.length === 0}
                >
                  Assign Selected {selectedUserIds.length > 0 ? `(${selectedUserIds.length})` : ""}
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ---------------- Create User modal ---------------- */}
      {modalOpen && (
        <div className="rg-modal-overlay" onClick={closeModal}>
          <div className="rg-modal" onClick={(e) => e.stopPropagation()}>
            <div className="rg-modal-header">
              <span className="rg-icon-chip">
                <FaUserFriends size={16} />
              </span>
              <h2>Create User</h2>
              <button type="button" className="rg-modal-close" onClick={closeModal} aria-label="Close">
                <FaTimes size={14} />
              </button>
            </div>

            <form onSubmit={handleSubmit} noValidate autoComplete="off">
              <div className="manage-field">
                <label htmlFor="cu-fullname">
                  Full Name<span className="required-dot">*</span>
                </label>
                <input
                  id="cu-fullname"
                  name="cu-fullname"
                  className="manage-input"
                  type="text"
                  placeholder="e.g. Priya Nair"
                  value={form.fullName}
                  autoComplete="off"
                  onChange={(e) => {
                    setForm((f) => ({ ...f, fullName: e.target.value }));
                    setErrors((prev) => ({ ...prev, fullName: null }));
                  }}
                />
                {errors.fullName && <p className="manage-error">{errors.fullName}</p>}
              </div>

              <div className="manage-field">
                <label htmlFor="cu-email">
                  Email<span className="required-dot">*</span>
                </label>
                <input
                  id="cu-email"
                  name="cu-email"
                  className="manage-input"
                  type="email"
                  placeholder="name@company.com"
                  value={form.email}
                  autoComplete="off"
                  onChange={(e) => {
                    setForm((f) => ({ ...f, email: e.target.value }));
                    setErrors((prev) => ({ ...prev, email: null }));
                  }}
                />
                {errors.email && <p className="manage-error">{errors.email}</p>}
              </div>

              <div className="manage-field" style={{ marginBottom: 8 }}>
                <label htmlFor="cu-password">
                  Password<span className="required-dot">*</span>
                </label>
                <div className="manage-input-icon-wrap">
                  <input
                    id="cu-password"
                    name="cu-new-password"
                    className="manage-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="Used to sign in to the workspace"
                    value={form.password}
                    autoComplete="new-password"
                    onChange={(e) => {
                      setForm((f) => ({ ...f, password: e.target.value }));
                      setErrors((prev) => ({ ...prev, password: null }));
                    }}
                  />
                  <button
                    type="button"
                    className="manage-input-icon-btn"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    tabIndex={-1}
                  >
                    {showPassword ? <FaEyeSlash size={14} /> : <FaEye size={14} />}
                  </button>
                </div>
                {errors.password && <p className="manage-error">{errors.password}</p>}
              </div>

              {errors.form && <p className="manage-error">{errors.form}</p>}

              <div className="rg-modal-actions">
                <button type="button" className="btn-secondary-dp" onClick={closeModal} disabled={isSaving}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary-dp" disabled={isSaving}>
                  {isSaving ? "Creating…" : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- Edit modal ---------------- */}
      {editingUser && editForm && (
        <div className="rg-modal-overlay" onClick={closeEditModal}>
          <div className="rg-modal" onClick={(e) => e.stopPropagation()}>
            <div className="rg-modal-header">
              <span className="rg-icon-chip">
                <FaEdit size={15} />
              </span>
              <h2>Edit User</h2>
              <button type="button" className="rg-modal-close" onClick={closeEditModal} aria-label="Close">
                <FaTimes size={14} />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} noValidate>
              <div className="manage-field">
                <label htmlFor="eu-fullname">Full Name</label>
                <input
                  id="eu-fullname"
                  className="manage-input"
                  type="text"
                  value={editForm.fullName}
                  onChange={(e) => setEditForm((f) => ({ ...f, fullName: e.target.value }))}
                />
              </div>
              <div className="manage-field">
                <label htmlFor="eu-email">Email</label>
                <input
                  id="eu-email"
                  className="manage-input"
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                />
              </div>
              <div className="manage-field" style={{ marginBottom: 8 }}>
                <label htmlFor="eu-role">Role</label>
                <select
                  id="eu-role"
                  className="manage-select"
                  value={editForm.roleGroup}
                  onChange={(e) => setEditForm((f) => ({ ...f, roleGroup: e.target.value }))}
                >
                  <option value="">Unassigned</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.name}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>

              {editErrors.form && <p className="manage-error">{editErrors.form}</p>}

              <div className="rg-modal-actions">
                <button type="button" className="btn-secondary-dp" onClick={closeEditModal} disabled={isSavingEdit}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary-dp" disabled={isSavingEdit}>
                  {isSavingEdit ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ---------------- Remove confirmation ---------------- */}
      {confirmRemove && (
        <div className="rg-modal-overlay" onClick={() => setConfirmRemove(null)}>
          <div className="rg-modal rg-modal-sm" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Remove user?</h2>
            <p className="manage-card-subheading" style={{ marginBottom: 20 }}>
              This will permanently remove <strong>{confirmRemove.full_name}</strong>. This can't be undone.
            </p>
            <div className="rg-modal-actions">
              <button type="button" className="btn-secondary-dp" onClick={() => setConfirmRemove(null)}>
                Cancel
              </button>
              <button type="button" className="btn-danger-dp" onClick={handleRemove}>
                Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Avatar({ name }) {
  return (
    <span className="avatar-circle" style={{ background: avatarColor(name || "?") }}>
      {initialsFor(name)}
    </span>
  );
}