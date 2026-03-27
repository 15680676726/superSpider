import type { ButtonProps, CollapseProps, ConfigProviderProps, ImageProps } from "antd";
import {
  Alert,
  Button as AntdButton,
  Collapse,
  ConfigProvider,
  Image,
  InputNumber,
  Popover,
} from "antd";
import type { CSSProperties, ReactNode, VideoHTMLAttributes } from "react";

export {
  Card,
  Checkbox,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Switch,
  Tag,
  Tooltip,
  message,
} from "antd";

type SparkButtonType =
  | NonNullable<ButtonProps["type"]>
  | "primaryLess"
  | "textCompact";

type SparkButtonProps = Omit<ButtonProps, "type"> & {
  type?: SparkButtonType;
};

type IconButtonProps = Omit<SparkButtonProps, "icon"> & {
  icon: ReactNode;
  bordered?: boolean;
};

type CodeBlockProps = {
  className?: string;
  language?: string;
  readOnly?: boolean;
  style?: CSSProperties;
  value?: string;
};

type CollapsePanelProps = Omit<CollapseProps, "items"> & {
  children?: ReactNode;
  defaultOpen?: boolean;
  extra?: ReactNode;
  title?: ReactNode;
};

type VideoProps = VideoHTMLAttributes<HTMLVideoElement> & {
  className?: string;
  src?: string;
  style?: CSSProperties;
 };

function normalizeButtonType(type: SparkButtonType | undefined): ButtonProps["type"] {
  if (type === "primaryLess") {
    return "default";
  }
  if (type === "textCompact") {
    return "text";
  }
  return type;
}

export function Button({ type, ...rest }: SparkButtonProps) {
  return <AntdButton {...rest} type={normalizeButtonType(type)} />;
}

export function CodeBlock({
  className,
  language,
  style,
  value = "",
}: CodeBlockProps) {
  return (
    <pre
      className={className}
      data-language={language}
      style={{
        margin: 0,
        overflowX: "auto",
        padding: 12,
        borderRadius: 8,
        background: "#f5f5f5",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: 12,
        lineHeight: 1.6,
        ...style,
      }}
    >
      <code>{value}</code>
    </pre>
  );
}

export function CollapsePanel({
  children,
  defaultOpen = true,
  extra,
  title,
  ...rest
}: CollapsePanelProps) {
  return (
    <Collapse
      {...rest}
      defaultActiveKey={defaultOpen ? ["panel"] : []}
      items={[
        {
          key: "panel",
          label: title,
          extra,
          children,
        },
      ]}
    />
  );
}

export function IconButton({
  icon,
  bordered = true,
  type,
  ...rest
}: IconButtonProps) {
  return (
    <AntdButton
      {...rest}
      icon={icon}
      type={normalizeButtonType(type ?? (bordered ? "default" : "text"))}
    />
  );
}

export function Video({ className, src, style, ...rest }: VideoProps) {
  return (
    <video
      {...rest}
      className={className}
      controls={rest.controls ?? true}
      src={src}
      style={{
        maxWidth: "100%",
        ...style,
      }}
    />
  );
}

export function copy(content: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(content);
  }
  const textarea = document.createElement("textarea");
  textarea.value = content;
  textarea.style.position = "fixed";
  textarea.style.left = "-999999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
  return Promise.resolve();
}

export function generateTheme(options: {
  bgBaseHex?: string;
  darkMode?: boolean;
  primaryHex?: string;
  textBaseHex?: string;
}) {
  return {
    colorBgBase: options.bgBaseHex ?? (options.darkMode ? "#0f172a" : "#ffffff"),
    colorPrimary: options.primaryHex ?? "#615ced",
    colorTextBase: options.textBaseHex ?? (options.darkMode ? "#e7e7ed" : "#1f2937"),
  };
}

export function generateThemeByToken(token: Record<string, unknown>): ConfigProviderProps {
  return {
    theme: {
      cssVar: true,
      hashed: false,
      token,
    },
  };
}

export { Alert, ConfigProvider, Image, InputNumber, Popover };
export type { ImageProps };
