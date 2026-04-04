import { Tag, Typography } from "antd";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import { resolveBuddyEvolutionView } from "./buddyEvolution";
import { buildBuddyStatusLine, presentBuddyStageLabel } from "./buddyPresentation";
import styles from "./index.module.less";

const { Text } = Typography;

export function BuddyCompanion({
  surface,
  onOpen,
}: {
  surface: BuddySurfaceResponse;
  onOpen: () => void;
}) {
  const evolution = resolveBuddyEvolutionView({
    evolutionStage: surface.growth.evolution_stage,
    rarity: surface.presentation.rarity,
  });
  return (
    <button
      type="button"
      className={styles.buddyCompanion}
      onClick={onOpen}
      data-testid="buddy-companion-trigger"
      aria-label={`Open ${surface.presentation.buddy_name} companion panel`}
    >
      <div className={styles.buddySprite} data-stage={surface.growth.evolution_stage}>
        <div className={styles.buddySpriteFace}>
          <span />
          <span />
        </div>
      </div>
      <div className={styles.buddyCompanionMeta}>
        <Text strong className={styles.buddyCompanionName}>
          {surface.presentation.buddy_name}
        </Text>
        <Text className={styles.buddyCompanionStatus}>{buildBuddyStatusLine(surface)}</Text>
        <div className={styles.buddyCompanionTags}>
          <Tag color={evolution.accentTone}>
            {presentBuddyStageLabel(evolution.stage)}
          </Tag>
          <Tag color="blue">亲密度 {surface.growth.intimacy}</Tag>
        </div>
      </div>
      <span className={styles.buddyCompanionAction}>查看属性</span>
    </button>
  );
}
