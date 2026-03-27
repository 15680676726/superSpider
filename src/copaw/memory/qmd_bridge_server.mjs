import { createServer } from "node:http";
import { isAbsolute } from "node:path";
import { pathToFileURL } from "node:url";

const dbPath = process.env.COPAW_QMD_BRIDGE_DB_PATH || "";
const host = process.env.COPAW_QMD_BRIDGE_HOST || "127.0.0.1";
const port = Number.parseInt(process.env.COPAW_QMD_BRIDGE_PORT || "8765", 10);
const defaultCollection = process.env.COPAW_QMD_BRIDGE_COLLECTION_NAME || "";
const sdkIndexEntry = process.env.COPAW_QMD_BRIDGE_SDK_INDEX_ENTRY || "";
const sdkStoreEntry = process.env.COPAW_QMD_BRIDGE_SDK_STORE_ENTRY || "";

if (!dbPath || !sdkIndexEntry || !sdkStoreEntry) {
  throw new Error("Missing required CoPaw QMD bridge environment variables.");
}

function normalizeImportSpecifier(specifier) {
  const normalized = String(specifier || "").trim();
  if (!normalized) {
    throw new Error("Missing import specifier for CoPaw QMD bridge.");
  }
  if (/^[a-zA-Z]:[\\/]/.test(normalized) || normalized.startsWith("\\\\") || isAbsolute(normalized)) {
    return pathToFileURL(normalized).href;
  }
  return normalized;
}

const { createStore, extractSnippet, addLineNumbers } = await import(
  normalizeImportSpecifier(sdkIndexEntry),
);
const { structuredSearch } = await import(normalizeImportSpecifier(sdkStoreEntry));

const store = await createStore({ dbPath });
const startedAt = Date.now();

function collectBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}

function writeJson(res, statusCode, payload) {
  res.writeHead(statusCode, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

function normalizedCollections(collections) {
  if (Array.isArray(collections) && collections.length > 0) {
    return collections.map((item) => String(item || "").trim()).filter(Boolean);
  }
  if (defaultCollection) {
    return [defaultCollection];
  }
  return undefined;
}

async function runStructuredQuery(params) {
  const searches = Array.isArray(params?.searches)
    ? params.searches.map((item) => ({
        type: String(item?.type || "").trim(),
        query: String(item?.query || "").trim(),
      })).filter((item) => item.type && item.query)
    : [];
  if (searches.length === 0) {
    throw new Error("Missing required field: searches");
  }
  const collections = normalizedCollections(params?.collections);
  const result = await structuredSearch(
    store.internal,
    searches,
    {
      collections,
      limit: Number.isFinite(params?.limit) ? Number(params.limit) : 10,
      minScore: Number.isFinite(params?.minScore) ? Number(params.minScore) : 0,
      candidateLimit: Number.isFinite(params?.candidateLimit)
        ? Number(params.candidateLimit)
        : undefined,
      intent: params?.intent ? String(params.intent) : undefined,
      skipRerank: params?.skipRerank === true,
    },
  );
  const primaryQuery =
    searches.find((item) => item.type === "lex")?.query
    || searches.find((item) => item.type === "vec")?.query
    || searches[0]?.query
    || "";
  return result.map((item) => {
    const { line, snippet } = extractSnippet(
      item.bestChunk,
      primaryQuery,
      300,
      undefined,
      undefined,
      params?.intent ? String(params.intent) : undefined,
    );
    return {
      docid: `#${item.docid}`,
      filepath: item.displayPath,
      file: item.displayPath,
      title: item.title,
      score: Math.round(item.score * 100) / 100,
      context: item.context,
      snippet: addLineNumbers(snippet, line),
    };
  });
}

async function buildHealthPayload() {
  const status = await store.getStatus();
  return {
    status: "ok",
    service: "copaw-qmd-bridge",
    uptime: Math.floor((Date.now() - startedAt) / 1000),
    dbPath,
    totalDocuments: status.totalDocuments,
    needsEmbedding: status.needsEmbedding,
    hasVectorIndex: status.hasVectorIndex,
    collections: status.collections,
  };
}

const server = createServer(async (req, res) => {
  try {
    const pathname = req.url || "/";
    if (pathname === "/health" && req.method === "GET") {
      writeJson(res, 200, await buildHealthPayload());
      return;
    }
    if (pathname === "/status" && req.method === "GET") {
      writeJson(res, 200, await store.getStatus());
      return;
    }
    if (pathname === "/prewarm" && req.method === "POST") {
      const raw = await collectBody(req);
      const params = raw ? JSON.parse(raw) : {};
      const collections = normalizedCollections(params?.collections);
      const warmupQuery = String(params?.query || "memory").trim() || "memory";
      await runStructuredQuery({
        searches: [
          { type: "lex", query: warmupQuery },
          { type: "vec", query: warmupQuery },
        ],
        collections,
        limit: 1,
        minScore: 0,
        skipRerank: params?.skipRerank !== false,
      });
      writeJson(res, 200, { ok: true });
      return;
    }
    if ((pathname === "/query" || pathname === "/search") && req.method === "POST") {
      const raw = await collectBody(req);
      const params = raw ? JSON.parse(raw) : {};
      const results = await runStructuredQuery(params);
      writeJson(res, 200, { results });
      return;
    }
    writeJson(res, 404, { error: "Not Found" });
  } catch (error) {
    writeJson(res, 500, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

async function shutdown() {
  server.close();
  await store.close();
}

process.on("SIGTERM", async () => {
  await shutdown();
  process.exit(0);
});
process.on("SIGINT", async () => {
  await shutdown();
  process.exit(0);
});

server.listen(port, host, () => {
  process.stdout.write(`copaw-qmd-bridge listening on http://${host}:${port}\n`);
});
