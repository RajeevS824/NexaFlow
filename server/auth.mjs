import express from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import crypto from "node:crypto";
import { getCorePool } from "./db.mjs";
import {
  store,
  PRODUCT_SLUGS,
  getOrgLicensedProducts,
  getUserRoleProducts,
} from "./store.mjs";

const EPHEMERAL_JWT_SECRET = crypto.randomBytes(32).toString("hex");
function getJwtSecret() {
  return process.env.JWT_SECRET_KEY || EPHEMERAL_JWT_SECRET;
}
const JWT_EXPIRES_IN = `${Number(process.env.JWT_EXPIRE_MINUTES || 480)}m`;

export function signToken(payload) {
  return jwt.sign(payload, getJwtSecret(), { expiresIn: JWT_EXPIRES_IN });
}

export function verifyToken(token) {
  try {
    return jwt.verify(token, getJwtSecret());
  } catch {
    return null;
  }
}

export function extractBearerOrQueryToken(req) {
  const auth = req.headers.authorization || "";
  if (auth.toLowerCase().startsWith("bearer ")) {
    return auth.slice(7).trim();
  }
  if (typeof req.query?.token === "string" && req.query.token.trim()) {
    return req.query.token.trim();
  }
  return null;
}

async function resolveAccountFromPayload(payload) {
  if (!payload || !payload.sub) return null;
  const id = Number(payload.sub);
  const accountType = payload.account_type || "enterprise";
  const role = payload.role || "user";
  const pool = getCorePool();

  if (pool) {
    try {
      if (role === "admin") {
        const r = await pool.query(
          `SELECT a.AdminID, a.OrgID, a.FullName, a.Email, o.OrganizationName
           FROM Admin a JOIN Organization o ON o.OrgID = a.OrgID
           WHERE a.AdminID = $1`,
          [id]
        );
        const row = r.rows[0];
        if (!row) return null;
        return {
          id: Number(row.adminid),
          org_id: Number(row.orgid),
          org_name: row.organizationname,
          full_name: row.fullname,
          email: row.email,
          role: "admin",
          account_type: "enterprise",
        };
      }
      if (accountType === "community") {
        const r = await pool.query(
          `SELECT c.CommunityEditionUserID, c.OrgID, c.FullName, c.Email, c.Status, o.OrganizationName
           FROM CommunityEditionUser c JOIN Organization o ON o.OrgID = c.OrgID
           WHERE c.CommunityEditionUserID = $1`,
          [id]
        );
        const row = r.rows[0];
        if (!row || !row.status) return null;
        return {
          id: Number(row.communityeditionuserid),
          org_id: Number(row.orgid),
          org_name: row.organizationname,
          full_name: row.fullname,
          email: row.email,
          role: "user",
          account_type: "community",
        };
      }
      const r = await pool.query(
        `SELECT u.UserID, u.OrgID, u.FirstName, u.Email, u.Status, o.OrganizationName
         FROM "user" u JOIN Organization o ON o.OrgID = u.OrgID
         WHERE u.UserID = $1`,
        [id]
      );
      const row = r.rows[0];
      if (!row || !row.status) return null;
      return {
        id: Number(row.userid),
        org_id: Number(row.orgid),
        org_name: row.organizationname,
        full_name: row.firstname,
        email: row.email,
        role: "user",
        account_type: "enterprise",
      };
    } catch (err) {
      console.error("[auth] DB session lookup failed:", err.message);
      return null;
    }
  }

  if (role === "admin") {
    const admin = store.admins.find((a) => a.id === id);
    if (!admin) return null;
    const org = store.organizations.find((o) => o.id === admin.orgId);
    return {
      id: admin.id,
      org_id: admin.orgId,
      org_name: org?.name || "onenextgen",
      full_name: admin.fullName,
      email: admin.email,
      role: "admin",
      account_type: "enterprise",
    };
  }

  if (accountType === "community") {
    const cu = store.communityUsers.find((u) => u.id === id);
    if (!cu || !cu.status) return null;
    const org = store.organizations.find((o) => o.id === cu.orgId);
    return {
      id: cu.id,
      org_id: cu.orgId,
      org_name: org?.name || "Community",
      full_name: cu.fullName,
      email: cu.email,
      role: "user",
      account_type: "community",
    };
  }

  const user = store.users.find((u) => u.id === id);
  if (!user || !user.status) return null;
  const org = store.organizations.find((o) => o.id === user.orgId);
  return {
    id: user.id,
    org_id: user.orgId,
    org_name: org?.name || "onenextgen",
    full_name: user.fullName,
    email: user.email,
    role: "user",
    account_type: "enterprise",
  };
}

