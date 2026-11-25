import express from "express";
import bcrypt from "bcryptjs";
import { requireAdmin } from "./auth.mjs";
import { getCorePool, getBmPool } from "./db.mjs";
import {
  store,
  PRODUCT_SLUGS,
  getOrgLicensedProducts,
  getOrgUserIds,
} from "./store.mjs";

export const adminRouter = express.Router();
adminRouter.use(requireAdmin);

function buildLast7Days() {
  const keys = [];
  const labels = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - i));
    keys.push(d.toISOString().slice(0, 10));
    labels.push(`${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`);
  }
  return { keys, labels };
}

adminRouter.get("/analytics/dashboard", async (req, res) => {
  const orgId = req.user.org_id;
  const pool = getCorePool();
  const bmPool = getBmPool();
  const { keys, labels } = buildLast7Days();

  if (pool) {
    try {
      const licRes = await pool.query(
        `SELECT p.ProductID, p.ProductCode, p.ProductName
         FROM License l
         JOIN Product p ON p.ProductID = l.ProductID
         WHERE l.OrgID = $1 AND l.Status = TRUE AND p.IsActive = TRUE
         ORDER BY p.ProductID`,
        [orgId]
      );
      const licensedProducts = licRes.rows.map((r) => ({
        id: Number(r.productid),
        code: r.productcode,
        name: r.productname,
        slug: PRODUCT_SLUGS[r.productcode] || r.productcode.toLowerCase(),
      }));
      const licensedSlugs = new Set(licensedProducts.map((p) => p.slug));

      const cntRes = await pool.query(
        `SELECT
           (SELECT COUNT(*) FROM "user" WHERE OrgID = $1 AND Status = TRUE) +
           (SELECT COUNT(*) FROM CommunityEditionUser WHERE OrgID = $1 AND Status = TRUE) AS cnt`,
        [orgId]
      );
      const activeUsers = Number(cntRes.rows[0]?.cnt || 0);

      const uidsRes = await pool.query(
        `SELECT UserID AS uid FROM "user" WHERE OrgID = $1
         UNION
         SELECT CommunityEditionUserID AS uid FROM CommunityEditionUser WHERE OrgID = $1`,
        [orgId]
      );
      const orgUserIds = uidsRes.rows.map((r) => Number(r.uid));
      const orgUserSet = new Set(orgUserIds);

      const products = {};

      if (licensedSlugs.has("document-parser")) {
        // Document Parser runs in-memory (SQL Server is external/not provisioned)
        const dpJobs = store.dpHistory.filter((h) => h.ownerId == null || orgUserSet.has(h.ownerId));
        const statusMap = new Map();
        const dayMap = new Map();
        for (const j of dpJobs) {
          const st = String(j.status || "pending").toLowerCase();
          statusMap.set(st, (statusMap.get(st) || 0) + 1);
          const day = String(j.queuedAt || "").slice(0, 10);
          if (day) dayMap.set(day, (dayMap.get(day) || 0) + 1);
        }
        products["document-parser"] = {
          available: true,
          documents_total: dpJobs.length,
          jobs_total: dpJobs.length,
          status_breakdown: Array.from(statusMap.entries()).map(([status, count]) => ({ status, count })),
          trend: keys.map((k, idx) => ({ label: labels[idx], value: dayMap.get(k) || 0 })),
        };
      }

      if (licensedSlugs.has("business-process-mapper")) {
        if (bmPool) {
          if (orgUserIds.length === 0) {
            products["business-process-mapper"] = {
              available: true,
              jobs_total: 0,
              status_breakdown: [],
              trend: keys.map((_k, idx) => ({ label: labels[idx], value: 0 })),
            };
          } else {
            const stRes = await bmPool.query(
              `SELECT status, COUNT(*)::int AS count FROM public.jobs
               WHERE user_id = ANY($1::int[]) GROUP BY status`,
              [orgUserIds]
            );
            const statusBreakdown = stRes.rows.map((r) => ({ status: String(r.status), count: Number(r.count) }));
            const jobsTotal = statusBreakdown.reduce((acc, s) => acc + s.count, 0);

            const trRes = await bmPool.query(
              `SELECT TO_CHAR(CAST(created_at AS DATE), 'YYYY-MM-DD') AS day, COUNT(*)::int AS count
               FROM public.jobs
               WHERE user_id = ANY($1::int[])
                 AND created_at >= (CAST(NOW() AT TIME ZONE 'UTC' AS DATE) - 6)
               GROUP BY CAST(created_at AS DATE)`,
              [orgUserIds]
            );
            const dayMap = new Map(trRes.rows.map((r) => [r.day, Number(r.count)]));
            products["business-process-mapper"] = {
              available: true,
              jobs_total: jobsTotal,
              status_breakdown: statusBreakdown,
              trend: keys.map((k, idx) => ({ label: labels[idx], value: dayMap.get(k) || 0 })),
            };
          }
        } else {
          products["business-process-mapper"] = { available: false };
        }
      }

      return res.json({
        active_users: activeUsers,
        licensed_product_count: licensedProducts.length,
        licensed_products: licensedProducts.map((p) => ({ slug: p.slug, name: p.name })),
        products,
      });
    } catch (err) {
      console.error("[admin] Analytics DB error:", err.message);
      return res.status(500).json({ detail: "Failed to load dashboard analytics." });
    }
  }

  // In-memory fallback
  const licensedProducts = getOrgLicensedProducts(orgId);
  const licensedSlugs = new Set(licensedProducts.map((p) => p.slug));
  const orgUserIds = new Set(getOrgUserIds(orgId));
  const activeUsers =
    store.users.filter((u) => u.orgId === orgId && u.status).length +
    store.communityUsers.filter((u) => u.orgId === orgId && u.status).length;

  const products = {};
  if (licensedSlugs.has("document-parser")) {
    const dpJobs = store.dpHistory.filter((h) => h.ownerId == null || orgUserIds.has(h.ownerId));
    const statusMap = new Map();
    const dayMap = new Map();
    for (const j of dpJobs) {
      const st = String(j.status || "pending").toLowerCase();
      statusMap.set(st, (statusMap.get(st) || 0) + 1);
      const day = String(j.queuedAt || "").slice(0, 10);
      if (day) dayMap.set(day, (dayMap.get(day) || 0) + 1);
    }
    products["document-parser"] = {
      available: true,
      documents_total: dpJobs.length,
      jobs_total: dpJobs.length,
      status_breakdown: Array.from(statusMap.entries()).map(([status, count]) => ({ status, count })),
      trend: keys.map((k, idx) => ({ label: labels[idx], value: dayMap.get(k) || 0 })),
    };
  }

  if (licensedSlugs.has("business-process-mapper")) {
    const bmJobs = Array.from(store.bmJobs.values()).filter((j) => j.user_id == null || orgUserIds.has(j.user_id));
    const statusMap = new Map();
    const dayMap = new Map();
    for (const j of bmJobs) {
      const st = String(j.status || "QUEUED").toLowerCase();
      statusMap.set(st, (statusMap.get(st) || 0) + 1);
      const day = String(j.created_at || "").slice(0, 10);
      if (day) dayMap.set(day, (dayMap.get(day) || 0) + 1);
    }
    products["business-process-mapper"] = {
      available: true,
      jobs_total: bmJobs.length,
      status_breakdown: Array.from(statusMap.entries()).map(([status, count]) => ({ status, count })),
      trend: keys.map((k, idx) => ({ label: labels[idx], value: dayMap.get(k) || 0 })),
    };
  }

  res.json({
    active_users: activeUsers,
    licensed_product_count: licensedProducts.length,
    licensed_products: licensedProducts.map((p) => ({ slug: p.slug, name: p.name })),
    products,
  });
});

