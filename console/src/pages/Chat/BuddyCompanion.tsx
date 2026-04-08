import { useEffect, useState } from "react";
import { Tag, Typography } from "antd";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import { BUDDY_ANIMATION_INTERVAL_MS, buildBuddyAvatarView } from "./buddyAvatar";
import { resolveBuddyEvolutionView } from "./buddyEvolution";
import { buildBuddyStatusLine, resolveBuddyDisplaySnapshot } from "./buddyPresentation";
import styles from "./index.module.less";

const { Text } = Typography;

export function BuddyCompanion({
  surface,
  onOpen,
}: {
  surface: BuddySurfaceResponse;
  onOpen: () => void;
}) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTick((current) => current + 1);
    }, BUDDY_ANIMATION_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  const snapshot = resolveBuddyDisplaySnapshot(surface);
  const evolution = resolveBuddyEvolutionView({
    evolutionStage: surface.growth.evolution_stage,
    currentForm: surface.presentation.current_form,
    capabilityPoints: surface.growth.capability_points,
    capabilityScore: surface.growth.capability_score,
    companionExperience: surface.growth.companion_experience,
    rarity: surface.presentation.rarity,
  });
  const avatar = buildBuddyAvatarView(surface, { tick });

  return (
    <button
      type="button"
      className={styles.buddyCompanion}
      onClick={onOpen}
      data-testid="buddy-companion-trigger"
      aria-label={`打开 ${snapshot.buddyName} 的伙伴面板`}
    >
      <div
        className={styles.buddySprite}
        data-testid="buddy-companion-sprite"
        data-stage={evolution.stage}
        data-presence={surface.presentation.presence_state}
        data-frame={avatar.frameIndex}
      >
        <div className={styles.buddySpriteAscii} aria-hidden="true">
          {avatar.lines.map((line, index) => (
            <span key={`${avatar.species}-${index}`}>{line}</span>
          ))}
        </div>
      </div>
      <div className={styles.buddyCompanionMeta}>
        <Text strong className={styles.buddyCompanionName}>
          {snapshot.buddyName}
        </Text>
        <Text className={styles.buddyCompanionStatus}>{buildBuddyStatusLine(surface)}</Text>
        <div style={{ display: "grid", gap: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <strong>最终目标</strong>
            {" · "}
            {snapshot.finalGoalSummary}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <strong>当前任务</strong>
            {" · "}
            {snapshot.currentTaskSummary}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <strong>下一步</strong>
            {" · "}
            {snapshot.singleNextActionSummary}
          </Text>
        </div>
        <div className={styles.buddyCompanionTags}>
          <Tag color={evolution.accentTone} data-testid="buddy-companion-species">
            {avatar.speciesLabel}
          </Tag>
          <Tag color={evolution.accentTone}>{snapshot.stageLabel}</Tag>
          <Tag color="gold" data-testid="buddy-companion-rarity">
            {avatar.rarityStars}
          </Tag>
          <Tag color="geekblue">{`积分 ${snapshot.capabilityPoints}`}</Tag>
          <Tag color="blue">{`亲密度 ${surface.growth.intimacy}`}</Tag>
        </div>
      </div>
      <span className={styles.buddyCompanionAction}>查看详情</span>
    </button>
  );
}
