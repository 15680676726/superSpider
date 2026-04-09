import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

export type XMarkdownProps = {
  children?: ReactNode;
  className?: string;
  components?: Components;
  content?: string;
  style?: CSSProperties;
  [key: string]: unknown;
};

export function XMarkdown({
  children,
  className,
  components,
  content,
  style,
}: XMarkdownProps) {
  const markdown =
    typeof content === "string"
      ? content
      : typeof children === "string"
        ? children
        : "";

  return (
    <div className={className} style={style}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a(anchorProps) {
            return <a {...anchorProps} rel="noreferrer" target="_blank" />;
          },
          code({ className: codeClassName, children: codeChildren, ...codeProps }) {
            return (
              <code
                {...codeProps}
                className={codeClassName}
                style={{
                  padding: "0.1em 0.35em",
                  borderRadius: 4,
                  background: "rgba(15, 23, 42, 0.08)",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                }}
              >
                {codeChildren}
              </code>
            );
          },
          pre({ children: preChildren, ...preProps }) {
            return (
              <pre
                {...(preProps as HTMLAttributes<HTMLPreElement>)}
                style={{
                  margin: "12px 0",
                  overflowX: "auto",
                  padding: 12,
                  borderRadius: 8,
                  background: "#f5f5f5",
                  fontSize: 12,
                  lineHeight: 1.6,
                }}
              >
                {preChildren}
              </pre>
            );
          },
          table(tableProps) {
            return (
              <div style={{ overflowX: "auto" }}>
                <table {...tableProps} />
              </div>
            );
          },
          ...components,
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

export default XMarkdown;