// ---------------- ROLES ----------------
function parseRoleActive(val, fallback = true) {
  if (val === undefined || val === null) return fallback;
  if (typeof val === "boolean") return val;
  return String(val).toLowerCase() !== "inactive" && String(val).toLowerCase() !== "false";
}

function formatRole(role) {
  const assignedCount = store.users.filter((u) => u.orgId === role.orgId && u.roleId === role.id).length;
  return {
    id: role.id,
    name: role.name,
    description: role.description,
    status: parseRoleActive(role.status),
    assigned_count: assignedCount,
  };
}

adminRouter.get("/roles", async (req, res) => {
  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT r.RoleID, r.RoleName, COALESCE(r.Description, '') AS Description, r.Status,
                COUNT(ur.UserRoleID)::int AS assigned_count
         FROM Role r
         LEFT JOIN UserRole ur ON ur.RoleID = r.RoleID
         WHERE r.OrgID = $1
         GROUP BY r.RoleID, r.RoleName, r.Description, r.Status
         ORDER BY r.RoleID DESC`,
        [req.user.org_id]
      );
      return res.json(
        r.rows.map((row) => ({
          id: Number(row.roleid),
          name: row.rolename,
          description: row.description,
          status: Boolean(row.status),
          assigned_count: Number(row.assigned_count || 0),
        }))
      );
    } catch (err) {
      console.error("[admin] list roles DB error:", err.message);
      return res.status(500).json({ detail: "Failed to load roles." });
    }
  }
  res.json(store.roles.filter((r) => r.orgId === req.user.org_id).map(formatRole));
});

adminRouter.post("/roles", async (req, res) => {
  const name = String(req.body?.name || "").trim();
  const description = String(req.body?.description || "").trim();
  const isActive = parseRoleActive(req.body?.status, true);
  if (!name) return res.status(400).json({ detail: "Role name is required." });

  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `INSERT INTO Role (OrgID, RoleName, Description, Status, CreatedBy)
         VALUES ($1, $2, $3, $4, $5) RETURNING RoleID`,
        [req.user.org_id, name, description, isActive, req.user.id]
      );
      return res.json({
        id: Number(r.rows[0].roleid),
        name,
        description,
        status: isActive,
        assigned_count: 0,
      });
    } catch (err) {
      console.error("[admin] create role DB error:", err.message);
      return res.status(500).json({ detail: "Failed to create role." });
    }
  }

  const role = {
    id: store.nextIds.role++,
    orgId: req.user.org_id,
    createdBy: req.user.id,
    name,
    description,
    status: isActive ? "active" : "inactive",
  };
  store.roles.push(role);
  res.json(formatRole(role));
});

adminRouter.put("/roles/:roleId", async (req, res) => {
  const roleId = Number(req.params.roleId);
  if (!Number.isInteger(roleId) || roleId <= 0) return res.status(400).json({ detail: "Invalid role ID." });
  const pool = getCorePool();
  if (pool) {
    try {
      const cur = await pool.query(
        `SELECT RoleID, RoleName, Description, Status FROM Role WHERE RoleID = $1 AND OrgID = $2`,
        [roleId, req.user.org_id]
      );
      if (!cur.rows[0]) return res.status(404).json({ detail: "Role not found." });
      const existing = cur.rows[0];
      const nextName = req.body?.name !== undefined ? String(req.body.name).trim() : existing.rolename;
      const nextDesc = req.body?.description !== undefined ? String(req.body.description).trim() : (existing.description || "");
      const nextStatus =
        req.body?.status !== undefined
          ? parseRoleActive(req.body.status, Boolean(existing.status))
          : Boolean(existing.status);

      await pool.query(
        `UPDATE Role SET RoleName = $1, Description = $2, Status = $3, UpdatedAt = NOW()
         WHERE RoleID = $4 AND OrgID = $5`,
        [nextName, nextDesc, nextStatus, roleId, req.user.org_id]
      );

      const cnt = await pool.query(`SELECT COUNT(*)::int AS cnt FROM UserRole WHERE RoleID = $1`, [roleId]);
      return res.json({
        id: roleId,
        name: nextName,
        description: nextDesc,
        status: nextStatus,
        assigned_count: Number(cnt.rows[0]?.cnt || 0),
      });
    } catch (err) {
      console.error("[admin] update role DB error:", err.message);
      return res.status(500).json({ detail: "Failed to update role." });
    }
  }

  const role = store.roles.find((r) => r.id === roleId && r.orgId === req.user.org_id);
  if (!role) return res.status(404).json({ detail: "Role not found." });
  if (req.body?.name !== undefined) role.name = String(req.body.name).trim();
  if (req.body?.description !== undefined) role.description = String(req.body.description).trim();
  if (req.body?.status !== undefined) role.status = parseRoleActive(req.body.status) ? "active" : "inactive";
  res.json(formatRole(role));
});

adminRouter.delete("/roles/:roleId", async (req, res) => {
  const roleId = Number(req.params.roleId);
  if (!Number.isInteger(roleId) || roleId <= 0) return res.status(400).json({ detail: "Invalid role ID." });
  const pool = getCorePool();
  if (pool) {
    const client = await pool.connect();
    try {
      const own = await client.query(`SELECT 1 FROM Role WHERE RoleID = $1 AND OrgID = $2`, [roleId, req.user.org_id]);
      if (own.rowCount === 0) return res.status(404).json({ detail: "Role not found." });

      await client.query("BEGIN");
      await client.query(`DELETE FROM UserRole WHERE RoleID = $1`, [roleId]);
      await client.query(`DELETE FROM RoleProductAccess WHERE RoleID = $1`, [roleId]);
      await client.query(`DELETE FROM Role WHERE RoleID = $1 AND OrgID = $2`, [roleId, req.user.org_id]);
      await client.query("COMMIT");
      return res.json({ message: "Role deleted." });
    } catch (err) {
      await client.query("ROLLBACK").catch(() => {});
      console.error("[admin] delete role DB error:", err.message);
      return res.status(500).json({ detail: "Failed to delete role." });
    } finally {
      client.release();
    }
  }

  const idx = store.roles.findIndex((r) => r.id === roleId && r.orgId === req.user.org_id);
  if (idx === -1) return res.status(404).json({ detail: "Role not found." });
  store.roles.splice(idx, 1);
  store.rolePermissions.delete(roleId);
  for (const u of store.users) {
    if (u.orgId === req.user.org_id && u.roleId === roleId) u.roleId = null;
  }
  res.json({ message: "Role deleted." });
});

// ---------------- USERS ----------------
function formatUser(user) {
  const role = user.roleId
    ? store.roles.find((r) => r.id === user.roleId && r.orgId === user.orgId)
    : null;
  return {
    id: user.id,
    full_name: user.fullName,
    email: user.email,
    role: "user",
    role_group: role ? role.name : null,
    status: Boolean(user.status),
    created_via_admin: Boolean(user.createdViaAdmin),
  };
}

adminRouter.get("/users", async (req, res) => {
  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT u.UserID, u.FirstName, u.Email, u.Status,
                (SELECT r.RoleName FROM UserRole ur JOIN Role r ON r.RoleID = ur.RoleID
                 WHERE ur.UserID = u.UserID LIMIT 1) AS role_group
         FROM "user" u
         WHERE u.OrgID = $1
         ORDER BY u.UserID DESC`,
        [req.user.org_id]
      );
      return res.json(
        r.rows.map((row) => ({
          id: Number(row.userid),
          full_name: row.firstname,
          email: row.email,
          role: "user",
          role_group: row.role_group || null,
          status: Boolean(row.status),
          created_via_admin: true,
        }))
      );
    } catch (err) {
      console.error("[admin] list users DB error:", err.message);
      return res.status(500).json({ detail: "Failed to load users." });
    }
  }
  res.json(store.users.filter((u) => u.orgId === req.user.org_id).map(formatUser));
});

