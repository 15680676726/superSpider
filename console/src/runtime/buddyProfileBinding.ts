export function normalizeBuddyProfileId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

export function resolveCanonicalBuddyProfileId(...values: unknown[]): string | null {
  for (const value of values) {
    const normalized = normalizeBuddyProfileId(value);
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

export function readBuddyProfileId(): string | null {
  return null;
}

export function writeBuddyProfileId(_profileId: string | null | undefined): void {}

export function resetBuddyProfileBindingForTests(): void {}
