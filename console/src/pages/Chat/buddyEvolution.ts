export type BuddyEvolutionStage =
  | "seed"
  | "bonded"
  | "capable"
  | "seasoned"
  | "signature";

type BuddyEvolutionInput = {
  companionExperience?: number | null;
};

const EVOLUTION_THRESHOLDS: Array<{
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
  const experience = Math.max(0, input.companionExperience ?? 0);
  return (
    EVOLUTION_THRESHOLDS.find((item) => experience >= item.minimumExperience)?.stage ??
    "seed"
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
  companionExperience?: number | null;
}) {
  const stage =
    normalizeKnownStage(input.evolutionStage) ||
    normalizeKnownStage(input.currentForm) ||
    resolveBuddyEvolutionStage({
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