adminRouter.post("/users", async (req, res) => {
  const fullName = String(req.body?.full_name || "").trim();
  const email = String(req.body?.email || "").trim().toLowerCase();
  const password = String(req.body?.password || "");
  if (!fullName || !email || !password) {
    return res.status(400).json({ detail: "Full name, email, and password are required." });
  }

  const pool = getCorePool();
  if (pool) {
    try {
      const dup = await pool.query(
        `SELECT 1 FROM Admin WHERE LOWER(Email) = LOWER($1)
         UNION ALL SELECT 1 FROM "user" WHERE LOWER(Email) = LOWER($1)
         UNION ALL SELECT 1 FROM CommunityEditionUser WHERE LOWER(Email) = LOWER($1)
         LIMIT 1`,
        [email]
      );
      if (dup.rowCount > 0) {
        return res.status(409).json({ detail: "A user with this email already exists." });
      }
      const pwHash = bcrypt.hashSync(password, 10);
      const r = await pool.query(
        `INSERT INTO "user" (OrgID, FirstName, Email, PasswordHash, Status)
         VALUES ($1, $2, $3, $4, TRUE) RETURNING UserID`,
        [req.user.org_id, fullName, email, pwHash]
      );
      return res.json({
        id: Number(r.rows[0].userid),
        full_name: fullName,
        email,
        role: "user",
        role_group: null,
        status: true,
        created_via_admin: true,
      });
    } catch (err) {
      console.error("[admin] create user DB error:", err.message);
      return res.status(500).json({ detail: "Failed to create user." });
    }
  }

  const exists =
    store.admins.some((a) => a.email.toLowerCase() === email) ||
    store.users.some((u) => u.email.toLowerCase() === email) ||
    store.communityUsers.some((u) => u.email.toLowerCase() === email);
  if (exists) return res.status(409).json({ detail: "A user with this email already exists." });

  const user = {
    id: store.nextIds.user++,
    orgId: req.user.org_id,
    fullName,
    email,
    passwordHash: bcrypt.hashSync(password, 10),
    status: true,
    createdViaAdmin: true,
    roleId: null,
  };
  store.users.push(user);
  res.json(formatUser(user));
});

