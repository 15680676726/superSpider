import { useState } from "react";
import { Checkbox, Input } from "@/ui";
import { SparkDeleteLine, SparkPlusLine } from "@agentscope-ai/icons";
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import styles from "../index.module.less";

export interface Row {
  key: string;
  value: string;
  isNew?: boolean;
}

interface EnvRowProps {
  row: Row;
  idx: number;
  checked: boolean;
  error?: string;
  onToggle: (idx: number) => void;
  onChange: (idx: number, field: "key" | "value", val: string) => void;
  onInsert: (idx: number) => void;
  onRemove: (idx: number) => void;
}

export function EnvRow({
  row,
  idx,
  checked,
  error,
  onToggle,
  onChange,
  onInsert,
  onRemove,
}: EnvRowProps) {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);

  return (
    <div className={`${styles.envRow} ${checked ? styles.envRowSelected : ""}`}>
      <Checkbox
        checked={checked}
        onChange={() => onToggle(idx)}
        className={styles.rowCheckbox}
      />

      <div className={styles.fieldsWrap}>
        <div
          className={`${styles.inputGroup} ${
            error ? styles.inputGroupError : ""
          }`}
        >
          <span className={styles.inputLabel}>键</span>
          <Input
            value={row.key}
            placeholder="变量名"
            disabled={!row.isNew}
            onChange={(e) => onChange(idx, "key", e.target.value)}
            className={styles.inputField}
            autoFocus={row.isNew}
          />
        </div>

        <div className={styles.inputGroup}>
          <span className={styles.inputLabel}>值</span>
          <Input
            value={row.value}
            placeholder="值"
            type={isPasswordVisible ? "text" : "password"}
            onChange={(e) => onChange(idx, "value", e.target.value)}
            className={styles.inputField}
            suffix={
              <button
                className={styles.passwordToggle}
                onClick={() => setIsPasswordVisible(!isPasswordVisible)}
                type="button"
                title={
                  isPasswordVisible
                    ? "隐藏值"
                    : "显示值"
                }
              >
                {isPasswordVisible ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              </button>
            }
          />
        </div>
      </div>

      <div className={styles.rowActions}>
        <button
          className={styles.rowIconBtn}
          onClick={() => onInsert(idx)}
          title="在下方插入行"
        >
          <SparkPlusLine />
        </button>
        <button
          className={`${styles.rowIconBtn} ${styles.rowIconBtnDanger}`}
          onClick={() => onRemove(idx)}
          title="删除行"
        >
          <SparkDeleteLine />
        </button>
      </div>

      {error && <div className={styles.rowError}>{error}</div>}
    </div>
  );
}
