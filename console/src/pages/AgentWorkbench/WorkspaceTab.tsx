import React, { useMemo, useRef } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  List,
  Space,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DownloadOutlined,
  FolderOpenOutlined,
  InboxOutlined,
  LinkOutlined,
  PlayCircleOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { workspaceApi } from "../../api/modules/workspace";
import {
  FileEditor,
  FileListPanel,
  useAgentsData,
} from "../Agent/Workspace/components";
import {
  commonText,
  getArtifactKindLabel,
  getEnvironmentDisplayName,
  getReplayTypeLabel,
  getStatusLabel,
  runtimeCenterText,
  workspaceText,
} from "./copy";
import { localizeWorkbenchText } from "./localize";
import type {
  AgentDetail,
  AgentProfile,
  EnvironmentArtifactItem,
  EnvironmentObservationItem,
  EnvironmentReplayItem,
} from "./useAgentWorkbench";

const { Paragraph, Text } = Typography;

function formatRuntimeTime(value: string | null | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const parsed = new Date(value.endsWith("Z") ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function RuntimeObservationList({
  title,
  emptyText,
  items,
  renderLine,
}: {
  title: string;
  emptyText: string;
  items: Array<EnvironmentObservationItem | EnvironmentReplayItem | EnvironmentArtifactItem>;
  renderLine: (
    item: EnvironmentObservationItem | EnvironmentReplayItem | EnvironmentArtifactItem,
  ) => React.ReactNode;
}) {
  return (
    <Card size="small" title={title} style={{ minHeight: 240 }}>
      <List
        dataSource={items}
        locale={{ emptyText }}
        renderItem={(item, index) => (
          <List.Item key={String(item.id ?? item.replay_id ?? item.artifact_id ?? index)}>
            {renderLine(item)}
          </List.Item>
        )}
      />
    </Card>
  );
}

export default function WorkspaceTab({
  agent,
  agentDetail,
  loading,
  error,
}: {
  agent: AgentProfile | null;
  agentDetail: AgentDetail | null;
  loading: boolean;
  error: string | null;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentEnvironmentLabel = workspaceText.currentEnvironment;
  const environmentRefLabel = workspaceText.environmentRef;
  const runtimeStatsLabel = workspaceText.runtimeStats;
  const runtimeBindingMissing = workspaceText.runtimeBindingMissing;
  const runtimeBindingHint = workspaceText.runtimeBindingHint;
  const observationsTitle = workspaceText.observationsTitle;
  const replaysTitle = workspaceText.replaysTitle;
  const artifactsTitle = workspaceText.artifactsTitle;
  const noObservations = workspaceText.noObservations;
  const noReplays = workspaceText.noReplays;
  const noArtifacts = workspaceText.noArtifacts;
  const filesUnavailable = workspaceText.filesUnavailable;

  const workspaceSummary = agentDetail?.workspace ?? null;
  const currentEnvironment =
    workspaceSummary?.current_environment ??
    agentDetail?.environments.find((item) => item.kind === "workspace") ??
    null;
  const filesSupported = Boolean(workspaceSummary?.files_supported);

  const {
    files,
    selectedFile,
    dailyMemories,
    expandedMemory,
    fileContent,
    loading: fileLoading,
    workspacePath,
    hasChanges,
    setFileContent,
    fetchFiles,
    handleFileClick,
    handleDailyMemoryClick,
    handleSave,
    handleReset,
  } = useAgentsData(filesSupported);

  const observations = useMemo(
    () => currentEnvironment?.observations ?? [],
    [currentEnvironment?.observations],
  );
  const replays = useMemo(
    () => currentEnvironment?.replays ?? [],
    [currentEnvironment?.replays],
  );
  const artifacts = useMemo(
    () => currentEnvironment?.artifacts ?? [],
    [currentEnvironment?.artifacts],
  );

  const handleDownload = async () => {
    try {
      const blob = await workspaceApi.downloadWorkspace();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `workspace-${new Date().toISOString().split("T")[0]}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(anchor);
      message.success(workspaceText.downloadSuccess);
    } catch (downloadError) {
      console.error("Workspace download failed:", downloadError);
      message.error(
        `${workspaceText.downloadFailed}: ${(downloadError as Error).message}`,
      );
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    if (!file.name.toLowerCase().endsWith(".zip")) {
      message.error(workspaceText.zipOnly);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
      message.error(
        workspaceText.fileSizeExceeded((file.size / (1024 * 1024)).toFixed(2)),
      );
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    try {
      const result = await workspaceApi.uploadFile(file);
      if (result.success) {
        message.success(workspaceText.uploadSuccess);
        await fetchFiles();
      } else {
        message.error(`${workspaceText.uploadFailed}: ${result.message}`);
      }
    } catch (uploadError) {
      console.error("Workspace upload failed:", uploadError);
      message.error(
        `${workspaceText.uploadFailed}: ${(uploadError as Error).message}`,
      );
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  if (!agent) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  if (loading) {
    return (
      <Card title={workspaceText.title} loading style={{ marginBottom: 32 }} />
    );
  }

  if (error) {
    return (
      <Alert
        showIcon
        type="error"
        message={runtimeCenterText.agentDetail}
        description={error}
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card
        className="baize-card"
        style={{
          background: "rgba(10, 22, 60, 0.45)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(201, 168, 76, 0.15)",
        }}
        title={
          <Space wrap>
            <FolderOpenOutlined style={{ color: "#C9A84C" }} />
            <span style={{ color: "white" }}>{workspaceText.title}</span>
            <Tag color="indigo" style={{ borderRadius: "6px", border: "none" }}>{agent.name}</Tag>
            {currentEnvironment?.status ? (
              <Tag color="blue" style={{ borderRadius: "6px", border: "none" }}>{getStatusLabel(currentEnvironment.status)}</Tag>
            ) : null}
          </Space>
        }
        extra={
          filesSupported ? (
            <Space>
              <Tooltip title={workspaceText.uploadTooltip}>
                <Button
                  size="small"
                  onClick={() => {
                    fileInputRef.current?.click();
                  }}
                  icon={<UploadOutlined />}
                  className="baize-btn"
                  style={{ background: "rgba(255, 255, 255, 0.05)", border: "1px solid rgba(255, 255, 255, 0.1)", color: "#e2e8f0" }}
                >
                  {commonText.upload}
                </Button>
              </Tooltip>
              <Button
                size="small"
                onClick={() => {
                  void handleDownload();
                }}
                icon={<DownloadOutlined />}
                className="baize-btn"
                style={{ background: "rgba(255, 255, 255, 0.05)", border: "1px solid rgba(255, 255, 255, 0.1)", color: "#e2e8f0" }}
              >
                {commonText.download}
              </Button>
            </Space>
          ) : null
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          {workspaceText.description} {workspaceText.taskProgressHint}
        </Paragraph>
        {currentEnvironment ? (
          <>
            <Paragraph style={{ marginBottom: 8 }}>
              <Text strong>{currentEnvironmentLabel}:</Text>{" "}
              {getEnvironmentDisplayName(
                currentEnvironment.kind,
                currentEnvironment.display_name,
              )}
            </Paragraph>
            <Paragraph style={{ marginBottom: 8 }}>
              <Text strong>{environmentRefLabel}:</Text>{" "}
              <Text code>{workspaceSummary?.current_environment_ref ?? currentEnvironment.ref}</Text>
            </Paragraph>
            {currentEnvironment.route ? (
              <Paragraph style={{ marginBottom: 8 }}>
                <Text strong>{runtimeCenterText.routesTitle}:</Text>{" "}
                <Text code>{currentEnvironment.route}</Text>
              </Paragraph>
            ) : null}
            <Space wrap>
              <Tag>{runtimeStatsLabel}</Tag>
              <Tag>
                {workspaceText.observationsTag(
                  currentEnvironment.stats?.observation_count ?? observations.length,
                )}
              </Tag>
              <Tag>
                {workspaceText.replaysTag(
                  currentEnvironment.stats?.replay_count ?? replays.length,
                )}
              </Tag>
              <Tag>
                {workspaceText.artifactsTag(
                  currentEnvironment.stats?.artifact_count ?? artifacts.length,
                )}
              </Tag>
            </Space>
          </>
        ) : (
          <Alert
            showIcon
            type="warning"
            message={runtimeBindingMissing}
            description={runtimeBindingHint}
          />
        )}
      </Card>

      {currentEnvironment ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          <RuntimeObservationList
            title={observationsTitle}
            emptyText={noObservations}
            items={observations}
            renderLine={(item) => (
              <Space direction="vertical" size={0}>
                <Text strong>
                  {localizeWorkbenchText(item.action_summary) || item.id || "-"}
                </Text>
                {item.result_summary ? (
                  <Text type="secondary">
                    {localizeWorkbenchText(item.result_summary)}
                  </Text>
                ) : null}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {formatRuntimeTime(item.created_at, runtimeCenterText.noTimestamp)}
                </Text>
              </Space>
            )}
          />
          <RuntimeObservationList
            title={replaysTitle}
            emptyText={noReplays}
            items={replays}
            renderLine={(item) => (
              <Space direction="vertical" size={0}>
                <Space wrap>
                  <PlayCircleOutlined />
                  <Text strong>
                    {item.replay_type
                      ? getReplayTypeLabel(item.replay_type)
                      : item.replay_id || "-"}
                  </Text>
                </Space>
                {item.storage_uri ? <Text type="secondary">{item.storage_uri}</Text> : null}
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {formatRuntimeTime(item.created_at, runtimeCenterText.noTimestamp)}
                </Text>
              </Space>
            )}
          />
          <RuntimeObservationList
            title={artifactsTitle}
            emptyText={noArtifacts}
            items={artifacts}
            renderLine={(item) => (
              <Space direction="vertical" size={0}>
                <Space wrap>
                  <InboxOutlined />
                  <Text strong>
                    {item.artifact_kind
                      ? getArtifactKindLabel(item.artifact_kind)
                      : item.artifact_id || "-"}
                  </Text>
                </Space>
                {item.storage_uri ? <Text type="secondary">{item.storage_uri}</Text> : null}
                {item.content_type ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {item.content_type}
                  </Text>
                ) : null}
              </Space>
            )}
          />
        </div>
      ) : null}

      {filesSupported ? (
        <Card
          title={workspaceText.filePanelTitle}
          extra={
            workspacePath ? (
              <Space>
                <LinkOutlined />
                <Text code>{workspacePath}</Text>
              </Space>
            ) : null
          }
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(280px, 360px) minmax(0, 1fr)",
              gap: 16,
              minHeight: 640,
            }}
          >
            <FileListPanel
              files={files}
              selectedFile={selectedFile}
              dailyMemories={dailyMemories}
              expandedMemory={expandedMemory}
              workspacePath={workspacePath}
              onRefresh={fetchFiles}
              onFileClick={handleFileClick}
              onDailyMemoryClick={handleDailyMemoryClick}
            />
            <FileEditor
              selectedFile={selectedFile}
              fileContent={fileContent}
              loading={fileLoading}
              hasChanges={hasChanges}
              onContentChange={setFileContent}
              onSave={handleSave}
              onReset={handleReset}
            />
          </div>
        </Card>
      ) : (
        <Alert
          showIcon
          type="info"
          message={filesUnavailable}
          description={runtimeBindingHint}
        />
      )}

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        style={{ display: "none" }}
        accept=".zip"
        title={workspaceText.zipInputTitle}
      />
    </div>
  );
}