adminRouter.put("/users/:userId", async (req, res) => {
  const userId = Number(req.params.userId);
  if (!Number.isInteger(userId) || userId <= 0) return res.status(400).json({ detail: "Invalid user ID." });
  const pool = getCorePool();
  if (pool) {
    try {
      const cur = await pool.query(
        `SELECT UserID, FirstName, Email, Status FROM "user" WHERE UserID = $1 AND OrgID = $2`,
        [userId, req.user.org_id]
      );
      if (!cur.rows[0]) return res.status(404).json({ detail: "User not found." });
      const nextName = req.body?.full_name !== undefined ? String(req.body.full_name).trim() : cur.rows[0].firstname;
      const nextEmail = req.body?.email !== undefined ? String(req.body.email).trim().toLowerCase() : cur.rows[0].email;
      await pool.query(
        `UPDATE "user" SET FirstName = $1, Email = $2, UpdatedAt = NOW() WHERE UserID = $3 AND OrgID = $4`,
        [nextName, nextEmail, userId, req.user.org_id]
      );
      const roleRes = await pool.query(
        `SELECT r.RoleName FROM UserRole ur JOIN Role r ON r.RoleID = ur.RoleID WHERE ur.UserID = $1 LIMIT 1`,
        [userId]
      );
      return res.json({
        id: userId,
        full_name: nextName,
        email: nextEmail,
        role: "user",
        role_group: roleRes.rows[0]?.rolename || null,
        status: Boolean(cur.rows[0].status),
        created_via_admin: true,
      });
    } catch (err) {
      console.error("[admin] update user DB error:", err.message);
      return res.status(500).json({ detail: "Failed to update user." });
    }
  }

  const user = store.users.find((u) => u.id === userId && u.orgId === req.user.org_id);
  if (!user) return res.status(404).json({ detail: "User not found." });
  if (req.body?.full_name !== undefined) user.fullName = String(req.body.full_name).trim();
  if (req.body?.email !== undefined) user.email = String(req.body.email).trim().toLowerCase();
  res.json(formatUser(user));
});

