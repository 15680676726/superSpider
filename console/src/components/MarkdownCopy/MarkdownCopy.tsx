import { useState, useEffect, useMemo } from "react";
import type { CSSProperties } from "react";
import { Button, message, Switch, Input } from "@/ui";
import { CopyOutlined } from "@ant-design/icons";
import { Skeleton } from "antd";
import { LazyMarkdown } from "../LazyMarkdown";
import { stripFrontmatter } from "../../utils/markdown";
import styles from "./index.module.less";

interface MarkdownCopyProps {
  content: string;
  showMarkdown?: boolean;
  onShowMarkdownChange?: (show: boolean) => void;
  copyButtonProps?: {
    type?:
      | "text"
      | "link"
      | "default"
      | "primary"
      | "dashed"
      | "primaryLess"
      | "textCompact"
      | undefined;
    size?: "small" | "middle" | "large" | undefined;
    style?: CSSProperties;
  };
  markdownViewerProps?: {
    style?: CSSProperties;
    className?: string;
  };
  textareaProps?: {
    rows?: number;
    placeholder?: string;
    disabled?: boolean;
    style?: CSSProperties;
    className?: string;
  };
  showControls?: boolean;
  editable?: boolean;
  onContentChange?: (content: string) => void;
}

const COPY_SUCCESS = "已复制";
const COPY_FAILED = "复制失败";
const CONTENT_PLACEHOLDER = "请输入内容";
const CONTENT_LABEL = "内容";
const PREVIEW_LABEL = "预览";

export function MarkdownCopy({
  content,
  showMarkdown = true,
  onShowMarkdownChange,
  copyButtonProps = {},
  markdownViewerProps = {},
  textareaProps = {},
  showControls = true,
  editable = false,
  onContentChange,
}: MarkdownCopyProps) {
  const [isCopying, setIsCopying] = useState(false);
  const [editContent, setEditContent] = useState(content);
  const [localShowMarkdown, setLocalShowMarkdown] = useState(showMarkdown);
  const markdownContent = useMemo(
    () => stripFrontmatter(content || ""),
    [content],
  );

  useEffect(() => {
    setEditContent(content);
  }, [content]);

  useEffect(() => {
    if (editable && !textareaProps.disabled) {
      setLocalShowMarkdown(false);
      return;
    }
    setLocalShowMarkdown(showMarkdown);
  }, [editable, textareaProps.disabled, showMarkdown]);

  const copyToClipboard = async () => {
    const contentToCopy =
      localShowMarkdown && !(editable && !textareaProps.disabled)
        ? content
        : editable
          ? editContent
          : content;

    if (!contentToCopy) {
      return;
    }

    setIsCopying(true);
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(contentToCopy);
        message.success(COPY_SUCCESS);
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = contentToCopy;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand("copy");
        textArea.remove();
        message.success(COPY_SUCCESS);
      }
    } catch (err) {
      console.error("Failed to copy text: ", err);
      message.error(COPY_FAILED);
    } finally {
      setIsCopying(false);
    }
  };

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setEditContent(newContent);
    onContentChange?.(newContent);
  };

  const handleShowMarkdownChange = (show: boolean) => {
    setLocalShowMarkdown(show);
    onShowMarkdownChange?.(show);
  };

  const defaultCopyButtonProps = {
    type: "text" as const,
    size: "small" as const,
    ...copyButtonProps,
  };

  const defaultMarkdownViewerProps = {
    style: {
      padding: 16,
      height: "100%",
      overflow: "auto",
      backgroundColor: "#fff",
      borderRadius: 6,
      ...markdownViewerProps.style,
    },
    ...markdownViewerProps,
  };

  const defaultTextareaProps = {
    rows: 12,
    placeholder: CONTENT_PLACEHOLDER,
    ...textareaProps,
  };

  return (
    <div className={styles.markdownCopy}>
      {showControls && (
        <div className={styles.controls}>
          <div>{CONTENT_LABEL}</div>
          <div className={styles.controlGroup}>
            <div className={styles.previewToggle}>
              <span className={styles.previewLabel}>{PREVIEW_LABEL}</span>
              <Switch
                checked={localShowMarkdown}
                onChange={handleShowMarkdownChange}
                size="small"
              />
            </div>
            <Button
              icon={<CopyOutlined />}
              {...defaultCopyButtonProps}
              onClick={copyToClipboard}
              loading={isCopying}
            />
          </div>
        </div>
      )}

      {localShowMarkdown ? (
        <div className={styles.markdownViewer}>
          <LazyMarkdown
            content={markdownContent}
            fallback={
              <div
                className={defaultMarkdownViewerProps.className}
                style={defaultMarkdownViewerProps.style}
              >
                <Skeleton active paragraph={{ rows: 6 }} />
              </div>
            }
            {...defaultMarkdownViewerProps}
          />
        </div>
      ) : (
        <div className={styles.textareaContainer}>
          <Input.TextArea
            value={editable ? editContent : content}
            onChange={handleContentChange}
            {...defaultTextareaProps}
            className={styles.textarea}
            readOnly={!editable || textareaProps.disabled}
          />
        </div>
      )}
    </div>
  );
}
