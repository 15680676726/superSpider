import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import { BUDDY_BODY_FRAMES } from "../../assets/buddy/base/bodyFrames";
import { BUDDY_PRESENCE_AURAS, BUDDY_STAGE_AURAS } from "../../assets/buddy/effects/auras";
import {
  BUDDY_EYES,
  BUDDY_HATS,
  BUDDY_HAT_LABELS,
  BUDDY_SPECIES,
  BUDDY_SPECIES_LABELS,
} from "../../assets/buddy/forms/catalog";
import { BUDDY_HAT_LINES } from "../../assets/buddy/parts/hats";

type BuddySpecies = (typeof BUDDY_SPECIES)[number];
type BuddyHat = (typeof BUDDY_HATS)[number];
type BuddyEye = (typeof BUDDY_EYES)[number];

export { BUDDY_SPECIES, BUDDY_HATS, BUDDY_EYES };

export const BUDDY_ANIMATION_INTERVAL_MS = 640;

const IDLE_SEQUENCE = [0, 0, 0, 1, 0, -1, 0, 0, 2, 0, -1, 0] as const;

export interface BuddyAvatarBones {
  species: BuddySpecies;
  hat: BuddyHat;
  eye: BuddyEye;
  shiny: boolean;
}

export interface BuddyAvatarView extends BuddyAvatarBones {
  lines: string[];
  speciesLabel: string;
  hatLabel: string;
  rarityStars: string;
  presenceState: string;
  frameIndex: number;
}

function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function pick<T>(values: readonly T[], hash: number): T {
  return values[Math.abs(hash) % values.length] as T;
}

function overlayLine(base: string, overlay: string): string {
  const length = Math.max(base.length, overlay.length);
  return Array.from({ length }, (_, index) => {
    const overlayChar = overlay[index] ?? " ";
    if (overlayChar !== " ") return overlayChar;
    return base[index] ?? " ";
  }).join("");
}

function normalizePresenceState(presence?: string | null): keyof typeof BUDDY_PRESENCE_AURAS {
  const value = (presence || "").trim();
  if (value === "available") return "available";
  if (value === "attentive") return "attentive";
  if (value === "focused") return "focused";
  if (value === "supporting") return "supporting";
  if (value === "celebrating") return "celebrating";
  if (value === "pulling-back") return "pulling-back";
  if (value === "resting") return "resting";
  return "idle";
}

function normalizeEvolutionStage(stage?: string | null): keyof typeof BUDDY_STAGE_AURAS {
  const value = (stage || "").trim();
  if (value === "bonded") return "bonded";
  if (value === "capable") return "capable";
  if (value === "seasoned") return "seasoned";
  if (value === "signature") return "signature";
  return "seed";
}

function moodEye(eye: BuddyEye, mood?: string | null, presence?: string | null): BuddyEye {
  const normalizedPresence = normalizePresenceState(presence);
  if (normalizedPresence === "resting") return "-";
  switch ((mood || "").trim()) {
    case "playful":
      return "^";
    case "proud":
      return "*";
    case "determined":
      return "@";
    case "warm":
      return "u";
    default:
      return eye;
  }
}

function speciesLabel(species: BuddySpecies): string {
  return BUDDY_SPECIES_LABELS[species] ?? species;
}

function hatLabel(hat: BuddyHat): string {
  return BUDDY_HAT_LABELS[hat] ?? hat;
}

function resolvePresenceStep(presenceState?: string | null, tick = 0): number {
  const safeTick = Math.max(0, tick);
  switch (normalizePresenceState(presenceState)) {
    case "celebrating":
      return safeTick;
    case "supporting":
      return [0, 1, 0, 2][safeTick % 4] ?? 0;
    case "pulling-back":
      return [1, 0, 2, 0][safeTick % 4] ?? 0;
    case "focused":
      return IDLE_SEQUENCE[(safeTick + 2) % IDLE_SEQUENCE.length] ?? 0;
    case "resting":
      return safeTick % 5 === 0 ? -1 : 0;
    case "attentive":
    case "available":
    case "idle":
    default:
      return IDLE_SEQUENCE[safeTick % IDLE_SEQUENCE.length] ?? 0;
  }
}

function resolveAuraLine(
  evolutionStage?: string | null,
  presenceState?: string | null,
  shiny?: boolean,
): string {
  const stageAura = BUDDY_STAGE_AURAS[normalizeEvolutionStage(evolutionStage)];
  const presenceAura = BUDDY_PRESENCE_AURAS[normalizePresenceState(presenceState)];
  let aura = overlayLine(stageAura, presenceAura);
  if (shiny) {
    aura = overlayLine(aura, "*          *");
  }
  return aura;
}

