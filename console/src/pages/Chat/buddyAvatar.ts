import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  BUDDY_BODY_FRAMES,
  BUDDY_HAT_LINES,
  BUDDY_PRESENCE_AURAS,
  BUDDY_STAGE_AURAS,
} from "./buddySpriteAssets";

export const BUDDY_SPECIES = [
  "duck",
  "goose",
  "blob",
  "cat",
  "dragon",
  "octopus",
  "owl",
  "penguin",
  "turtle",
  "snail",
  "ghost",
  "axolotl",
  "capybara",
  "cactus",
  "robot",
  "rabbit",
  "mushroom",
  "chonk",
] as const;

export const BUDDY_HATS = [
  "none",
  "crown",
  "tophat",
  "propeller",
  "halo",
  "wizard",
  "beanie",
  "tinyduck",
] as const;

export const BUDDY_EYES = ["o", "^", "*", "@", "-", "u"] as const;

type BuddySpecies = (typeof BUDDY_SPECIES)[number];
type BuddyHat = (typeof BUDDY_HATS)[number];
type BuddyEye = (typeof BUDDY_EYES)[number];

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
  switch (species) {
    case "duck":
      return "小鸭";
    case "goose":
      return "白鹅";
    case "blob":
      return "团子";
    case "cat":
      return "小猫";
    case "dragon":
      return "幼龙";
    case "octopus":
      return "章章";
    case "owl":
      return "猫头鹰";
    case "penguin":
      return "企鹅";
    case "turtle":
      return "小龟";
    case "snail":
      return "蜗牛";
    case "ghost":
      return "小幽灵";
    case "axolotl":
      return "六角";
    case "capybara":
      return "水豚";
    case "cactus":
      return "仙人掌";
    case "robot":
      return "机器人";
    case "rabbit":
      return "小兔";
    case "mushroom":
      return "蘑菇";
    case "chonk":
      return "团宠";
    default:
      return species;
  }
}

function hatLabel(hat: BuddyHat): string {
  switch (hat) {
    case "none":
      return "无帽";
    case "crown":
      return "王冠";
    case "tophat":
      return "礼帽";
    case "propeller":
      return "螺旋帽";
    case "halo":
      return "光环";
    case "wizard":
      return "巫师帽";
    case "beanie":
      return "毛线帽";
    case "tinyduck":
      return "小鸭帽";
    default:
      return hat;
  }
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
