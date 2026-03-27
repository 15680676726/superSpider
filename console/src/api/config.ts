declare const BASE_URL: string;

declare global {
  interface Window {
    __COPAW_RUNTIME__?: {
      apiBaseUrl?: string;
      apiToken?: string;
      token?: string;
    };
  }
}

const TOKEN_STORAGE_KEYS = [
  "copaw.apiToken",
  "copaw_api_token",
  "copaw-token",
] as const;

function canUseDom(): boolean {
  return typeof window !== "undefined" && typeof document !== "undefined";
}

function normalizeApiPath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

function readMetaContent(name: string): string {
  if (!canUseDom()) {
    return "";
  }
  const content = document
    .querySelector(`meta[name="${name}"]`)
    ?.getAttribute("content");
  return content?.trim() || "";
}

function readStorage(storage: Storage | undefined, key: string): string {
  if (!storage) {
    return "";
  }
  try {
    return storage.getItem(key)?.trim() || "";
  } catch {
    return "";
  }
}

function getStorage(kind: "localStorage" | "sessionStorage"): Storage | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  try {
    return window[kind];
  } catch {
    return undefined;
  }
}

function readCookie(name: string): string {
  if (!canUseDom()) {
    return "";
  }
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${escapedName}=([^;]*)`),
  );
  if (!match?.[1]) {
    return "";
  }
  try {
    return decodeURIComponent(match[1]).trim();
  } catch {
    return match[1].trim();
  }
}

function getRuntimeConfig():
  | {
      apiBaseUrl?: string;
      apiToken?: string;
      token?: string;
    }
  | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.__COPAW_RUNTIME__ || null;
}

function firstNonEmpty(...values: Array<string | null | undefined>): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

/**
 * Get the full API URL with /api prefix.
 */
export function getApiUrl(path: string): string {
  const runtimeBaseUrl = getRuntimeConfig()?.apiBaseUrl;
  const base = firstNonEmpty(runtimeBaseUrl, BASE_URL).replace(/\/+$/, "");
  return `${base}/api${normalizeApiPath(path)}`;
}

/**
 * Get the API token from runtime state only.
 *
 * Supported sources, in order:
 * 1. window.__COPAW_RUNTIME__.apiToken / token
 * 2. <meta name="copaw-api-token" content="...">
 * 3. localStorage / sessionStorage under copaw-specific keys
 * 4. cookie: copaw_api_token
 */
export function getApiToken(): string {
  const runtimeConfig = getRuntimeConfig();
  const storageCandidates = canUseDom()
    ? TOKEN_STORAGE_KEYS.flatMap((key) => [
        readStorage(getStorage("localStorage"), key),
        readStorage(getStorage("sessionStorage"), key),
      ])
    : [];

  return firstNonEmpty(
    runtimeConfig?.apiToken,
    runtimeConfig?.token,
    readMetaContent("copaw-api-token"),
    ...storageCandidates,
    readCookie("copaw_api_token"),
  );
}
