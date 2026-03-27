import { Checkbox, Button } from "@/ui";
import { SparkDeleteLine } from "@agentscope-ai/icons";
import styles from "../index.module.less";

interface ToolbarProps {
  workingRowsLength: number;
  allSelected: boolean;
  someSelected: boolean;
  selectedSize: number;
  dirty: boolean;
  saving: boolean;
  indeterminate: boolean;
  onToggleSelectAll: () => void;
  onRemoveSelected: () => void;
  onReset: () => void;
  onSave: () => void;
  className?: string;
}

export function Toolbar({
  workingRowsLength,
  allSelected,
  someSelected,
  selectedSize,
  dirty,
  saving,
  indeterminate,
  onToggleSelectAll,
  onRemoveSelected,
  onReset,
  onSave,
  className,
}: ToolbarProps) {
  return (
    <div className={`${styles.toolbar} ${className || ""}`}>
      <div className={styles.toolbarLeft}>
        {workingRowsLength > 0 && (
          <Checkbox
            checked={allSelected}
            indeterminate={indeterminate}
            onChange={onToggleSelectAll}
          />
        )}
        <span className={styles.toolbarCount}>
          {someSelected
            ? `${selectedSize} ${"共"} ${workingRowsLength} ${"已选"}`
            : `${workingRowsLength} ${
                workingRowsLength !== 1
                  ? "变量"
                  : "变量"
              }`}
        </span>
      </div>

      <div className={styles.toolbarRight}>
        {someSelected && (
          <Button
            danger
            size="small"
            icon={<SparkDeleteLine />}
            onClick={onRemoveSelected}
            disabled={saving}
          >
            {"删除"} ({selectedSize})
          </Button>
        )}
        {dirty && (
          <>
            <Button size="small" onClick={onReset} disabled={saving}>
              {"重置"}
            </Button>
            <Button
              type="primary"
              size="small"
              loading={saving}
              onClick={onSave}
            >
              {"保存"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
