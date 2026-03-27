import {
  lazy,
  Suspense,
  type CSSProperties,
  type ReactNode,
} from "react";

const XMarkdown = lazy(async () => {
  const module = await import("@/ui/markdown");
  return { default: module.XMarkdown };
});

type MarkdownRendererProps = {
  content: string;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
};

interface LazyMarkdownProps extends MarkdownRendererProps {
  fallback?: ReactNode;
}

export function LazyMarkdown({
  content,
  className,
  style,
  fallback = null,
}: LazyMarkdownProps) {
  return (
    <Suspense fallback={fallback}>
      <XMarkdown className={className} content={content} style={style} />
    </Suspense>
  );
}
