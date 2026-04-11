import { useEffect, useState } from "react";
import { ChevronRight, Sparkles } from "lucide-react";
import { Col, Progress, Row, Spin, Statistic, Tag, Typography } from "antd";
import { useLocation } from "react-router-dom";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  BUDDY_ANIMATION_INTERVAL_MS,
  buildBuddyAvatarView,
  renderBuddyFace,
} from "../../pages/Chat/buddyAvatar";
import { resolveBuddyEvolutionView } from "../../pages/Chat/buddyEvolution";
import { resolveBuddyDisplaySnapshot } from "../../pages/Chat/buddyPresentation";
import {
  BUDDY_PROFILE_CHANGED_EVENT,
  readActiveBuddyProfileId,
} from "../../runtime/buddyProfileBinding";
import {
  getBuddySummarySnapshot,
  subscribeBuddySummary,
  type BuddySummarySnapshot,
} from "../../runtime/buddySummaryStore";
import styles from "./index.module.less";

const { Text } = Typography;

interface CustomWindow extends Window {
  currentThreadMeta?: Record<string, unknown>;
}

declare const window: CustomWindow;

// ── 空态（未绑定伙伴） ──────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className={styles.emptyState}>
      <div className={styles.emptyIcon}>
        <Sparkles size={28} />
      </div>
      <div className={styles.emptyTitle}>尚无伙伴</div>
      <div className={styles.emptyDesc}>在聊天中绑定伙伴后，这里会显示伙伴详情</div>
    </div>
  );
}

