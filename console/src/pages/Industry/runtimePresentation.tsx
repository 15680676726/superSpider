import { Alert, Empty, List, Space, Tag, Typography } from "antd";

import type { IndustryCapabilityRecommendationSection } from "../../api/modules/industry";
import type { MediaAnalysisSummary } from "../../api/modules/media";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import {
  analysisStatusColor,
  formatAnalysisMode,
  formatAnalysisStatus,
  formatAnalysisWritebackStatus,
  formatMediaType,
  mediaTypeColor,
  resolveMediaTitle,
} from "../../utils/mediaPresentation";

const { Paragraph, Text } = Typography;

export function presentRecommendationSubsectionTitle(
  section: IndustryCapabilityRecommendationSection,
): string {
  if (section.section_kind === "execution-core") {
    return "编排能力";
  }
  if (section.section_kind === "system-baseline") {
    return "基础运行";
  }
  if (section.section_kind === "shared") {
    return "多人共用";
  }
  return normalizeSpiderMeshBrand(section.role_name || section.title) || section.title;
}

export function renderMediaAnalysisList(
  analyses: MediaAnalysisSummary[],
  options?: {
    emptyText?: string;
    adoptedTag?: string;
    showWriteback?: boolean;
  },
) {
  if (!analyses.length) {
    return (
      <Empty
        description={options?.emptyText || "暂无素材分析结果"}
        style={{ margin: "8px 0" }}
      />
    );
  }

  return (
    <List
      size="small"
      style={{ marginTop: 8 }}
      dataSource={analyses}
      renderItem={(analysis) => {
        const mediaType = analysis.detected_media_type || "unknown";
        const summary = analysis.summary || analysis.key_points?.slice(0, 2).join(" / ") || "暂无摘要";
        return (
          <List.Item style={{ padding: "10px 0" }}>
            <div style={{ width: "100%" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <Space wrap>
                    <Text strong style={{ color: "var(--baize-text-main)" }}>
                      {resolveMediaTitle(analysis)}
                    </Text>
                    <Tag color={mediaTypeColor(mediaType)}>{formatMediaType(mediaType)}</Tag>
                    <Tag>{formatAnalysisMode(analysis.analysis_mode)}</Tag>
                    <Tag color={analysisStatusColor(analysis.status)}>
                      {formatAnalysisStatus(analysis.status)}
                    </Tag>
                    {options?.adoptedTag ? <Tag color="green">{options.adoptedTag}</Tag> : null}
                    {options?.showWriteback && analysis.strategy_writeback_status ? (
                      <Tag>{`策略 ${formatAnalysisWritebackStatus(analysis.strategy_writeback_status)}`}</Tag>
                    ) : null}
                    {options?.showWriteback && analysis.backlog_writeback_status ? (
                      <Tag>{`待办 ${formatAnalysisWritebackStatus(analysis.backlog_writeback_status)}`}</Tag>
                    ) : null}
                  </Space>
                  <Paragraph style={{ margin: "8px 0 0" }}>{summary}</Paragraph>
                  {analysis.key_points?.length ? (
                    <Text type="secondary" style={{ display: "block" }}>
                      {analysis.key_points.slice(0, 3).join(" / ")}
                    </Text>
                  ) : null}
                  {(analysis.warnings || []).map((warning) => (
                    <Alert
                      key={`${analysis.analysis_id}:${warning}`}
                      type="warning"
                      showIcon
                      message={warning}
                      style={{ marginTop: 8 }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </List.Item>
        );
      }}
    />
  );
}