export { resolveAccountFromPayload };

export async function requireUser(req, res, next) {
  const token = extractBearerOrQueryToken(req);
  if (!token) {
    return res.status(401).json({ detail: "Not authenticated." });
  }
  const payload = verifyToken(token);
  const account = await resolveAccountFromPayload(payload);
  if (!account) {
    return res.status(401).json({ detail: "Invalid or expired token." });
  }
  req.user = account;
  return next();
}

export function requireAdmin(req, res, next) {
  requireUser(req, res, () => {
    if (req.user.role !== "admin") {
      return res.status(403).json({ detail: "Admin privileges required." });
    }
    return next();
  });
}

async function fetchProductsForAccount(account) {
  const pool = getCorePool();
  if (!pool) {
    return account.account_type === "enterprise" && account.role !== "admin"
      ? getUserRoleProducts(account.id, account.org_id)
      : getOrgLicensedProducts(account.org_id);
  }

  if (account.account_type === "enterprise" && account.role !== "admin") {
    const r = await pool.query(
      `SELECT p.ProductID, p.ProductCode, p.ProductName, rpa.CanView, rpa.CanEdit, rpa.CanExecute
       FROM UserRole ur
       JOIN Role r ON r.RoleID = ur.RoleID
       JOIN RoleProductAccess rpa ON rpa.RoleID = r.RoleID
       JOIN Product p ON p.ProductID = rpa.ProductID
       JOIN License l ON l.ProductID = p.ProductID AND l.OrgID = $1
       WHERE ur.UserID = $2
         AND r.Status = TRUE
         AND rpa.CanView = TRUE
         AND p.IsActive = TRUE
         AND l.Status = TRUE
       ORDER BY p.ProductID`,
      [account.org_id, account.id]
    );
    return r.rows.map((row) => ({
      id: Number(row.productid),
      code: row.productcode,
      name: row.productname,
      slug: PRODUCT_SLUGS[row.productcode] || row.productcode.toLowerCase(),
      can_view: Boolean(row.canview),
      can_edit: Boolean(row.canedit),
      can_execute: Boolean(row.canexecute),
    }));
  }

  const r = await pool.query(
    `SELECT p.ProductID, p.ProductCode, p.ProductName
     FROM License l
     JOIN Product p ON p.ProductID = l.ProductID
     WHERE l.OrgID = $1 AND l.Status = TRUE AND p.IsActive = TRUE
     ORDER BY p.ProductID`,
    [account.org_id]
  );
  return r.rows.map((row) => ({
    id: Number(row.productid),
    code: row.productcode,
    name: row.productname,
    slug: PRODUCT_SLUGS[row.productcode] || row.productcode.toLowerCase(),
  }));
}

async function buildLoginResponse(account) {
  const products = await fetchProductsForAccount(account);
  const token = signToken({
    sub: String(account.id),
    email: account.email,
    role: account.role,
    account_type: account.account_type,
    org_id: account.org_id,
  });

  return {
    token,
    user_id: account.id,
    full_name: account.full_name,
    email: account.email,
    role: account.role,
    account_type: account.account_type,
    org_id: account.org_id,
    org_name: account.org_name,
    products,
  };
}

export const authRouter = express.Router();