// ── 主面板 ──────────────────────────────────────────────────────────────
export default function RightPanel() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [boundProfileId, setBoundProfileId] = useState<string | null>(() =>
    readActiveBuddyProfileId(window.currentThreadMeta),
  );
  const initialSnapshot = (() => {
    const profileId = readActiveBuddyProfileId(window.currentThreadMeta);
    return profileId
      ? getBuddySummarySnapshot(profileId)
      : { loading: false, error: null, surface: null };
  })();
  const [summarySnapshot, setSummarySnapshot] =
    useState<BuddySummarySnapshot>(initialSnapshot);
  const [tick, setTick] = useState(0);
  const [documentVisible, setDocumentVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState !== "hidden",
  );
  const shouldShowPanel = Boolean(boundProfileId);
  const surface: BuddySurfaceResponse | null = summarySnapshot.surface;
  const loading = summarySnapshot.loading;
  const shouldAnimateAvatar =
    shouldShowPanel &&
    !collapsed &&
    documentVisible &&
    surface !== null;

  useEffect(() => {
    setBoundProfileId(readActiveBuddyProfileId(window.currentThreadMeta));
  }, [location.key, location.pathname]);

  useEffect(() => {
    const syncBoundProfile = (event: Event) => {
      const detail =
        event instanceof CustomEvent && event.detail && typeof event.detail === "object"
          ? event.detail
          : null;
      const threadMeta =
        detail && "meta" in detail ? (detail.meta as Record<string, unknown> | undefined) : null;
      setBoundProfileId(readActiveBuddyProfileId(threadMeta ?? window.currentThreadMeta));
    };
    const syncStoredProfile = (event: Event) => {
      const detail =
        event instanceof CustomEvent && event.detail && typeof event.detail === "object"
          ? event.detail
          : null;
      const profileId =
        detail && "profileId" in detail ? (detail.profileId as string | null | undefined) : null;
      setBoundProfileId(readActiveBuddyProfileId({ buddy_profile_id: profileId ?? null }));
    };
    window.addEventListener("copaw:thread-context", syncBoundProfile);
    window.addEventListener(BUDDY_PROFILE_CHANGED_EVENT, syncStoredProfile);
    return () => {
      window.removeEventListener("copaw:thread-context", syncBoundProfile);
      window.removeEventListener(BUDDY_PROFILE_CHANGED_EVENT, syncStoredProfile);
    };
  }, []);

  useEffect(() => {
    if (!boundProfileId) {
      setSummarySnapshot({
        loading: false,
        error: null,
        surface: null,
      });
      return undefined;
    }
    setSummarySnapshot(getBuddySummarySnapshot(boundProfileId));
    return subscribeBuddySummary(boundProfileId, setSummarySnapshot);
  }, [boundProfileId]);

  useEffect(() => {
    if (typeof document === "undefined") {
      return undefined;
    }
    const syncVisibility = () => {
      setDocumentVisible(document.visibilityState !== "hidden");
    };
    document.addEventListener("visibilitychange", syncVisibility);
    return () => {
      document.removeEventListener("visibilitychange", syncVisibility);
    };
  }, []);

  // 头像动画 tick
  useEffect(() => {
    if (!shouldAnimateAvatar) {
      return undefined;
    }
    const timer = window.setInterval(() => setTick((t) => t + 1), BUDDY_ANIMATION_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [shouldAnimateAvatar]);

  if (!shouldShowPanel) {
    return null;
  }

  const snapshot = surface ? resolveBuddyDisplaySnapshot(surface) : null;
  const evolution = surface
    ? resolveBuddyEvolutionView({
        evolutionStage: surface.growth.evolution_stage,
        currentForm: surface.presentation.current_form,
        capabilityPoints: surface.growth.capability_points,
        capabilityScore: surface.growth.capability_score,
        companionExperience: surface.growth.companion_experience,
        rarity: surface.presentation.rarity,
      })
    : null;
  const avatar = surface ? buildBuddyAvatarView(surface, { tick }) : null;

  return (
    <>
      {/* 折叠后的右侧竖条 */}
      {collapsed && (
        <div className={styles.collapsedTab} onClick={() => setCollapsed(false)}>
          <ChevronRight size={13} />
          <span className={styles.collapsedLabel}>伙伴</span>
        </div>
      )}

      {/* 展开面板 */}
      <div className={`${styles.panel} ${collapsed ? styles.panelHidden : ""}`}>

        {/* ── 头部：收起按钮 + 伙伴名 ── */}
        <div className={styles.panelHeader}>
          <span className={styles.panelTitle}>伙伴详情</span>
          <button className={styles.collapseBtn} onClick={() => setCollapsed(true)} type="button">
            <ChevronRight size={13} />
          </button>
        </div>

        <div className={styles.scrollArea}>
          {loading ? (
            <div className={styles.loadingState}><Spin /></div>
          ) : !surface || !snapshot || !avatar ? (
            <EmptyState />
          ) : (
            <>
              {/* ── 头像区 ── */}
              <div className={styles.avatarSection}>
                <div
                  className={styles.spriteBox}
                  data-stage={evolution?.stage ?? snapshot.stage}
                  data-presence={surface.presentation.presence_state}
                  data-frame={avatar.frameIndex}
                  style={{ colorScheme: "light" }}
                >
                  {/* 内联 style 强制绕过所有全局 CSS 继承 */}
                  <div
                    className={styles.spriteAscii}
                    aria-hidden="true"
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      fontFamily: '"Consolas", "Courier New", Courier, monospace',
                      fontSize: "16px",
                      lineHeight: "1.1",
                      color: "#111827",
                      whiteSpace: "pre",
                      letterSpacing: "0",
                      fontWeight: 400,
                    }}
                  >
                    {avatar.lines.map((line, i) => (
                      <span key={`${avatar.species}-${i}`} style={{ display: "block", color: "#111827" }}>{line}</span>
                    ))}
                  </div>
                </div>
                <div className={styles.buddyName}>{snapshot.buddyName}</div>
                <div className={styles.buddyStage}>{snapshot.stageLabel} · {evolution?.rarityLabel ?? surface.presentation.rarity}</div>
                <div className={styles.tagRow}>
                  <Tag color={evolution?.accentTone ?? "purple"}>{avatar.speciesLabel}</Tag>
                  <Tag color="gold">{avatar.rarityStars}</Tag>
                  {avatar.shiny ? <Tag color="magenta">闪亮</Tag> : null}
                  <Tag>{renderBuddyFace(avatar)}</Tag>
                </div>
              </div>

              {/* ── 状态信息 ── */}
              <div className={styles.infoSection}>
                <div className={styles.infoRow}><span className={styles.infoLabel}>心情</span><span className={styles.infoValue}>{snapshot.moodLabel}</span></div>
              </div>

              {/* ── 关系数值 ── */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionLabel}>关系</div>
                <Row gutter={12}>
                  <Col span={12}><Statistic title="亲密度" value={surface.growth.intimacy} /></Col>
                  <Col span={12}><Statistic title="契合度" value={surface.growth.affinity} /></Col>
                </Row>
                {snapshot.companionStrategySummary ? (
                  <div className={styles.strategyText}>
                    <Text type="secondary" style={{ fontSize: 11 }}>陪伴策略：{snapshot.companionStrategySummary}</Text>
                  </div>
                ) : null}
              </div>

              {/* ── 成长 ── */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionLabel}>成长</div>
                <Row gutter={12}>
                  <Col span={12}><Statistic title="成长积分" value={snapshot.capabilityPoints} /></Col>
                  <Col span={12}><Statistic title="有效闭环" value={snapshot.settledClosureCount} /></Col>
                </Row>
                <div className={styles.progressWrap}>
                  <div className={styles.progressLabel}>下阶段进度</div>
                  <Progress percent={snapshot.progressToNextStage} size="small" />
                </div>
                <Row gutter={12} style={{ marginTop: 10 }}>
                  <Col span={12}><Statistic title="独立成果" value={snapshot.independentOutcomeCount} /></Col>
                  <Col span={12}><Statistic title="跨周期数" value={snapshot.distinctSettledCycleCount} /></Col>
                </Row>
                <Row gutter={12} style={{ marginTop: 10 }}>
                  <Col span={12}><Statistic title="完成率" value={Math.round(snapshot.recentCompletionRate * 100)} suffix="%" /></Col>
                  <Col span={12}><Statistic title="出错率" value={Math.round(snapshot.recentExecutionErrorRate * 100)} suffix="%" /></Col>
                </Row>
              </div>

              {/* ── 领域能力 ── */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionLabel}>领域能力</div>
                <Row gutter={12}>
                  <Col span={12}><Statistic title="策略分" value={surface.growth.strategy_score ?? 0} /></Col>
                  <Col span={12}><Statistic title="执行分" value={surface.growth.execution_score ?? 0} /></Col>
                </Row>
                <Row gutter={12} style={{ marginTop: 10 }}>
                  <Col span={12}><Statistic title="证据分" value={surface.growth.evidence_score ?? 0} /></Col>
                  <Col span={12}><Statistic title="稳定度" value={surface.growth.stability_score ?? 0} /></Col>
                </Row>
              </div>

              {/* ── 当前推进背景 ── */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionLabel}>当前推进背景</div>
                <div className={styles.contextItem}><span className={styles.contextLabel}>最终目标</span><span className={styles.contextValue}>{snapshot.finalGoalSummary}</span></div>
                <div className={styles.contextItem}><span className={styles.contextLabel}>当前任务</span><span className={styles.contextValue}>{snapshot.currentTaskSummary}</span></div>
                <div className={styles.contextItem}><span className={styles.contextLabel}>为什么现在做</span><span className={styles.contextValue}>{snapshot.whyNowSummary}</span></div>
                <div className={styles.contextItem}><span className={styles.contextLabel}>唯一下一步</span><span className={styles.contextValue}>{snapshot.singleNextActionSummary}</span></div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
