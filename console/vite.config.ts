import fs from "node:fs/promises";
import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const DEFAULT_OLD_ASSET_RETENTION_MINUTES = 24 * 60;

function normalizeModuleId(id: string): string {
  return id.replace(/\\/g, "/");
}

function resolveNodeModulePackage(id: string): string | null {
  const normalized = normalizeModuleId(id);
  const marker = "/node_modules/";
  const markerIndex = normalized.lastIndexOf(marker);
  if (markerIndex < 0) {
    return null;
  }
  const remainder = normalized.slice(markerIndex + marker.length);
  if (!remainder) {
    return null;
  }
  const segments = remainder.split("/");
  if (segments[0]?.startsWith("@") && segments.length >= 2) {
    return `${segments[0]}/${segments[1]}`;
  }
  return segments[0] || null;
}

function resolveManualChunk(id: string): string | undefined {
  const normalized = normalizeModuleId(id);
  if (!normalized.includes("/node_modules/")) {
    return undefined;
  }

  const pkg = resolveNodeModulePackage(normalized);
  if (!pkg) {
    return undefined;
  }

  if (
    pkg === "react" ||
    pkg === "react-dom" ||
    pkg === "scheduler"
  ) {
    return "vendor-react-core";
  }

  if (
    pkg === "react-router" ||
    pkg === "react-router-dom" ||
    pkg === "@remix-run/router"
  ) {
    return "vendor-react-router";
  }

  if (
    pkg === "@agentscope-ai/icons" ||
    pkg === "@agentscope-ai/icons-override-antd" ||
    pkg === "@agentscope-ai/icons-svg-override-antd"
  ) {
    return "vendor-agentscope-icons";
  }

  if (
    pkg === "react-markdown" ||
    pkg === "remark-gfm" ||
    pkg.startsWith("micromark") ||
    pkg.startsWith("mdast-util-") ||
    pkg.startsWith("hast-util-") ||
    pkg.startsWith("unist-") ||
    pkg === "decode-named-character-reference" ||
    pkg === "html-url-attributes" ||
    pkg === "property-information" ||
    pkg === "space-separated-tokens" ||
    pkg === "comma-separated-tokens" ||
    pkg === "unified" ||
    pkg === "vfile" ||
    pkg === "vfile-message"
  ) {
    return "vendor-markdown";
  }

  if (pkg === "lucide-react") {
    return "vendor-lucide";
  }

  if (
    pkg === "@babel/runtime" ||
    pkg.startsWith("@babel/") ||
    pkg === "regenerator-runtime"
  ) {
    return "vendor-babel-runtime";
  }

  if (
    pkg === "ahooks" ||
    pkg === "copy-to-clipboard" ||
    pkg === "dayjs" ||
    pkg === "lodash" ||
    pkg === "uuid"
  ) {
    return "vendor-runtime-utils";
  }

  if (
    pkg === "dompurify" ||
    pkg === "marked-footnote" ||
    pkg === "react-error-boundary" ||
    pkg === "use-stick-to-bottom"
  ) {
    return "vendor-chat-utils";
  }

  if (
    pkg === "immer" ||
    pkg === "use-context-selector" ||
    pkg === "xstate" ||
    pkg === "zustand"
  ) {
    return "vendor-react-state";
  }

  if (pkg === "mermaid") {
    return "vendor-mermaid";
  }

  return undefined;
}

