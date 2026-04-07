import { useEffect, useState } from "react";
import { Card, Col, Drawer, Progress, Row, Statistic, Tag, Typography } from "antd";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  BUDDY_ANIMATION_INTERVAL_MS,
  buildBuddyAvatarView,
  renderBuddyFace,
} from "./buddyAvatar";
import { resolveBuddyEvolutionView } from "./buddyEvolution";
import { resolveBuddyDisplaySnapshot } from "./buddyPresentation";
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

  const snapshot = surface ? resolveBuddyDisplaySnapshot(surface) : null;
  const evolution = surface
    ? resolveBuddyEvolutionView({
        evolutionStage: surface.growth.evolution_stage,
        currentForm: surface.presentation.current_form,
        capabilityScore: surface.growth.capability_score,
        companionExperience: surface.growth.companion_experience,
        rarity: surface.presentation.rarity,
      })
    : null;
  const avatar = surface ? buildBuddyAvatarView(surface, { tick }) : null;

  return (
    <Drawer
      title={snapshot ? `${snapshot.buddyName} 的伙伴面板` : "伙伴面板"}
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      {!surface || !avatar || !snapshot ? null : (
        <Row gutter={[12, 12]}>
          <Col span={24}>
            <Card size="small" title="身份">
              <div className={styles.buddyPanelAvatar}>
                <div
                  className={styles.buddyPanelAvatarSprite}
                  data-stage={evolution?.stage ?? snapshot.stage}
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
                当前阶段：{snapshot.stageLabel}
                {" / "}
                {evolution?.rarityLabel ?? surface.presentation.rarity}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前心情：{snapshot.moodLabel}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前陪伴状态：{snapshot.presenceLabel}
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
                鼓励风格：{snapshot.encouragementStyleLabel}
              </Paragraph>
              {snapshot.companionStrategySummary ? (
                <Paragraph style={{ marginBottom: 0 }}>
                  <Text strong>陪伴策略：</Text>
                  {snapshot.companionStrategySummary}
                </Paragraph>
              ) : null}
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="成长">
              <Row gutter={12}>
                <Col span={12}>
                  <Statistic title="等级" value={surface.growth.growth_level} />
                </Col>
                <Col span={12}>
                  <Statistic title="能力分" value={surface.growth.capability_score ?? 0} />
                </Col>
              </Row>
              <Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
                当前领域：{surface.growth.domain_label || "未确认"}
              </Paragraph>
              <Progress percent={surface.growth.progress_to_next_stage} style={{ marginTop: 12 }} />
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="领域能力">
              <Row gutter={12}>
                <Col span={12}>
                  <Statistic title="策略分" value={surface.growth.strategy_score ?? 0} />
                </Col>
                <Col span={12}>
                  <Statistic title="执行分" value={surface.growth.execution_score ?? 0} />
                </Col>
              </Row>
              <Row gutter={12} style={{ marginTop: 12 }}>
                <Col span={12}>
                  <Statistic title="证据分" value={surface.growth.evidence_score ?? 0} />
                </Col>
                <Col span={12}>
                  <Statistic title="稳定度" value={surface.growth.stability_score ?? 0} />
                </Col>
              </Row>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="当前关系上下文">
              <Paragraph>
                <Text strong>最终目标：</Text>
                {snapshot.finalGoalSummary}
              </Paragraph>
              <Paragraph>
                <Text strong>当前任务：</Text>
                {snapshot.currentTaskSummary}
              </Paragraph>
              <Paragraph>
                <Text strong>为什么现在做：</Text>
                {snapshot.whyNowSummary}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>唯一下一步：</Text>
                {snapshot.singleNextActionSummary}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Tag color={evolution?.accentTone ?? "default"}>{`物种 ${avatar.speciesLabel}`}</Tag>
            <Tag>{`帽子 ${avatar.hatLabel}`}</Tag>
            <Tag>{`陪伴状态 ${snapshot.presenceLabel}`}</Tag>
            <Tag color={evolution?.accentTone ?? "purple"}>
              {`领域 ${surface.growth.domain_label || "未确认"}`}
            </Tag>
            <Tag color="green">{`能力分 ${surface.growth.capability_score ?? 0}`}</Tag>
            
          </Col>
        </Row>
      )}
    </Drawer>
  );
}
