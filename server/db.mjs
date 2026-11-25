import pg from "pg";

const { Pool } = pg;

function buildDbCandidates(rawUrl, extraNames = []) {
  if (!rawUrl) return [];
  try {
    const parsed = new URL(rawUrl);
    const origName = parsed.pathname.replace(/^\//, "");
    const candidates = [origName, origName.toLowerCase(), ...extraNames].filter(Boolean);
    const seen = new Set();
    return candidates
      .filter((name) => {
        if (seen.has(name)) return false;
        seen.add(name);
        return true;
      })
      .map((name) => {
        const u = new URL(rawUrl);
        u.pathname = "/" + encodeURIComponent(name);
        return { name, url: u.toString() };
      });
  } catch {
    return [{ name: "default", url: rawUrl }];
  }
}

async function connectWithFallback(rawUrl, extraNames, label) {
  const candidates = buildDbCandidates(rawUrl, extraNames);
  for (const cand of candidates) {
    const pool = new Pool({
      connectionString: cand.url,
      connectionTimeoutMillis: 6000,
      idleTimeoutMillis: 30000,
      max: 10,
    });
    try {
      await pool.query("SELECT 1");
      console.log(`[DB] Connected ${label} pool to database "${cand.name}"`);
      return pool;
    } catch (err) {
      await pool.end().catch(() => {});
      if (err?.code === "3D000") {
        continue; // try next database name candidate
      }
      console.warn(`[DB] ${label} database "${cand.name}" unreachable (${err?.code || err?.message}); using in-memory fallback`);
      return null;
    }
  }
  if (candidates.length > 0) {
    console.warn(`[DB] No matching ${label} database found; using in-memory fallback`);
  }
  return null;
}

let corePool = null;
let bmPool = null;

export async function initDatabases() {
  const coreUrl = process.env.DATABASE_URL?.trim();
  const bmUrl = process.env.BUSINESSMAP_DATABASE_URL?.trim();

  const [cPool, bPool] = await Promise.all([
    coreUrl ? connectWithFallback(coreUrl, ["dev.onenextgendb", "onenextgendb"], "Core") : null,
    bmUrl ? connectWithFallback(bmUrl, ["onenextgenbusinessmapdb"], "BusinessMap") : null,
  ]);

  corePool = cPool;
  bmPool = bPool;
}

export function getCorePool() {
  return corePool;
}

export function getBmPool() {
  return bmPool;
}