adminRouter.delete("/users/:userId", async (req, res) => {
  const userId = Number(req.params.userId);
  if (!Number.isInteger(userId) || userId <= 0) return res.status(400).json({ detail: "Invalid user ID." });
  const pool = getCorePool();
  if (pool) {
    const client = await pool.connect();
    try {
      const own = await client.query(`SELECT 1 FROM "user" WHERE UserID = $1 AND OrgID = $2`, [userId, req.user.org_id]);
      if (own.rowCount === 0) return res.status(404).json({ detail: "User not found." });

      await client.query("BEGIN");
      await client.query(`DELETE FROM UserRole WHERE UserID = $1`, [userId]);
      await client.query(`DELETE FROM "user" WHERE UserID = $1 AND OrgID = $2`, [userId, req.user.org_id]);
      await client.query("COMMIT");
      return res.json({ message: "User deleted." });
    } catch (err) {
      await client.query("ROLLBACK").catch(() => {});
      console.error("[admin] delete user DB error:", err.message);
      return res.status(500).json({ detail: "Failed to delete user." });
    } finally {
      client.release();
    }
  }

  const idx = store.users.findIndex((u) => u.id === userId && u.orgId === req.user.org_id);
  if (idx === -1) return res.status(404).json({ detail: "User not found." });
  store.users.splice(idx, 1);
  res.json({ message: "User deleted." });
});

