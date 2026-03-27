import React, { useState, useMemo } from "react";
import { Button, Card, Input, Switch, message } from "@/ui";
import { CopyOutlined, UndoOutlined, SaveOutlined } from "@ant-design/icons";
import { Skeleton } from "antd";
import type { MarkdownFile } from "../../../../api/types";
import { LazyMarkdown } from "../../../../components/LazyMarkdown";
import { stripFrontmatter } from "../../../../utils/markdown";
import styles from "../index.module.less";

interface FileEditorProps {
  selectedFile: MarkdownFile | null;
  fileContent: string;
  loading: boolean;
  hasChanges: boolean;
  onContentChange: (content: string) => void;
  onSave: () => void;
  onReset: () => void;
}

export const FileEditor: React.FC<FileEditorProps> = ({
  selectedFile,
  fileContent,
  loading,
  hasChanges,
  onContentChange,
  onSave,
  onReset,
}) => {
  const [showMarkdown, setShowMarkdown] = useState(true);

  const isMarkdownFile = selectedFile?.filename.endsWith(".md") || false;
  const markdownContent = useMemo(
    () => stripFrontmatter(fileContent || ""),
    [fileContent],
  );

  const copyToClipboard = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(fileContent);
        message.success("已复制");
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = fileContent;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand("copy");
        textArea.remove();
        message.success("已复制");
      }
    } catch (err) {
      console.error("Failed to copy text: ", err);
      message.error("复制失败");
    }
  };

  return (
    <div className={styles.fileEditor}>
      <Card className={styles.editorCard}>
        {selectedFile ? (
          <>
            <div className={styles.editorHeader}>
              <div>
                <div className={styles.fileName}>{selectedFile.filename}</div>
                <div className={styles.filePath}>{selectedFile.path}</div>
              </div>
              <div className={styles.buttonGroup}>
                <Button
                  size="small"
                  onClick={onReset}
                  disabled={!hasChanges}
                  icon={<UndoOutlined />}
                >
                  {"重置"}
                </Button>
                <Button
                  type="primary"
                  size="small"
                  onClick={onSave}
                  disabled={!hasChanges}
                  loading={loading}
                  icon={<SaveOutlined />}
                >
                  {"保存"}
                </Button>
              </div>
            </div>

            <div className={styles.editorContent}>
              <div className={styles.contentLabel}>
                <div>{"内容"}</div>
                {isMarkdownFile && (
                  <div className={styles.buttonGroup}>
                    <div className={styles.markdownToggle}>
                      <span className={styles.toggleLabel}>{"预览"}</span>
                      <Switch
                        checked={showMarkdown}
                        onChange={setShowMarkdown}
                        size="small"
                      />
                    </div>
                    <Button
                      icon={<CopyOutlined />}
                      type="text"
                      onClick={() => void copyToClipboard()}
                      className={styles.copyButton}
                    />
                  </div>
                )}
              </div>
              {showMarkdown && isMarkdownFile ? (
                <LazyMarkdown
                  content={markdownContent}
                  className={styles.markdownViewer}
                  fallback={
                    <div className={styles.markdownViewer}>
                      <Skeleton active paragraph={{ rows: 8 }} />
                    </div>
                  }
                />
              ) : (
                <Input.TextArea
                  value={fileContent}
                  onChange={(e) => onContentChange(e.target.value)}
                  className={styles.textarea}
                  placeholder={"请输入文件内容"}
                />
              )}
            </div>
          </>
        ) : (
          <div className={styles.emptyState}>
            {"请选择要查看的文件"}
          </div>
        )}
      </Card>
    </div>
  );
};
