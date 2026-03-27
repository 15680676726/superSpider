import React from "react";
import { Button, Card } from "@/ui";
import { ReloadOutlined } from "@ant-design/icons";
import type { MarkdownFile, DailyMemoryFile } from "../../../../api/types";
import { FileItem } from "./FileItem";
import styles from "../index.module.less";

interface FileListPanelProps {
  files: MarkdownFile[];
  selectedFile: MarkdownFile | null;
  dailyMemories: DailyMemoryFile[];
  expandedMemory: boolean;
  workspacePath: string;
  onRefresh: () => void;
  onFileClick: (file: MarkdownFile) => void;
  onDailyMemoryClick: (daily: DailyMemoryFile) => void;
}

export const FileListPanel: React.FC<FileListPanelProps> = ({
  files,
  selectedFile,
  dailyMemories,
  expandedMemory,
  onRefresh,
  onFileClick,
  onDailyMemoryClick,
}) => {
  return (
    <div className={styles.fileListPanel}>
      <Card
        bodyStyle={{
          padding: 16,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          overflow: "auto",
        }}
        style={{ flex: 1, minHeight: 0 }}
      >
        <div className={styles.headerRow}>
          <h3 className={styles.sectionTitle}>{"核心文件"}</h3>
          <Button size="small" onClick={onRefresh} icon={<ReloadOutlined />}>
            {"刷新"}
          </Button>
        </div>

        <p className={styles.infoText}>
          {
            "查看工作区中的核心 Markdown 文件与记忆文件。"
          }
        </p>
        <div className={styles.divider} />

        <div className={styles.scrollContainer}>
          {files.length > 0 ? (
            files.map((file) => (
              <FileItem
                key={file.filename}
                file={file}
                selectedFile={selectedFile}
                expandedMemory={expandedMemory}
                dailyMemories={dailyMemories}
                onFileClick={onFileClick}
                onDailyMemoryClick={onDailyMemoryClick}
              />
            ))
          ) : (
            <div className={styles.emptyState}>{"暂无文件"}</div>
          )}
        </div>
      </Card>
    </div>
  );
};