adminRouter.post("/users/:userId/assign-role", async (req, res) => {
  const userId = Number(req.params.userId);
  if (!Number.isInteger(userId) || userId <= 0) return res.status(400).json({ detail: "Invalid user ID." });
  const roleName = String(req.body?.role_name || "").trim();
  const pool = getCorePool();
  if (pool) {
    try {
      const u = await pool.query(`SELECT UserID FROM "user" WHERE UserID = $1 AND OrgID = $2`, [userId, req.user.org_id]);
      if (!u.rows[0]) return res.status(404).json({ detail: "User not found." });

      const r = await pool.query(
        `SELECT RoleID, RoleName FROM Role WHERE OrgID = $1 AND LOWER(RoleName) = LOWER($2) LIMIT 1`,
        [req.user.org_id, roleName]
      );
      if (!r.rows[0]) return res.status(404).json({ detail: "Role not found." });

      const roleId = Number(r.rows[0].roleid);
      await pool.query(`DELETE FROM UserRole WHERE UserID = $1`, [userId]);
      await pool.query(
        `INSERT INTO UserRole (UserID, RoleID, AssignedBy) VALUES ($1, $2, $3)`,
        [userId, roleId, req.user.id]
      );
      return res.json({ message: `Role '${r.rows[0].rolename}' assigned to user ${userId}.` });
    } catch (err) {
      console.error("[admin] assign role DB error:", err.message);
      return res.status(500).json({ detail: "Failed to assign role." });
    }
  }

  const user = store.users.find((u) => u.id === userId && u.orgId === req.user.org_id);
  if (!user) return res.status(404).json({ detail: "User not found." });
  const role = store.roles.find(
    (r) => r.orgId === req.user.org_id && r.name.toLowerCase() === roleName.toLowerCase()
  );
  if (!role) return res.status(404).json({ detail: "Role not found." });
  user.roleId = role.id;
  res.json({ message: `Role '${role.name}' assigned to user ${userId}.` });
});