authRouter.post("/login", async (req, res) => {
  const email = String(req.body?.email || "").trim().toLowerCase();
  const password = String(req.body?.password || "");

  if (!email || !password) {
    return res.status(400).json({ detail: "Email and password are required." });
  }

  const pool = getCorePool();
  if (pool) {
    try {
      const aRes = await pool.query(
        `SELECT a.AdminID, a.OrgID, a.FullName, a.Email, a.PasswordHash, o.OrganizationName
         FROM Admin a JOIN Organization o ON o.OrgID = a.OrgID
         WHERE LOWER(a.Email) = LOWER($1) LIMIT 1`,
        [email]
      );
      const admin = aRes.rows[0];
      if (admin && admin.passwordhash && bcrypt.compareSync(password, admin.passwordhash)) {
        return res.json(
          await buildLoginResponse({
            id: Number(admin.adminid),
            org_id: Number(admin.orgid),
            org_name: admin.organizationname,
            full_name: admin.fullname,
            email: admin.email,
            role: "admin",
            account_type: "enterprise",
          })
        );
      }

      const uRes = await pool.query(
        `SELECT u.UserID, u.OrgID, u.FirstName, u.Email, u.PasswordHash, u.Status, o.OrganizationName
         FROM "user" u JOIN Organization o ON o.OrgID = u.OrgID
         WHERE LOWER(u.Email) = LOWER($1) LIMIT 1`,
        [email]
      );
      const ent = uRes.rows[0];
      if (ent) {
        if (!ent.status) {
          return res.status(403).json({ detail: "Your account has been deactivated." });
        }
        if (ent.passwordhash && bcrypt.compareSync(password, ent.passwordhash)) {
          return res.json(
            await buildLoginResponse({
              id: Number(ent.userid),
              org_id: Number(ent.orgid),
              org_name: ent.organizationname,
              full_name: ent.firstname,
              email: ent.email,
              role: "user",
              account_type: "enterprise",
            })
          );
        }
      }

      const cRes = await pool.query(
        `SELECT c.CommunityEditionUserID, c.OrgID, c.FullName, c.Email, c.PasswordHash, c.Status, o.OrganizationName
         FROM CommunityEditionUser c JOIN Organization o ON o.OrgID = c.OrgID
         WHERE LOWER(c.Email) = LOWER($1) LIMIT 1`,
        [email]
      );
      const com = cRes.rows[0];
      if (com) {
        if (!com.status) {
          return res.status(403).json({ detail: "Your account has been deactivated." });
        }
        if (com.passwordhash && bcrypt.compareSync(password, com.passwordhash)) {
          return res.json(
            await buildLoginResponse({
              id: Number(com.communityeditionuserid),
              org_id: Number(com.orgid),
              org_name: com.organizationname,
              full_name: com.fullname,
              email: com.email,
              role: "user",
              account_type: "community",
            })
          );
        }
      }

      return res.status(401).json({ detail: "Invalid email or password." });
    } catch (err) {
      console.error("[auth] Login DB error:", err.message);
      return res.status(500).json({ detail: "Login failed." });
    }
  }

  // In-memory fallback
  const admin = store.admins.find((a) => a.email.toLowerCase() === email);
  if (admin && bcrypt.compareSync(password, admin.passwordHash)) {
    const org = store.organizations.find((o) => o.id === admin.orgId);
    return res.json(
      await buildLoginResponse({
        id: admin.id,
        org_id: admin.orgId,
        org_name: org?.name || "onenextgen",
        full_name: admin.fullName,
        email: admin.email,
        role: "admin",
        account_type: "enterprise",
      })
    );
  }

  const entUser = store.users.find((u) => u.email.toLowerCase() === email);
  if (entUser) {
    if (!entUser.status) {
      return res.status(403).json({ detail: "Your account has been deactivated." });
    }
    if (bcrypt.compareSync(password, entUser.passwordHash)) {
      const org = store.organizations.find((o) => o.id === entUser.orgId);
      return res.json(
        await buildLoginResponse({
          id: entUser.id,
          org_id: entUser.orgId,
          org_name: org?.name || "onenextgen",
          full_name: entUser.fullName,
          email: entUser.email,
          role: "user",
          account_type: "enterprise",
        })
      );
    }
  }

  const comUser = store.communityUsers.find((u) => u.email.toLowerCase() === email);
  if (comUser) {
    if (!comUser.status) {
      return res.status(403).json({ detail: "Your account has been deactivated." });
    }
    if (bcrypt.compareSync(password, comUser.passwordHash)) {
      const org = store.organizations.find((o) => o.id === comUser.orgId);
      return res.json(
        await buildLoginResponse({
          id: comUser.id,
          org_id: comUser.orgId,
          org_name: org?.name || "Community",
          full_name: comUser.fullName,
          email: comUser.email,
          role: "user",
          account_type: "community",
        })
      );
    }
  }

  return res.status(401).json({ detail: "Invalid email or password." });
});

