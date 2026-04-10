const STORAGE_KEY = "copaw.buddy_onboarding_draft";

export function loadBuddyOnboardingDraft(): unknown | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  return JSON.parse(raw) as unknown;
}

export function saveBuddyOnboardingDraft(value: unknown): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearBuddyOnboardingDraft(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
