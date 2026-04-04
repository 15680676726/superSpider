import { Card, Col, Drawer, Progress, Row, Statistic, Tag, Typography } from "antd";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import { resolveBuddyEvolutionView } from "./buddyEvolution";
import { presentBuddyMoodLabel, presentBuddyStageLabel } from "./buddyPresentation";

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
  const evolution = surface
    ? resolveBuddyEvolutionView({
        evolutionStage: surface.growth.evolution_stage,
        rarity: surface.presentation.rarity,
      })
    : null;
  return (
    <Drawer
      title={surface ? `${surface.presentation.buddy_name} 的伙伴面板` : "伙伴面板"}
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      {!surface ? null : (
        <Row gutter={[12, 12]}>
          <Col span={24}>
            <Card size="small" title="Identity">
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>{surface.profile.display_name}</Text> 的伙伴显化体
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前形态：{presentBuddyStageLabel(evolution?.stage ?? surface.growth.evolution_stage)} / {evolution?.rarityLabel ?? surface.presentation.rarity}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                当前情绪：{presentBuddyMoodLabel(surface.presentation.mood_state)}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="Relationship">
              <Row gutter={12}>
                <Col span={12}><Statistic title="亲密度" value={surface.growth.intimacy} /></Col>
                <Col span={12}><Statistic title="契合度" value={surface.growth.affinity} /></Col>
              </Row>
              <Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
                鼓励风格：{surface.relationship?.encouragement_style || "old-friend"}
              </Paragraph>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="Growth">
              <Row gutter={12}>
                <Col span={12}><Statistic title="成长等级" value={surface.growth.growth_level} /></Col>
                <Col span={12}><Statistic title="经验" value={surface.growth.companion_experience} /></Col>
              </Row>
              <Progress percent={surface.growth.progress_to_next_stage} style={{ marginTop: 12 }} />
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="Capability">
              <Row gutter={12}>
                <Col span={8}><Statistic title="知识值" value={surface.growth.knowledge_value} /></Col>
                <Col span={8}><Statistic title="技能值" value={surface.growth.skill_value} /></Col>
                <Col span={8}><Statistic title="沟通次数" value={surface.growth.communication_count} /></Col>
              </Row>
            </Card>
          </Col>
          <Col span={24}>
            <Card size="small" title="Current Bond Context">
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
            <Tag color={evolution?.accentTone ?? "purple"}>陪跑完成 {surface.growth.completed_support_runs}</Tag>
            <Tag color="green">愉快度 {surface.growth.pleasant_interaction_score}</Tag>
          </Col>
        </Row>
      )}
    </Drawer>
  );
}
