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
      return "Common";
    case "uncommon":
      return "Uncommon";
    case "rare":
      return "Rare";
    case "epic":
      return "Epic";
    case "signature":
      return "Signature";
    default:
      return "Growing";
  }
}

export function resolveBuddyEvolutionView(input: {
  evolutionStage?: string | null;
  rarity?: string | null;
}) {
  const stage = (input.evolutionStage || "seed").trim() as BuddyEvolutionStage;
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
