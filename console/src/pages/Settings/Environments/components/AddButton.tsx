import { SparkPlusLine } from "@agentscope-ai/icons";
import styles from "../index.module.less";

interface AddButtonProps {
  onClick: () => void;
  className?: string;
}

export function AddButton({ onClick, className }: AddButtonProps) {
  return (
    <div className={`${styles.addBar} ${className || ""}`}>
      <button
        className={styles.addBtn}
        onClick={onClick}
        title={"添加变量"}
      >
        <SparkPlusLine />
        <span>{"添加变量"}</span>
      </button>
    </div>
  );
}
