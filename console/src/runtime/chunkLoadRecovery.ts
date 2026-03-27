const CHUNK_RELOAD_KEY = "copaw:chunk-load-reload-at";
const CHUNK_RELOAD_TTL_MS = 15_000;

function normalizeErrorMessage(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object") {
    const name =
      "name" in error && typeof error.name === "string" ? error.name : "";
    const message =
      "message" in error && typeof error.message === "string"
        ? error.message
        : "";
    return `${name} ${message}`.trim();
  }
  return "";
}

export function isChunkLoadError(error: unknown): boolean {
  const message = normalizeErrorMessage(error).toLowerCase();
  if (!message) {
    return false;
  }
  return (
    message.includes("failed to fetch dynamically imported module") ||
    message.includes("importing a module script failed") ||
    message.includes("loading chunk") ||
    message.includes("chunkloaderror") ||
    message.includes("failed to load module script")
  );
}

function readReloadAttemptAt(): number | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.sessionStorage.getItem(CHUNK_RELOAD_KEY);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function clearChunkReloadAttempt(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(CHUNK_RELOAD_KEY);
}

export function canAutoReloadAfterChunkError(): boolean {
  const attemptedAt = readReloadAttemptAt();
  if (attemptedAt === null) {
    return true;
  }
  return Date.now() - attemptedAt > CHUNK_RELOAD_TTL_MS;
}

export function reloadForChunkError(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  if (!canAutoReloadAfterChunkError()) {
    return false;
  }
  window.sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  window.location.reload();
  return true;
}