authRouter.post("/register", async (req, res) => {
  const fullName = String(req.body?.full_name || "").trim();
  const email = String(req.body?.email || "").trim().toLowerCase();
  const companyName = String(req.body?.company_name || "My Company").trim() || "My Company";
  const password = String(req.body?.password || "");

  if (!fullName || !email || !password) {
    return res.status(400).json({ detail: "Full name, email, and password are required." });
  }

  const pool = getCorePool();
  if (pool) {
    const client = await pool.connect();
    try {
      const dup = await client.query(
        `SELECT 1 FROM Admin WHERE LOWER(Email) = LOWER($1)
         UNION ALL SELECT 1 FROM "user" WHERE LOWER(Email) = LOWER($1)
         UNION ALL SELECT 1 FROM CommunityEditionUser WHERE LOWER(Email) = LOWER($1)
         LIMIT 1`,
        [email]
      );
      if (dup.rowCount > 0) {
        return res.status(409).json({ detail: "An account with this email already exists." });
      }

      await client.query("BEGIN");
      const suffix = crypto.randomBytes(4).toString("hex");
      const baseSlug = companyName.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 60) || "community";
      const slug = `${baseSlug}-${suffix}`;
      const code = `COM-${suffix.toUpperCase()}`;

      const orgRes = await client.query(
        `INSERT INTO Organization (OrganizationName, OrganizationSlug, CompanyCode, Email, Address, Status)
         VALUES ($1, $2, $3, $4, '', TRUE) RETURNING OrgID`,
        [companyName, slug, code, email]
      );
      const orgId = Number(orgRes.rows[0].orgid);

      const prodRes = await client.query(`SELECT ProductID, ProductCode FROM Product WHERE IsActive = TRUE`);
      const today = new Date().toISOString().slice(0, 10);
      for (const p of prodRes.rows) {
        const licKey = `COM-${p.productcode}-${orgId}-${new Date().getFullYear()}`;
        await client.query(
          `INSERT INTO License (LicenseKey, OrgID, ProductID, PurchaseDate, Status)
           VALUES ($1, $2, $3, $4, TRUE)`,
          [licKey, orgId, Number(p.productid), today]
        );
      }

      const pwHash = bcrypt.hashSync(password, 10);
      const cuRes = await client.query(
        `INSERT INTO CommunityEditionUser (OrgID, FullName, Email, PasswordHash)
         VALUES ($1, $2, $3, $4) RETURNING CommunityEditionUserID`,
        [orgId, fullName, email, pwHash]
      );
      const userId = Number(cuRes.rows[0].communityeditionuserid);
      await client.query("COMMIT");

      return res.json(
        await buildLoginResponse({
          id: userId,
          org_id: orgId,
          org_name: companyName,
          full_name: fullName,
          email,
          role: "user",
          account_type: "community",
        })
      );
    } catch (err) {
      await client.query("ROLLBACK").catch(() => {});
      console.error("[auth] Register DB error:", err.message);
      return res.status(500).json({ detail: "Registration failed." });
    } finally {
      client.release();
    }
  }

  const exists =
    store.admins.some((a) => a.email.toLowerCase() === email) ||
    store.users.some((u) => u.email.toLowerCase() === email) ||
    store.communityUsers.some((u) => u.email.toLowerCase() === email);

  if (exists) {
    return res.status(409).json({ detail: "An account with this email already exists." });
  }

  const orgId = store.nextIds.org++;
  const suffix = crypto.randomBytes(4).toString("hex");
  const baseSlug = companyName.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 60) || "community";
  store.organizations.push({
    id: orgId,
    name: companyName,
    slug: `${baseSlug}-${suffix}`,
    code: `COM-${suffix.toUpperCase()}`,
    email,
    address: "",
    status: true,
  });

  for (const prod of store.products) {
    if (prod.isActive) {
      store.licenses.push({
        id: store.licenses.length + 1,
        orgId,
        productId: prod.id,
        licenseKey: `COM-${prod.code}-${orgId}-${new Date().getFullYear()}`,
        purchaseDate: new Date().toISOString().slice(0, 10),
        status: true,
      });
    }
  }

  const userId = store.nextIds.communityUser++;
  const newUser = {
    id: userId,
    orgId,
    fullName,
    email,
    passwordHash: bcrypt.hashSync(password, 10),
    status: true,
  };
  store.communityUsers.push(newUser);

  return res.json(
    await buildLoginResponse({
      id: newUser.id,
      org_id: orgId,
      org_name: companyName,
      full_name: fullName,
      email,
      role: "user",
      account_type: "community",
    })
  );
});