export function presentBuddyRarityStars(rarity?: string | null): string {
  switch ((rarity || "").trim()) {
    case "signature":
      return "★★★★★";
    case "epic":
      return "★★★★";
    case "rare":
      return "★★★";
    case "uncommon":
      return "★★";
    case "common":
    default:
      return "★";
  }
}

export function resolveBuddyAvatarBones(
  surface: Partial<Pick<BuddySurfaceResponse, "profile" | "presentation">>,
): BuddyAvatarBones {
  const profileId =
    surface.profile?.profile_id ||
    surface.presentation?.profile_id ||
    surface.presentation?.buddy_name ||
    "buddy";
  const seed = hashString(
    [
      profileId,
      surface.presentation?.buddy_name || "buddy",
      surface.presentation?.profile_id || profileId,
    ].join(":"),
  );
  return {
    species: pick(BUDDY_SPECIES, seed),
    eye: pick(BUDDY_EYES, seed >>> 3),
    hat: pick(BUDDY_HATS, seed >>> 7),
    shiny: ((seed >>> 11) & 0b1111) === 0,
  };
}

export function spriteFrameCount(species: BuddySpecies): number {
  return BUDDY_BODY_FRAMES[species].length;
}

export function renderBuddyFace(
  avatar: Pick<BuddyAvatarBones, "species" | "eye"> & {
    moodState?: string | null;
    presenceState?: string | null;
  },
): string {
  const eye = moodEye(avatar.eye, avatar.moodState, avatar.presenceState);
  return `${speciesLabel(avatar.species)} ${eye}${eye}`;
}

export function renderBuddyAvatarLines(
  avatar: Pick<BuddyAvatarView, "species" | "hat" | "eye"> & {
    evolutionStage?: string | null;
    presenceState?: string | null;
    moodState?: string | null;
    frameIndex?: number;
    shiny?: boolean;
  },
): string[] {
  const frames = BUDDY_BODY_FRAMES[avatar.species];
  const blink = (avatar.frameIndex ?? 0) < 0;
  const normalizedFrame = blink ? 0 : (avatar.frameIndex ?? 0) % frames.length;
  const eye = blink ? "-" : moodEye(avatar.eye, avatar.moodState, avatar.presenceState);
  const frame = frames[normalizedFrame]!.map((line) => line.split("{E}").join(eye));
  const lines = [...frame];

  const topLine = overlayLine(
    resolveAuraLine(avatar.evolutionStage, avatar.presenceState, avatar.shiny),
    BUDDY_HAT_LINES[avatar.hat],
  );
  if (topLine.trim()) {
    lines[0] = topLine;
  } else if (!lines[0]?.trim()) {
    lines.shift();
  }

  if (normalizePresenceState(avatar.presenceState) === "celebrating") {
    lines[lines.length - 1] = overlayLine(lines[lines.length - 1] ?? "", "  +  ++  + ");
  } else if (normalizePresenceState(avatar.presenceState) === "supporting") {
    lines[lines.length - 1] = overlayLine(lines[lines.length - 1] ?? "", "  ~  ~~  ~ ");
  } else if (normalizePresenceState(avatar.presenceState) === "pulling-back") {
    lines[lines.length - 1] = overlayLine(lines[lines.length - 1] ?? "", "  !  !!  ! ");
  }

  return lines;
}

export function buildBuddyAvatarView(
  surface: Partial<Pick<BuddySurfaceResponse, "profile" | "presentation" | "growth">>,
  options?: { tick?: number },
): BuddyAvatarView {
  const bones = resolveBuddyAvatarBones(surface);
  const frames = BUDDY_BODY_FRAMES[bones.species];
  const frameStep = resolvePresenceStep(surface.presentation?.presence_state, options?.tick ?? 0);
  const stageOffset =
    normalizeEvolutionStage(surface.growth?.evolution_stage) === "signature"
      ? 2
      : normalizeEvolutionStage(surface.growth?.evolution_stage) === "seasoned"
        ? 1
        : 0;
  const frameIndex = frameStep < 0 ? -1 : (stageOffset + frameStep) % frames.length;

  const displayEye = moodEye(
    bones.eye,
    surface.presentation?.mood_state,
    surface.presentation?.presence_state,
  );

  return {
    ...bones,
    eye: displayEye,
    lines: renderBuddyAvatarLines({
      ...bones,
      eye: displayEye,
      frameIndex,
      evolutionStage: surface.growth?.evolution_stage,
      presenceState: surface.presentation?.presence_state,
      moodState: surface.presentation?.mood_state,
    }),
    speciesLabel: speciesLabel(bones.species),
    hatLabel: hatLabel(bones.hat),
    rarityStars: presentBuddyRarityStars(surface.presentation?.rarity),
    presenceState: surface.presentation?.presence_state || "idle",
    frameIndex,
  };
}