adminRouter.delete("/users/:userId/unassign-role", async (req, res) => {
  const userId = Number(req.params.userId);
  if (!Number.isInteger(userId) || userId <= 0) return res.status(400).json({ detail: "Invalid user ID." });
  const pool = getCorePool();
  if (pool) {
    try {
      await pool.query(
        `DELETE FROM UserRole WHERE UserID = $1 AND UserID IN (SELECT UserID FROM "user" WHERE OrgID = $2)`,
        [userId, req.user.org_id]
      );
      return res.json({ message: `All roles unassigned from user ${userId}.` });
    } catch (err) {
      console.error("[admin] unassign role DB error:", err.message);
      return res.status(500).json({ detail: "Failed to unassign role." });
    }
  }

  const user = store.users.find((u) => u.id === userId && u.orgId === req.user.org_id);
  if (!user) return res.status(404).json({ detail: "User not found." });
  user.roleId = null;
  res.json({ message: `All roles unassigned from user ${userId}.` });
});

// ---------------- PRODUCTS ----------------
adminRouter.get("/products", async (req, res) => {
  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT p.ProductID, p.ProductCode, p.ProductName, COALESCE(p.Description, '') AS Description,
                COALESCE(p.Version, '1.0') AS Version, p.IsActive, l.Status AS license_status
         FROM License l
         JOIN Product p ON p.ProductID = l.ProductID
         WHERE l.OrgID = $1
         ORDER BY p.ProductID`,
        [req.user.org_id]
      );
      return res.json(
        r.rows.map((row) => ({
          id: Number(row.productid),
          code: row.productcode,
          name: row.productname,
          slug: PRODUCT_SLUGS[row.productcode] || row.productcode.toLowerCase(),
          description: row.description,
          version: row.version,
          purchased: true,
          enabled: Boolean(row.license_status && row.isactive),
        }))
      );
    } catch (err) {
      console.error("[admin] products DB error:", err.message);
      return res.status(500).json({ detail: "Failed to load products." });
    }
  }

  const orgLicenses = store.licenses.filter((l) => l.orgId === req.user.org_id);
  const result = [];
  for (const lic of orgLicenses) {
    const prod = store.products.find((p) => p.id === lic.productId);
    if (!prod) continue;
    result.push({
      id: prod.id,
      code: prod.code,
      name: prod.name,
      slug: prod.slug,
      description: prod.description,
      version: prod.version,
      purchased: true,
      enabled: Boolean(lic.status && prod.isActive),
    });
  }
  res.json(result);
});

adminRouter.patch("/products/:productId/toggle", async (req, res) => {
  const productId = Number(req.params.productId);
  if (!Number.isInteger(productId) || productId <= 0) return res.status(400).json({ detail: "Invalid product ID." });
  const enabled = Boolean(req.body?.enabled);
  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `UPDATE License SET Status = $1 WHERE OrgID = $2 AND ProductID = $3`,
        [enabled, req.user.org_id, productId]
      );
      if (r.rowCount === 0) return res.status(404).json({ detail: "Product not found in your licenses." });
      return res.json({ message: `Product ${enabled ? "enabled" : "disabled"}.` });
    } catch (err) {
      console.error("[admin] toggle product DB error:", err.message);
      return res.status(500).json({ detail: "Failed to update product." });
    }
  }

  const lic = store.licenses.find((l) => l.orgId === req.user.org_id && l.productId === productId);
  if (!lic) return res.status(404).json({ detail: "Product not found in your licenses." });
  lic.status = enabled;
  res.json({ message: `Product ${enabled ? "enabled" : "disabled"}.` });
});

// ---------------- ROLE PERMISSIONS ----------------
adminRouter.get("/roles/:roleId/permissions", async (req, res) => {
  const roleId = Number(req.params.roleId);
  if (!Number.isInteger(roleId) || roleId <= 0) return res.status(400).json({ detail: "Invalid role ID." });
  const pool = getCorePool();
  if (pool) {
    try {
      const roleChk = await pool.query(
        `SELECT 1 FROM Role WHERE RoleID = $1 AND OrgID = $2`,
        [roleId, req.user.org_id]
      );
      if (roleChk.rowCount === 0) return res.status(404).json({ detail: "Role not found." });

      const r = await pool.query(
        `SELECT l.ProductID,
                COALESCE(rpa.CanView, FALSE) AS can_view,
                COALESCE(rpa.CanEdit, FALSE) AS can_edit,
                COALESCE(rpa.CanExecute, FALSE) AS can_execute
         FROM License l
         LEFT JOIN RoleProductAccess rpa ON rpa.ProductID = l.ProductID AND rpa.RoleID = $1
         WHERE l.OrgID = $2
         ORDER BY l.ProductID`,
        [roleId, req.user.org_id]
      );
      return res.json(
        r.rows.map((row) => ({
          product_id: Number(row.productid),
          can_view: Boolean(row.can_view),
          can_edit: Boolean(row.can_edit),
          can_execute: Boolean(row.can_execute),
        }))
      );
    } catch (err) {
      console.error("[admin] get permissions DB error:", err.message);
      return res.status(500).json({ detail: "Failed to load permissions." });
    }
  }

  const role = store.roles.find((r) => r.id === roleId && r.orgId === req.user.org_id);
  if (!role) return res.status(404).json({ detail: "Role not found." });
  const existing = store.rolePermissions.get(roleId) || [];
  const licensed = store.licenses.filter((l) => l.orgId === req.user.org_id);
  res.json(
    licensed.map((lic) => {
      const found = existing.find((p) => p.product_id === lic.productId);
      return found || { product_id: lic.productId, can_view: false, can_edit: false, can_execute: false };
    })
  );
});

adminRouter.post("/roles/:roleId/permissions", async (req, res) => {
  const roleId = Number(req.params.roleId);
  if (!Number.isInteger(roleId) || roleId <= 0) return res.status(400).json({ detail: "Invalid role ID." });
  const permissions = Array.isArray(req.body?.permissions) ? req.body.permissions : [];
  const pool = getCorePool();
  if (pool) {
    const client = await pool.connect();
    try {
      const roleChk = await client.query(
        `SELECT 1 FROM Role WHERE RoleID = $1 AND OrgID = $2`,
        [roleId, req.user.org_id]
      );
      if (roleChk.rowCount === 0) return res.status(404).json({ detail: "Role not found." });

      const licRes = await client.query(`SELECT ProductID FROM License WHERE OrgID = $1`, [req.user.org_id]);
      const licensedIds = new Set(licRes.rows.map((r) => Number(r.productid)));

      await client.query("BEGIN");
      await client.query(`DELETE FROM RoleProductAccess WHERE RoleID = $1`, [roleId]);
      for (const p of permissions) {
        const pid = Number(p.product_id);
        if (!Number.isInteger(pid) || !licensedIds.has(pid)) continue;
        await client.query(
          `INSERT INTO RoleProductAccess (RoleID, ProductID, CanView, CanEdit, CanExecute, AssignedBy)
           VALUES ($1, $2, $3, $4, $5, $6)`,
          [roleId, pid, Boolean(p.can_view), Boolean(p.can_edit), Boolean(p.can_execute), req.user.id]
        );
      }
      await client.query("COMMIT");
      return res.json({ message: "Permissions saved." });
    } catch (err) {
      await client.query("ROLLBACK").catch(() => {});
      console.error("[admin] save permissions DB error:", err.message);
      return res.status(500).json({ detail: "Failed to save permissions." });
    } finally {
      client.release();
    }
  }

  const role = store.roles.find((r) => r.id === roleId && r.orgId === req.user.org_id);
  if (!role) return res.status(404).json({ detail: "Role not found." });
  store.rolePermissions.set(
    roleId,
    permissions.map((p) => ({
      product_id: Number(p.product_id),
      can_view: Boolean(p.can_view),
      can_edit: Boolean(p.can_edit),
      can_execute: Boolean(p.can_execute),
    }))
  );
  res.json({ message: "Permissions saved." });
});
