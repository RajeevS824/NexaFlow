import "dotenv/config";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import cors from "cors";

import { initDatabases, getCorePool, getBmPool } from "./server/db.mjs";
import { authRouter, contactRouter, requireUser } from "./server/auth.mjs";
import { adminRouter } from "./server/admin.mjs";
import {
  documentParserRouter,
  attachDocumentParserWs,
  DP_OUTPUT_ROOT,
} from "./server/documentParser.mjs";
import { businessMapRouter } from "./server/businessMap.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.join(__dirname, "Core-App-Frontend");
const FRONTEND_DIST = path.join(FRONTEND_ROOT, "dist");
const PORT = Number(process.env.PORT || 3000);
const HOST = "0.0.0.0";
const IS_PROD = process.env.NODE_ENV === "production";

async function startServer() {
  await initDatabases();

  const app = express();
  const server = http.createServer(app);

  const configuredOrigins = new Set(
    String(process.env.ALLOWED_ORIGINS || "http://localhost:3000,http://127.0.0.1:3000")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );

  app.use(
    cors((req, callback) => {
      const origin = req.headers.origin;
      if (!origin) return callback(null, { origin: false });
      try {
        const originUrl = new URL(origin);
        const originHost = originUrl.host;
        const reqHost = String(req.headers["x-forwarded-host"] || req.headers.host || "").split(",")[0].trim();
        const isAiStudioRunApp =
          originUrl.protocol === "https:" && /^ais-[a-z0-9-]+(\.[a-z0-9-]+)*\.run\.app$/i.test(originUrl.hostname);
        const allowed =
          configuredOrigins.has(origin) ||
          isAiStudioRunApp ||
          (reqHost && originHost === reqHost);
        return callback(null, { origin: allowed, credentials: allowed });
      } catch {
        return callback(null, { origin: false });
      }
    })
  );
  app.use(express.json({ limit: "25mb" }));
  app.use(express.urlencoded({ extended: true, limit: "25mb" }));

  // Health check
  app.get("/health", (_req, res) => {
    res.json({
      status: "ok",
      services: {
        core: getCorePool() ? "postgresql" : "in-memory",
        document_parser: "in-memory",
        business_map: getBmPool() ? "postgresql" : "in-memory",
      },
    });
  });

  // Core-App-Backend routes
  app.use("/api/auth", authRouter);
  app.use("/api/contact", contactRouter);
  app.use("/api/admin", adminRouter);

  // Document Parser routes + output image static serving
  app.use("/document", documentParserRouter);
  app.use("/output", requireUser, express.static(DP_OUTPUT_ROOT));
  attachDocumentParserWs(server);

  // Business Map routes
  app.use("/bm", businessMapRouter);

  if (IS_PROD) {
    app.use(express.static(FRONTEND_DIST));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(FRONTEND_DIST, "index.html"));
    });
  } else {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      root: FRONTEND_ROOT,
      configFile: path.join(FRONTEND_ROOT, "vite.config.js"),
      server: {
        middlewareMode: true,
        hmr: false,
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  }

  server.listen(PORT, HOST, () => {
    console.log(`[NexaFlow] Server listening on http://${HOST}:${PORT} (${IS_PROD ? "production" : "development"})`);
  });
}

startServer().catch((err) => {
  console.error("[NexaFlow] Failed to start server:", err);
  process.exit(1);
});
