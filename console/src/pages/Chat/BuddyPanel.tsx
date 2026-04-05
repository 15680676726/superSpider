import { useEffect, useState } from "react";
import { Card, Col, Drawer, Progress, Row, Statistic, Tag, Typography } from "antd";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  BUDDY_ANIMATION_INTERVAL_MS,
  buildBuddyAvatarView,
  renderBuddyFace,
} from "./buddyAvatar";
import { resolveBuddyEvolutionView } from "./buddyEvolution";
import {
  presentBuddyMoodLabel,
  presentBuddyPresenceLabel,
  presentBuddyStageLabel,
} from "./buddyPresentation";
import styles from "./index.module.less";

const { Paragraph, Text } = Typography;

export function BuddyPanel({
  open,
  surface,
  onClose,
}: {
  open: boolean;
  surface: BuddySurfaceResponse | null;
  onClose: () => void;
}) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setInterval(() => {
      setTick((current) => current + 1);
    }, BUDDY_ANIMATION_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [open]);

  const evolution = surface
    ? resolveBuddyEvolutionView({
        evolutionStage: surface.growth.evolution_stage,
        rarity: surface.presentation.rarity,
      })
    : null;
  const avatar = surface ? buildBuddyAvatarView(surface, { tick }) : null;

  return (
    <Drawer
      title={surface ? `${surface.presentation.buddy_name} 的伙伴面板` : "伙伴面板"}
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      {!surface || !avatar ? null : (
        <Row gutter={[12, 12]}>
          <Col span={24}>
            <Card size="small" title="身份">
              <div className={styles.buddyPanelAvatar}>
                <div
                  className={styles.buddyPanelAvatarSprite}
                  data-stage={surface.growth.evolution_stage}
                  data-presence={surface.presentation.presence_state}
                  data-frame={avatar.frameIndex}
                >
                  <div className={styles.buddySpriteAscii} aria-hidden="true">
                    {avatar.lines.map((line, index) => (
                      <span key={`${avatar.species}-${index}`}>{line}</span>
                    ))}
                  </div>
                </div>
                <div className={styles.buddyPanelAvatarMeta}>
                  <Tag
                    color={evolution?.accentTone ?? "default"}
                    data-testid="buddy-panel-avatar-species"
                  >
                    {avatar.speciesLabel}
                  </Tag>
                  <Tag color="gold" data-testid="buddy-panel-avatar-rarity">
                    {avatar.rarityStars}
                  </Tag>
                  <Tag>{avatar.hatLabel}</Tag>
                  <Tag>{renderBuddyFace(avatar)}</Tag>
                  {avatar.shiny ? <Tag color="magenta">闪亮</Tag> : null}
                </div>
              </div>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>{surface.profile.display_name}</Text>
                {" 的伙伴显化"}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前形态：
                {presentBuddyStageLabel(evolution?.stage ?? surface.growth.evolution_stage)}
                {" / "}
                {evolution?.rarityLabel ?? surface.presentation.rarity}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前心情：{presentBuddyMoodLabel(surface.presentation.mood_state)}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前陪伴状态：{presentBuddyPresenceLabel(surface.presentation.presence_state)}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="关系">
              <Row gutter={12}>
                <Col span={12}>
                  <Statistic title="亲密度" value={surface.growth.intimacy} />
                </Col>
                <Col span={12}>
                  <Statistic title="契合度" value={surface.growth.affinity} />
                </Col>
              </Row>
              <Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
                鼓励风格：{surface.relationship?.encouragement_style || "老朋友"}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="成长">
              <Row gutter={12}>
                <Col span={12}>
                  <Statistic title="等级" value={surface.growth.growth_level} />
                </Col>
                <Col span={12}>
                  <Statistic title="陪伴经验" value={surface.growth.companion_experience} />
                </Col>
              </Row>
              <Progress percent={surface.growth.progress_to_next_stage} style={{ marginTop: 12 }} />
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="能力">
              <Row gutter={12}>
                <Col span={8}>
                  <Statistic title="知识值" value={surface.growth.knowledge_value} />
                </Col>
                <Col span={8}>
                  <Statistic title="技能值" value={surface.growth.skill_value} />
                </Col>
                <Col span={8}>
                  <Statistic title="沟通次数" value={surface.growth.communication_count} />
                </Col>
              </Row>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="当前关系上下文">
              <Paragraph>
                <Text strong>最终目标：</Text>
                {surface.presentation.current_goal_summary}
              </Paragraph>
              <Paragraph>
                <Text strong>当前任务：</Text>
                {surface.presentation.current_task_summary}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>为什么现在做：</Text>
                {surface.presentation.why_now_summary}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Tag color={evolution?.accentTone ?? "default"}>{`物种 ${avatar.speciesLabel}`}</Tag>
            <Tag>{`帽子 ${avatar.hatLabel}`}</Tag>
            <Tag>{`陪伴状态 ${presentBuddyPresenceLabel(surface.presentation.presence_state)}`}</Tag>
            <Tag color={evolution?.accentTone ?? "purple"}>
              {`陪跑完成 ${surface.growth.completed_support_runs}`}
            </Tag>
            <Tag color="green">{`愉快度 ${surface.growth.pleasant_interaction_score}`}</Tag>
          </Col>
        </Row>
      )}
    </Drawer>
  );
}
