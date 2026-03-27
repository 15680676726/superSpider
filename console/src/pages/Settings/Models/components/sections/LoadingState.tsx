import { Button } from "@/ui";
import styles from "../../index.module.less";

interface LoadingStateProps {
  message: string;
  error?: boolean;
  onRetry?: () => void;
  className?: string;
}

export function LoadingState({
  message,
  error,
  onRetry,
  className,
}: LoadingStateProps) {
  return (
    <div className={`${styles.loading} ${className || ""}`}>
      <span
        className={styles.loadingText}
        style={{ color: error ? "#ff4d4f" : undefined }}
      >
        {message}
      </span>
      {error && onRetry && (
        <Button onClick={onRetry} style={{ marginTop: 12 }}>
          {"重试"}
        </Button>
      )}
    </div>
  );
}
