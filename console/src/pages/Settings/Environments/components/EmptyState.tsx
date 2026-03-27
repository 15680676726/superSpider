import styles from "../index.module.less";

interface EmptyStateProps {
  className?: string;
}

export function EmptyState({ className }: EmptyStateProps) {
  return (
    <div className={`${styles.emptyState} ${className || ""}`}>
      <span className={styles.emptyIcon}>📦</span>
      <span>{"尚未配置环境变量。"}</span>
    </div>
  );
}
