import {
  inferWritebackTargetsFromFocus,
  normalizeWritebackTargetsFromThreadMeta,
  presentSessionKindLabel,
} from "./chatRuntimePresentation";

function readMetaString(
  threadMeta: Record<string, unknown>,
  key: string,
): string {
  const value = threadMeta[key];
  return typeof value === "string" ? value.trim() : "";
}

export function resolveThreadRuntimePresentation({
  currentGoal,
  sessionKind,
  threadMeta,
}: {
  currentGoal: string | null;
  sessionKind: string;
  threadMeta: Record<string, unknown>;
}): {
  focusLabel: string | null;
  focusHint: string | null;
  threadKindLabel: string | null;
  threadKindHint: string | null;
  writebackLabel: string | null;
  writebackHint: string | null;
} {
  const focusKind = readMetaString(threadMeta, "current_focus_kind");
  const focusId = readMetaString(threadMeta, "current_focus_id");
  const focusLabel = currentGoal?.trim() ? `Focus: ${currentGoal.trim()}` : null;
  const focusHintParts = [
    focusKind ? `kind=${focusKind}` : "",
    focusId ? `id=${focusId}` : "",
  ].filter(Boolean);
  const focusHint = focusHintParts.length > 0 ? focusHintParts.join(" | ") : null;

  const normalizedSessionKind = sessionKind.trim();
  const threadKindLabel = normalizedSessionKind
    ? `Thread: ${presentSessionKindLabel(normalizedSessionKind)}`
    : null;
  const threadBindingKind = readMetaString(threadMeta, "thread_binding_kind");
  const ownerScope = readMetaString(threadMeta, "owner_scope");
  const threadKindHintParts = [
    normalizedSessionKind ? `session_kind=${normalizedSessionKind}` : "",
    threadBindingKind ? `thread_binding_kind=${threadBindingKind}` : "",
    ownerScope ? `owner_scope=${ownerScope}` : "",
  ].filter(Boolean);
  const threadKindHint =
    threadKindHintParts.length > 0 ? threadKindHintParts.join(" | ") : null;

  const metaWritebackTargets = normalizeWritebackTargetsFromThreadMeta(threadMeta);
  const inferredWritebackTargets =
    metaWritebackTargets.length > 0
      ? metaWritebackTargets
      : inferWritebackTargetsFromFocus({
          sessionKind: normalizedSessionKind,
          focusKind,
        });
  const writebackLabel =
    inferredWritebackTargets.length > 0
      ? `Writeback: ${inferredWritebackTargets.join("/")}`
      : null;
  const writebackRoleName = readMetaString(
    threadMeta,
    "chat_writeback_target_role_name",
  );
  const writebackMatchSignalsCount = Array.isArray(
    threadMeta.chat_writeback_target_match_signals,
  )
    ? threadMeta.chat_writeback_target_match_signals.length
    : 0;
  const writebackHintParts = [
    metaWritebackTargets.length > 0
      ? `targets=${metaWritebackTargets.join(",")}`
      : inferredWritebackTargets.length > 0
        ? `inferred=${inferredWritebackTargets.join(",")}`
        : "",
    writebackRoleName ? `role=${writebackRoleName}` : "",
    writebackMatchSignalsCount > 0
      ? `match_signals=${writebackMatchSignalsCount}`
      : "",
  ].filter(Boolean);
  const writebackHint =
    writebackHintParts.length > 0 ? writebackHintParts.join(" | ") : null;

  return {
    focusLabel,
    focusHint,
    threadKindLabel,
    threadKindHint,
    writebackLabel,
    writebackHint,
  };
}