authRouter.get("/me", requireUser, async (req, res) => {
  const account = req.user;
  const products = await fetchProductsForAccount(account);

  res.json({
    user_id: account.id,
    full_name: account.full_name,
    email: account.email,
    role: account.role,
    account_type: account.account_type,
    org_id: account.org_id,
    org_name: account.org_name,
    products,
  });
});

authRouter.post("/forgot-password", async (req, res) => {
  const email = String(req.body?.email || "").trim().toLowerCase();
  if (!email) {
    return res.status(400).json({ detail: "Email is required." });
  }

  const pool = getCorePool();
  if (pool) {
    try {
      let match = null;
      const a = await pool.query(`SELECT AdminID, Email FROM Admin WHERE LOWER(Email) = LOWER($1) LIMIT 1`, [email]);
      if (a.rows[0]) match = { type: "admin", id: Number(a.rows[0].adminid), email: a.rows[0].email };
      if (!match) {
        const u = await pool.query(`SELECT UserID, Email FROM "user" WHERE LOWER(Email) = LOWER($1) LIMIT 1`, [email]);
        if (u.rows[0]) match = { type: "user", id: Number(u.rows[0].userid), email: u.rows[0].email };
      }
      if (!match) {
        const c = await pool.query(
          `SELECT CommunityEditionUserID, Email FROM CommunityEditionUser WHERE LOWER(Email) = LOWER($1) LIMIT 1`,
          [email]
        );
        if (c.rows[0]) match = { type: "community", id: Number(c.rows[0].communityeditionuserid), email: c.rows[0].email };
      }
      if (match) {
        const token = crypto.randomBytes(24).toString("hex");
        const expiresAt = new Date(Date.now() + 3600 * 1000);
        await pool.query(
          `INSERT INTO PasswordResetToken (Token, AccountType, AccountID, Email, ExpiresAt)
           VALUES ($1, $2, $3, $4, $5)`,
          [token, match.type, match.id, match.email, expiresAt]
        );
      }
      return res.json({
        message: "If an account with that email exists, a password reset link has been sent.",
      });
    } catch (err) {
      console.error("[auth] forgot-password DB error:", err.message);
      return res.status(500).json({ detail: "Failed to process password reset request." });
    }
  }

  let match = null;
  const admin = store.admins.find((a) => a.email.toLowerCase() === email);
  if (admin) match = { type: "admin", id: admin.id, email: admin.email };
  const ent = !match && store.users.find((u) => u.email.toLowerCase() === email);
  if (ent) match = { type: "user", id: ent.id, email: ent.email };
  const com = !match && store.communityUsers.find((u) => u.email.toLowerCase() === email);
  if (com) match = { type: "community", id: com.id, email: com.email };

  if (match) {
    const token = crypto.randomBytes(24).toString("hex");
    store.passwordResetTokens.set(token, {
      accountType: match.type,
      accountId: match.id,
      email: match.email,
      expiresAt: Date.now() + 3600 * 1000,
      used: false,
    });
  }

  return res.json({
    message: "If an account with that email exists, a password reset link has been sent.",
  });
});

