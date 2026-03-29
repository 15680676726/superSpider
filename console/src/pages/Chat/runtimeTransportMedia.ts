import type { MediaSourceSpec } from "../../api/modules/media";

function normalizeRuntimeMediaSource(value: unknown): MediaSourceSpec | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Partial<MediaSourceSpec>;
  if (typeof candidate.source_kind !== "string" || !candidate.source_kind.trim()) {
    return null;
  }
  return { ...candidate, source_kind: candidate.source_kind } as MediaSourceSpec;
}

function runtimeMediaSourceKey(source: MediaSourceSpec): string {
  return (
    source.source_id ||
    source.artifact_id ||
    source.storage_uri ||
    source.url ||
    source.filename ||
    JSON.stringify(source)
  );
}

export function normalizeRuntimeMediaSources(items: unknown[]): MediaSourceSpec[] {
  const deduped: MediaSourceSpec[] = [];
  const seen = new Set<string>();
  items.forEach((item) => {
    const normalized = normalizeRuntimeMediaSource(item);
    if (!normalized) {
      return;
    }
    const key = runtimeMediaSourceKey(normalized);
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    deduped.push(normalized);
  });
  return deduped;
}
