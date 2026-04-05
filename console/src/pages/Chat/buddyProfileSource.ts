import { resolveCanonicalBuddyProfileId } from "../../runtime/buddyProfileBinding";

export function resolveRequestedBuddyProfileId(value: unknown): string | null {
  return resolveCanonicalBuddyProfileId(value);
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
