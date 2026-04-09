import { Modal, Space, Tag } from "antd";
import {
  Activity,
  AlertTriangle,
  CircleDashed,
  LoaderCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { useRuntimeExecutionPulse } from "../hooks/useRuntimeExecutionPulse";
import RuntimeExecutionStrip from "./RuntimeExecutionStrip";
import styles from "./RuntimeExecutionLauncher.module.less";

function iconForState(
  loading: boolean,
  running: number,
  blocked: number,
  suspicious: number,
) {
  if (loading) {
    return <LoaderCircle size={18} className={styles.spin} />;
  }
  if (blocked > 0 || suspicious > 0) {
    return <AlertTriangle size={18} />;
  }
  if (running > 0) {
    return <Activity size={18} className={styles.pulse} />;
  }
  return <CircleDashed size={18} />;
}

export default function RuntimeExecutionLauncher() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [documentVisible, setDocumentVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState !== "hidden",
  );
  const launcherActive = open && documentVisible;

  useEffect(() => {
    if (typeof document === "undefined") {
      return undefined;
    }
    const syncVisibility = () => {
      setDocumentVisible(document.visibilityState !== "hidden");
    };
    document.addEventListener("visibilitychange", syncVisibility);
    return () => {
      document.removeEventListener("visibilitychange", syncVisibility);
    };
  }, []);

  const pulse = useRuntimeExecutionPulse({
    actor: "runtime-floating-launcher",
    maxItems: 6,
    active: launcherActive,
  });

  const metrics = useMemo(() => {
    const running = pulse.items.filter(
      (item) => item.currentTaskId || item.queueDepth > 0,
    ).length;
    const blocked = pulse.items.filter(
      (item) =>
        item.executionState === "waiting-confirm" ||
        item.executionState === "waiting-verification" ||
        item.runtimeStatus === "blocked",
    ).length;
    const suspicious = pulse.items.filter((item) =>
      item.signals.some((signal) => signal.level !== "good"),
    ).length;
    return {
      running,
      blocked,
      suspicious,
    };
  }, [pulse.items]);

  const statusText = !open
    ? "点击查看执行状态"
    : pulse.loading
      ? "正在同步执行状态"
      : metrics.running > 0
        ? `执行中 ${metrics.running}`
        : metrics.blocked > 0
          ? `待确认 ${metrics.blocked}`
          : pulse.items.length > 0
            ? "运行待命"
            : "当前空闲";

  if (location.pathname.startsWith("/runtime-center")) {
    return null;
  }

  return (
    <>
      <div className={styles.wrap}>
        <button
          type="button"
          className={styles.launcher}
          onClick={() => setOpen(true)}
          aria-label="打开当前执行总览"
          title={statusText}
        >
          {metrics.running > 0 || metrics.blocked > 0 || metrics.suspicious > 0 ? (
            <span className={styles.badge}>
              {metrics.running || metrics.blocked || metrics.suspicious}
            </span>
          ) : null}
          <div
            className={`${styles.iconWrap} ${
              metrics.blocked > 0 || metrics.suspicious > 0
                ? styles.iconAlert
                : metrics.running > 0
                  ? styles.iconBusy
                  : styles.iconIdle
            }`}
          >
            {iconForState(
              pulse.loading,
              metrics.running,
              metrics.blocked,
              metrics.suspicious,
            )}
          </div>
        </button>
      </div>

      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={1120}
        destroyOnHidden={false}
        title={
          <Space wrap size={8}>
            <span>当前执行总览</span>
            <Tag color={metrics.running > 0 ? "processing" : "default"}>
              {metrics.running > 0 ? `执行中 ${metrics.running}` : "当前空闲"}
            </Tag>
            <Tag color={metrics.blocked > 0 ? "error" : "default"}>
              {`待确认 ${metrics.blocked}`}
            </Tag>
            <Tag color={metrics.suspicious > 0 ? "warning" : "default"}>
              {`需关注 ${metrics.suspicious}`}
            </Tag>
          </Space>
        }
        className={`${styles.modal} baize-modal`}
        wrapClassName="baize-modal-wrap"
      >
        <RuntimeExecutionStrip
          sticky={false}
          title="当前执行总览"
          summary="集中查看谁在执行、为何触发、卡点与下一步，并可直接暂停或取消。"
          pulse={pulse}
        />
      </Modal>
    </>
  );
}