function extractIndexAssetRefs(html: string): Set<string> {
  const refs = new Set<string>();
  const pattern = /\/assets\/([^"'?#\s)]+)/g;
  let match: RegExpExecArray | null = pattern.exec(html);
  while (match) {
    if (match[1]) {
      refs.add(match[1]);
    }
    match = pattern.exec(html);
  }
  return refs;
}

function isHashedBuildAsset(filename: string): boolean {
  return /-[A-Za-z0-9_-]{6,}\./.test(filename);
}

function preserveRecentHashedAssetsPlugin(
  rootDir: string,
  retentionMinutes: number,
): Plugin {
  return {
    name: "copaw-preserve-recent-hashed-assets",
    apply: "build",
    async closeBundle() {
      const distDir = path.resolve(rootDir, "dist");
      const assetsDir = path.join(distDir, "assets");
      const retentionMs = Math.max(1, retentionMinutes) * 60 * 1000;
      const cutoff = Date.now() - retentionMs;

      let currentIndexHtml = "";
      try {
        currentIndexHtml = await fs.readFile(
          path.join(distDir, "index.html"),
          "utf8",
        );
      } catch {
        return;
      }

      const activeAssetRefs = extractIndexAssetRefs(currentIndexHtml);

      let assetEntries: Array<{ isFile: () => boolean; name: string }> = [];
      try {
        assetEntries = await fs.readdir(assetsDir, {
          withFileTypes: true,
          encoding: "utf8",
        });
      } catch {
        return;
      }

      const removable = assetEntries.filter(
        (entry) =>
          entry.isFile() &&
          isHashedBuildAsset(entry.name) &&
          !activeAssetRefs.has(entry.name),
      );

      let removedCount = 0;
      for (const entry of removable) {
        const fullPath = path.join(assetsDir, entry.name);
        try {
          const stat = await fs.stat(fullPath);
          if (stat.mtimeMs >= cutoff) {
            continue;
          }
          await fs.rm(fullPath, { force: true });
          removedCount += 1;
        } catch {
          // Ignore races with concurrent reads or external cleanup.
        }
      }

      if (removedCount > 0) {
        console.info(
          `[vite] removed ${removedCount} expired asset file(s); retention window ${retentionMinutes} minute(s).`,
        );
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Empty = same-origin; frontend and backend served together, no hardcoded host.
  const apiBaseUrl = env.BASE_URL ?? "";
  const assetRetentionMinutes = Number.parseInt(
    env.CONSOLE_OLD_ASSET_RETENTION_MINUTES ||
      String(DEFAULT_OLD_ASSET_RETENTION_MINUTES),
    10,
  );

  return {
    define: {
      BASE_URL: JSON.stringify(apiBaseUrl),
      MOBILE: false,
    },
    plugins: [
      react(),
      preserveRecentHashedAssetsPlugin(
        __dirname,
        Number.isFinite(assetRetentionMinutes) &&
          assetRetentionMinutes > 0
          ? assetRetentionMinutes
          : DEFAULT_OLD_ASSET_RETENTION_MINUTES,
      ),
    ],
    css: {
      modules: {
        localsConvention: "camelCase",
        generateScopedName: "[name]__[local]__[hash:base64:5]",
      },
      preprocessorOptions: {
        less: {
          javascriptEnabled: true,
        },
      },
    },
    resolve: {
      alias: [
        {
          find: /^@agentscope-ai\/design$/,
          replacement: path.resolve(__dirname, "./src/ui/index.tsx"),
        },
        {
          find: /^@ant-design\/x-markdown$/,
          replacement: path.resolve(__dirname, "./src/ui/markdown.tsx"),
        },
        {
          find: /^@ant-design\/x$/,
          replacement: path.resolve(__dirname, "./src/ui/antx.tsx"),
        },
        {
          find: /^@ant-design\/x-markdown\/plugins\/Latex$/,
          replacement: path.resolve(__dirname, "./src/ui/markdownLatexPlugin.ts"),
        },
        {
          find: /^@\//,
          replacement: `${path.resolve(__dirname, "./src")}/`,
        },
      ],
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
    },
    optimizeDeps: {
      include: ["diff"],
    },
    build: {
      // Keep prior hashed assets so already-open pages can still lazy-load them
      // during a rolling rebuild or service restart. Expired files are pruned
      // after a grace window by the build plugin above.
      emptyOutDir: false,
      modulePreload: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            return resolveManualChunk(id);
          },
        },
      },
    },
  };
});
