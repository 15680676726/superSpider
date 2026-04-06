import { resolveCanonicalBuddyProfileId } from "../../runtime/buddyProfileBinding";

export function resolveRequestedBuddyProfileId(value: unknown): string | null {
  return resolveCanonicalBuddyProfileId(value);
}

export function resolveThreadBuddyProfileId(
  threadMeta: Record<string, unknown> | null | undefined,
): string | null {
  return resolveCanonicalBuddyProfileId(
    threadMeta && typeof threadMeta.buddy_profile_id === "string"
      ? threadMeta.buddy_profile_id
      : null,
  );
}

export function resolveBuddySurfaceProfileRequest({
  threadMeta,
  requestedProfileId,
}: {
  threadMeta: Record<string, unknown> | null | undefined;
  requestedProfileId: unknown;
}): string | null {
  return resolveCanonicalBuddyProfileId(
    resolveThreadBuddyProfileId(threadMeta),
    requestedProfileId,
  );
}

export function mergeBuddyProfileIntoThreadMeta({
  threadMeta,
  requestedProfileId,
}: {
  threadMeta: Record<string, unknown>;
  requestedProfileId: string | null;
}): Record<string, unknown> {
  const canonicalThreadProfileId = resolveThreadBuddyProfileId(threadMeta);
  if (canonicalThreadProfileId || !requestedProfileId) {
    return threadMeta;
  }
  return {
    ...threadMeta,
    buddy_profile_id: requestedProfileId,
  };
}

export function resolveBuddyProfileIdFromBuddySurface({
  requestedProfileId,
  surfaceProfileId,
}: {
  requestedProfileId: unknown;
  surfaceProfileId: unknown;
}): string | null {
  return resolveCanonicalBuddyProfileId(surfaceProfileId, requestedProfileId);
}