authRouter.get("/reset-password/:token/validate", async (req, res) => {
  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT ExpiresAt, UsedAt FROM PasswordResetToken WHERE Token = $1 LIMIT 1`,
        [req.params.token]
      );
      const row = r.rows[0];
      const valid = Boolean(row && !row.usedat && new Date(row.expiresat).getTime() > Date.now());
      return res.json({ valid });
    } catch {
      return res.json({ valid: false });
    }
  }

  const entry = store.passwordResetTokens.get(req.params.token);
  const valid = Boolean(entry && !entry.used && entry.expiresAt > Date.now());
  res.json({ valid });
});

authRouter.post("/reset-password", async (req, res) => {
  const token = String(req.body?.token || "");
  const newPassword = String(req.body?.new_password || "");
  if (newPassword.length < 6) {
    return res.status(400).json({ detail: "Password must be at least 6 characters." });
  }

  const pool = getCorePool();
  if (pool) {
    try {
      const r = await pool.query(
        `SELECT AccountType, AccountID, ExpiresAt, UsedAt FROM PasswordResetToken WHERE Token = $1 LIMIT 1`,
        [token]
      );
      const row = r.rows[0];
      if (!row || row.usedat || new Date(row.expiresat).getTime() <= Date.now()) {
        return res.status(400).json({ detail: "Invalid or expired reset token." });
      }
      const hash = bcrypt.hashSync(newPassword, 10);
      if (row.accounttype === "admin") {
        await pool.query(`UPDATE Admin SET PasswordHash = $1, UpdatedAt = NOW() WHERE AdminID = $2`, [hash, row.accountid]);
      } else if (row.accounttype === "user") {
        await pool.query(`UPDATE "user" SET PasswordHash = $1, UpdatedAt = NOW() WHERE UserID = $2`, [hash, row.accountid]);
      } else if (row.accounttype === "community") {
        await pool.query(`UPDATE CommunityEditionUser SET PasswordHash = $1, UpdatedAt = NOW() WHERE CommunityEditionUserID = $2`, [hash, row.accountid]);
      }
      await pool.query(`UPDATE PasswordResetToken SET UsedAt = NOW() WHERE Token = $1`, [token]);
      return res.json({ message: "Password has been reset successfully." });
    } catch (err) {
      console.error("[auth] reset-password DB error:", err.message);
      return res.status(500).json({ detail: "Failed to reset password." });
    }
  }

  const entry = store.passwordResetTokens.get(token);
  if (!entry || entry.used || entry.expiresAt <= Date.now()) {
    return res.status(400).json({ detail: "Invalid or expired reset token." });
  }

  const hash = bcrypt.hashSync(newPassword, 10);
  if (entry.accountType === "admin") {
    const a = store.admins.find((x) => x.id === entry.accountId);
    if (a) a.passwordHash = hash;
  } else if (entry.accountType === "user") {
    const u = store.users.find((x) => x.id === entry.accountId);
    if (u) u.passwordHash = hash;
  } else if (entry.accountType === "community") {
    const c = store.communityUsers.find((x) => x.id === entry.accountId);
    if (c) c.passwordHash = hash;
  }

  entry.used = true;
  return res.json({ message: "Password has been reset successfully." });
});

export const contactRouter = express.Router();

contactRouter.post("/message", async (req, res) => {
  const { full_name, email, company_name, message } = req.body || {};
  const pool = getCorePool();
  if (pool) {
    try {
      await pool.query(
        `INSERT INTO ContactMessage (FullName, Email, CompanyName, Message, EmailSent)
         VALUES ($1, $2, $3, $4, FALSE)`,
        [full_name || "", email || "", company_name || "", message || ""]
      );
    } catch (err) {
      console.error("[contact] DB insert failed:", err.message);
    }
  } else {
    store.contactMessages.push({
      id: store.nextIds.contact++,
      full_name: full_name || "",
      email: email || "",
      company_name: company_name || "",
      message: message || "",
      createdAt: new Date().toISOString(),
    });
  }
  res.json({ message: "Thank you for contacting us! Our team will get back to you shortly." });
});

contactRouter.post("/request-demo", async (req, res) => {
  const { full_name, email, company_name, message } = req.body || {};
  const pool = getCorePool();
  if (pool) {
    try {
      await pool.query(
        `INSERT INTO DemoRequest (FullName, Email, CompanyName, Message, EmailSent)
         VALUES ($1, $2, $3, $4, FALSE)`,
        [full_name || "", email || "", company_name || "", message || ""]
      );
    } catch (err) {
      console.error("[contact] DemoRequest DB insert failed:", err.message);
    }
  } else {
    store.demoRequests.push({
      id: store.nextIds.demo++,
      full_name: full_name || "",
      email: email || "",
      company_name: company_name || "",
      message: message || "",
      createdAt: new Date().toISOString(),
    });
  }
  res.json({ message: "Your demo request has been received! We will reach out soon." });
});
