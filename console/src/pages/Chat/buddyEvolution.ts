export type BuddyEvolutionStage =
  | "seed"
  | "bonded"
  | "capable"
  | "seasoned"
  | "signature";

type BuddyEvolutionInput = {
  capabilityScore?: number | null;
  companionExperience?: number | null;
};

const CAPABILITY_STAGE_BANDS: Array<{
  minimumScore: number;
  stage: BuddyEvolutionStage;
}> = [
  { minimumScore: 80, stage: "signature" },
  { minimumScore: 60, stage: "seasoned" },
  { minimumScore: 40, stage: "capable" },
  { minimumScore: 20, stage: "bonded" },
  { minimumScore: 0, stage: "seed" },
];

const EXPERIENCE_FALLBACK_THRESHOLDS: Array<{
  minimumExperience: number;
  stage: BuddyEvolutionStage;
}> = [
  { minimumExperience: 220, stage: "signature" },
  { minimumExperience: 140, stage: "seasoned" },
  { minimumExperience: 80, stage: "capable" },
  { minimumExperience: 40, stage: "bonded" },
  { minimumExperience: 0, stage: "seed" },
];

function normalizeKnownStage(raw?: string | null): BuddyEvolutionStage | null {
  switch ((raw || "").trim()) {
    case "seed":
    case "bonded":
    case "capable":
    case "seasoned":
    case "signature":
      return (raw || "").trim() as BuddyEvolutionStage;
    default:
      return null;
  }
}

export function resolveBuddyEvolutionStage(
  input: BuddyEvolutionInput,
): BuddyEvolutionStage {
  const capabilityScore = input.capabilityScore;
  if (typeof capabilityScore === "number" && Number.isFinite(capabilityScore)) {
    const normalizedScore = Math.max(0, Math.min(100, capabilityScore));
    return (
      CAPABILITY_STAGE_BANDS.find((item) => normalizedScore >= item.minimumScore)?.stage ??
      "seed"
    );
  }
  const experience = Math.max(0, input.companionExperience ?? 0);
  return (
    EXPERIENCE_FALLBACK_THRESHOLDS.find((item) => experience >= item.minimumExperience)
      ?.stage ?? "seed"
  );
}

export function presentBuddyRarityLabel(rarity?: string | null): string {
  switch ((rarity || "").trim()) {
    case "common":
      return "普通";
    case "uncommon":
      return "进阶";
    case "rare":
      return "稀有";
    case "epic":
      return "史诗";
    case "signature":
      return "招牌";
    default:
      return "成长中";
  }
}

export function resolveBuddyEvolutionView(input: {
  evolutionStage?: string | null;
  rarity?: string | null;
  currentForm?: string | null;
  capabilityScore?: number | null;
  companionExperience?: number | null;
}) {
  const stage =
    normalizeKnownStage(input.evolutionStage) ||
    normalizeKnownStage(input.currentForm) ||
    resolveBuddyEvolutionStage({
      capabilityScore: input.capabilityScore,
      companionExperience: input.companionExperience,
    });
  const accentTone =
    stage === "signature"
      ? "gold"
      : stage === "seasoned"
        ? "violet"
        : stage === "capable"
          ? "blue"
          : stage === "bonded"
            ? "green"
            : "default";
  return {
    stage,
    accentTone,
    rarityLabel: presentBuddyRarityLabel(input.rarity),
  };
}
