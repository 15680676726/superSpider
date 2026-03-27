import type { CSSProperties, ReactNode } from "react";

type BlockRendererProps = {
  children?: ReactNode;
  className?: string;
  header?: ReactNode;
  lang?: string;
  style?: CSSProperties;
};

function BlockRenderer({
  children,
  className,
  header,
  lang,
  style,
}: BlockRendererProps) {
  return (
    <div className={className} style={style}>
      {header}
      <pre
        data-language={lang || undefined}
        style={{
          margin: 0,
          overflowX: "auto",
          padding: 12,
          borderRadius: 8,
          background: "#f5f5f5",
          fontSize: 12,
          lineHeight: 1.6,
        }}
      >
        <code style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}>
          {children}
        </code>
      </pre>
    </div>
  );
}

export function CodeHighlighter(props: BlockRendererProps) {
  return <BlockRenderer {...props} />;
}

export function Mermaid(props: BlockRendererProps) {
  return <BlockRenderer {...props} />;
}
