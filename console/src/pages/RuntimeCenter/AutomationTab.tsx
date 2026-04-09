import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Table,
  Tag,
  TimePicker,
  Typography,
  message,
  type FormInstance,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { RefreshCw } from "lucide-react";
import api from "../../api";
import type {
  RuntimeHeartbeatConfig,
  RuntimeHeartbeatDetail,
  RuntimeScheduleConfig,
  RuntimeScheduleDetail,
  RuntimeScheduleHostBindingMeta,
  RuntimeScheduleSummary,
} from "../../api/types";
import styles from "./index.module.less";
import FixedSopPanel from "./FixedSopPanel";
import {
  AUTOMATION_TEXT,
  formatRuntimeActionLabel,
  formatRuntimeStatus,
  formatScheduleTaskType,
  localizeRuntimeText,
} from "./text";

dayjs.extend(customParseFormat);

const { Text } = Typography;
const TIME_FORMAT = "HH:mm";

type CronType = "hourly" | "daily" | "weekly" | "custom";
type EveryUnit = "m" | "h";

type ScheduleFormValues = Omit<RuntimeScheduleConfig, "request"> & {
  cronType?: CronType;
  cronTime?: dayjs.Dayjs | null;
  cronDaysOfWeek?: number[];
  cronCustom?: string;
  request?: Omit<NonNullable<RuntimeScheduleConfig["request"]>, "input"> & {
    input?: string;
  };
};

type HeartbeatFormValues = Omit<RuntimeHeartbeatConfig, "every"> & {
  everyNumber?: number;
  everyUnit?: EveryUnit;
  useActiveHours?: boolean;
  activeHoursStart?: string;
  activeHoursEnd?: string;
};

type ScheduleFormFieldValues =
  Parameters<FormInstance<ScheduleFormValues>["setFieldsValue"]>[0];

const TIMEZONE_OPTIONS = [
  { value: "UTC", label: "UTC" },
  { value: "Asia/Shanghai", label: "中国上海（UTC+8）" },
  { value: "Asia/Tokyo", label: "日本东京（UTC+9）" },
  { value: "Asia/Seoul", label: "韩国首尔（UTC+9）" },
  { value: "Asia/Hong_Kong", label: "中国香港（UTC+8）" },
  { value: "Asia/Singapore", label: "新加坡（UTC+8）" },
  { value: "Asia/Dubai", label: "阿联酋迪拜（UTC+4）" },
  { value: "Europe/London", label: "英国伦敦（UTC+0）" },
  { value: "Europe/Paris", label: "法国巴黎（UTC+1）" },
  { value: "Europe/Berlin", label: "德国柏林（UTC+1）" },
  { value: "Europe/Moscow", label: "俄罗斯莫斯科（UTC+3）" },
  { value: "America/New_York", label: "美国纽约（UTC-5）" },
  { value: "America/Chicago", label: "美国支加哥（UTC-6）" },
  { value: "America/Denver", label: "美国丹佛（UTC-7）" },
  { value: "America/Los_Angeles", label: "美国洛杉矶（UTC-8）" },
  { value: "America/Toronto", label: "加拿大多伦多（UTC-5）" },
  { value: "Australia/Sydney", label: "澳大利亚悉尼（UTC+10）" },
  { value: "Australia/Melbourne", label: "澳大利亚墨尔本（UTC+10）" },
  { value: "Pacific/Auckland", label: "新西兰奥克兰（UTC+12）" },
];

const DEFAULT_SCHEDULE_FORM_VALUES: ScheduleFormValues = {
  id: "",
  name: "",
  enabled: true,
  schedule: {
    type: "cron",
    cron: "0 9 * * *",
    timezone: "UTC",
  },
  cronType: "daily",
  cronTime: dayjs().hour(9).minute(0),
  task_type: "agent",
  dispatch: {
    type: "channel",
    channel: "console",
    target: {
      user_id: "",
      session_id: "",
    },
    mode: "final",
  },
  runtime: {
    max_concurrency: 1,
    timeout_seconds: 120,
    misfire_grace_seconds: 60,
  },
  request: {
    input: "",
  },
};

const TARGET_OPTIONS = [
  { value: "main", label: AUTOMATION_TEXT.heartbeat.targetMain },
  { value: "last", label: AUTOMATION_TEXT.heartbeat.targetLast },
];

const CRON_RE = /^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$/;
const EVERY_RE =
  /^(?:(?<hours>\d+)h)?(?:(?<minutes>\d+)m)?(?:(?<seconds>\d+)s)?$/i;

function normalizeSchedule(item: RuntimeScheduleSummary): RuntimeScheduleSummary {
  return {
    ...item,
    title: item.title || item.name || item.id,
    actions: item.actions ?? {},
  };
}

function nonEmptyString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const next = value.trim();
  return next || null;
}

function readScheduleHostMeta(
  schedule?: RuntimeScheduleSummary | null,
): RuntimeScheduleHostBindingMeta | null {
  if (schedule?.host_meta && typeof schedule.host_meta === "object") {
    return schedule.host_meta;
  }
  return null;
}

function getScheduleHostWarnings(hostMeta?: RuntimeScheduleHostBindingMeta | null): string[] {
  if (!hostMeta) {
    return [];
  }

  const warnings = new Set<string>();
  const environmentRef = nonEmptyString(hostMeta.environment_ref);
  const sessionMountId = nonEmptyString(hostMeta.session_mount_id);
  const snapshotEnvironmentRef = nonEmptyString(hostMeta.host_snapshot?.environment_ref);
  const snapshotSessionMountId = nonEmptyString(hostMeta.host_snapshot?.session_mount_id);
  const schedulerEnvironmentRef = nonEmptyString(
    hostMeta.scheduler_inputs?.environment_ref ??
      hostMeta.host_snapshot?.scheduler_inputs?.environment_ref,
  );
  const schedulerSessionMountId = nonEmptyString(
    hostMeta.scheduler_inputs?.session_mount_id ??
      hostMeta.host_snapshot?.scheduler_inputs?.session_mount_id,
  );

  if (
    environmentRef &&
    ((snapshotEnvironmentRef && snapshotEnvironmentRef !== environmentRef) ||
      (schedulerEnvironmentRef && schedulerEnvironmentRef !== environmentRef))
  ) {
    warnings.add("环境引用不一致");
  }

  if (
    sessionMountId &&
    ((snapshotSessionMountId && snapshotSessionMountId !== sessionMountId) ||
      (schedulerSessionMountId && schedulerSessionMountId !== sessionMountId))
  ) {
    warnings.add("会话挂载不一致");
  }

  return [...warnings];
}

function parseCron(cron: string): {
  type: CronType;
  hour?: number;
  minute?: number;
  daysOfWeek?: number[];
  rawCron?: string;
} {
  const trimmed = (cron || "").trim();
  if (!trimmed) {
    return { type: "daily", hour: 9, minute: 0 };
  }

  const match = trimmed.match(CRON_RE);
  if (!match) {
    return { type: "custom", rawCron: trimmed };
  }

  const [, minute, hour, dayOfMonth, month, dayOfWeek] = match;

  if (
    hour === "*" &&
    dayOfMonth === "*" &&
    month === "*" &&
    dayOfWeek === "*" &&
    minute === "0"
  ) {
    return { type: "hourly", minute: 0 };
  }

  if (dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    const parsedHour = parseInt(hour, 10);
    const parsedMinute = parseInt(minute, 10);
    if (
      !Number.isNaN(parsedHour) &&
      !Number.isNaN(parsedMinute) &&
      parsedHour >= 0 &&
      parsedHour < 24 &&
      parsedMinute >= 0 &&
      parsedMinute < 60
    ) {
      return { type: "daily", hour: parsedHour, minute: parsedMinute };
    }
  }

  if (dayOfMonth === "*" && month === "*" && dayOfWeek !== "*") {
    const parsedHour = parseInt(hour, 10);
    const parsedMinute = parseInt(minute, 10);
    if (
      !Number.isNaN(parsedHour) &&
      !Number.isNaN(parsedMinute) &&
      parsedHour >= 0 &&
      parsedHour < 24 &&
      parsedMinute >= 0 &&
      parsedMinute < 60
    ) {
      const days = dayOfWeek
        .split(",")
        .flatMap((part) => {
          if (part.includes("-")) {
            const [start, end] = part.split("-").map((value) => parseInt(value, 10));
            if (Number.isNaN(start) || Number.isNaN(end)) {
              return [];
            }
            return Array.from({ length: end - start + 1 }, (_, index) => start + index);
          }
          const day = parseInt(part, 10);
          return Number.isNaN(day) ? [] : [day];
        })
        .filter((day, index, list) => day >= 0 && day <= 6 && list.indexOf(day) === index);
      if (days.length > 0) {
        return {
          type: "weekly",
          hour: parsedHour,
          minute: parsedMinute,
          daysOfWeek: days,
        };
      }
    }
  }

  return { type: "custom", rawCron: trimmed };
}

function serializeCron(values: ScheduleFormValues): string {
  if (values.cronType === "hourly") {
    return "0 * * * *";
  }
  if (values.cronType === "custom") {
    return values.cronCustom?.trim() || "0 9 * * *";
  }

  const hour = values.cronTime?.hour() ?? 9;
  const minute = values.cronTime?.minute() ?? 0;
  if (values.cronType === "weekly") {
    const days =
      values.cronDaysOfWeek && values.cronDaysOfWeek.length > 0
        ? [...values.cronDaysOfWeek].sort((left, right) => left - right).join(",")
        : "1";
    return `${minute} ${hour} * * ${days}`;
  }
  return `${minute} ${hour} * * *`;
}

function parseEvery(every: string): { number: number; unit: EveryUnit } {
  const match = (every || "").trim().match(EVERY_RE);
  if (!match?.groups) {
    return { number: 6, unit: "h" };
  }
  const hours = parseInt(match.groups.hours ?? "0", 10);
  const minutes = parseInt(match.groups.minutes ?? "0", 10);
  const seconds = parseInt(match.groups.seconds ?? "0", 10);
  const totalMinutes = hours * 60 + minutes + Math.round(seconds / 60);
  if (totalMinutes <= 0) {
    return { number: 6, unit: "h" };
  }
  if (totalMinutes >= 60 && totalMinutes % 60 === 0) {
    return { number: totalMinutes / 60, unit: "h" };
  }
  return { number: totalMinutes, unit: "m" };
}

function serializeEvery(number = 6, unit: EveryUnit = "h"): string {
  return `${number}${unit}`;
}

function statusColor(status: string) {
  if (["failed", "error"].includes(status)) {
    return "error";
  }
  if (["running", "scheduled", "success", "active"].includes(status)) {
    return "success";
  }
  if (["paused", "reviewing", "waiting-confirm", "skipped"].includes(status)) {
    return "warning";
  }
  return "default";
}

function formatRuntimeTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

function TimePickerHHmm({
  value,
  onChange,
}: {
  value?: string | null;
  onChange?: (next: string) => void;
}) {
  return (
    <TimePicker
      format={TIME_FORMAT}
      value={value ? dayjs(value, TIME_FORMAT) : null}
      onChange={(_, text) => {
        const next = Array.isArray(text) ? text[0] : text;
        if (next) {
          onChange?.(next);
        }
      }}
      minuteStep={15}
      needConfirm={false}
      style={{ width: "100%" }}
    />
  );
}

function buildScheduleFormValues(detail: RuntimeScheduleDetail): ScheduleFormValues {
  const cronParts = parseCron(detail.spec.schedule?.cron || "0 9 * * *");
  return {
    ...detail.spec,
    cronType: cronParts.type,
    cronTime:
      cronParts.type === "daily" || cronParts.type === "weekly"
        ? dayjs().hour(cronParts.hour ?? 9).minute(cronParts.minute ?? 0)
        : null,
    cronDaysOfWeek: cronParts.daysOfWeek,
    cronCustom: cronParts.rawCron,
    request: {
      ...detail.spec.request,
      input: detail.spec.request?.input
        ? JSON.stringify(detail.spec.request.input, null, 2)
        : "",
    },
  };
}

function buildSchedulePayload(values: ScheduleFormValues): RuntimeScheduleConfig {
  const payload: RuntimeScheduleConfig = {
    id: values.id.trim(),
    name: values.name.trim(),
    enabled: values.enabled ?? true,
    schedule: {
      type: "cron",
      cron: serializeCron(values),
      timezone: values.schedule?.timezone || "UTC",
    },
    task_type: values.task_type || "agent",
    text: values.text?.trim() || undefined,
    dispatch: {
      type: "channel",
      channel: values.dispatch?.channel || "console",
      target: {
        user_id: values.dispatch?.target?.user_id?.trim() || "",
        session_id: values.dispatch?.target?.session_id?.trim() || "",
      },
      mode: values.dispatch?.mode || "final",
      meta: values.dispatch?.meta || {},
    },
    runtime: {
      max_concurrency: values.runtime?.max_concurrency ?? 1,
      timeout_seconds: values.runtime?.timeout_seconds ?? 120,
      misfire_grace_seconds: values.runtime?.misfire_grace_seconds ?? 60,
    },
    meta: values.meta || {},
  };

  if (payload.task_type === "text") {
    payload.text = values.text?.trim() || "";
  } else {
    let parsedInput: unknown = values.request?.input || "";
    if (typeof parsedInput === "string" && parsedInput.trim()) {
      try {
        parsedInput = JSON.parse(parsedInput);
      } catch {
        // Fallback or ignore parse error if handled by form
      }
    }
    payload.request = {
      ...(values.request || {}),
      input: parsedInput,
      user_id: payload.dispatch.target.user_id,
      session_id: payload.dispatch.target.session_id,
    };
  }

  return payload;
}

interface AutomationTabProps {
  focusScope?: string | null;
  refreshSignal?: string;
  openDetail: (route: string, title: string) => Promise<void>;
  onRuntimeChanged?: () => Promise<void> | void;
}

export default function AutomationTab({
  focusScope,
  refreshSignal,
  openDetail,
  onRuntimeChanged,
}: AutomationTabProps) {
  const [schedules, setSchedules] = useState<RuntimeScheduleSummary[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [scheduleRefreshing, setScheduleRefreshing] = useState(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [heartbeatDetail, setHeartbeatDetail] = useState<RuntimeHeartbeatDetail | null>(null);
  const [heartbeatLoading, setHeartbeatLoading] = useState(true);
  const [heartbeatSaving, setHeartbeatSaving] = useState(false);
  const [heartbeatRunning, setHeartbeatRunning] = useState(false);
  const [heartbeatError, setHeartbeatError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null);
  const [actingScheduleId, setActingScheduleId] = useState<string | null>(null);
  const [heartbeatForm] = Form.useForm<HeartbeatFormValues>();
  const [scheduleForm] = Form.useForm<ScheduleFormValues>();
  const heartbeatAnchorRef = useRef<HTMLDivElement | null>(null);
  const didLoadRef = useRef(false);

  const loadSchedules = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") {
      setScheduleLoading(true);
    } else {
      setScheduleRefreshing(true);
    }
    try {
      const payload = await api.listRuntimeSchedules();
      setSchedules((payload || []).map(normalizeSchedule));
      setScheduleError(null);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      setScheduleError(detail);
    } finally {
      setScheduleLoading(false);
      setScheduleRefreshing(false);
    }
  }, []);

  const loadHeartbeat = useCallback(async () => {
    setHeartbeatLoading(true);
    try {
      const detail = await api.getRuntimeHeartbeat();
      const config = detail.heartbeat;
      const parsedEvery = parseEvery(config.every ?? "6h");
      setHeartbeatDetail(detail);
      heartbeatForm.setFieldsValue({
        enabled: config.enabled ?? false,
        everyNumber: parsedEvery.number,
        everyUnit: parsedEvery.unit,
        target: config.target ?? "main",
        useActiveHours: !!config.activeHours,
        activeHoursStart: config.activeHours?.start ?? "08:00",
        activeHoursEnd: config.activeHours?.end ?? "22:00",
      });
      setHeartbeatError(null);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      setHeartbeatDetail(null);
      setHeartbeatError(detail);
    } finally {
      setHeartbeatLoading(false);
    }
  }, [heartbeatForm]);

  useEffect(() => {
    void Promise.all([loadSchedules("initial"), loadHeartbeat()]);
  }, [loadHeartbeat, loadSchedules]);

  useEffect(() => {
    if (!refreshSignal) {
      return;
    }
    if (!didLoadRef.current) {
      didLoadRef.current = true;
      return;
    }
    void Promise.all([loadSchedules(), loadHeartbeat()]);
  }, [loadHeartbeat, loadSchedules, refreshSignal]);

  useEffect(() => {
    if (focusScope !== "heartbeat" || !heartbeatAnchorRef.current) {
      return;
    }
    heartbeatAnchorRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focusScope]);

  const refreshRuntimeSurface = useCallback(async () => {
    await Promise.resolve(onRuntimeChanged?.());
  }, [onRuntimeChanged]);

  const openCreateDrawer = () => {
    setEditingScheduleId(null);
    scheduleForm.resetFields();
    scheduleForm.setFieldsValue(
      DEFAULT_SCHEDULE_FORM_VALUES as unknown as ScheduleFormFieldValues,
    );
    setDrawerOpen(true);
  };

  const openEditDrawer = useCallback(async (scheduleId: string) => {
    setDrawerLoading(true);
    try {
      const detail = await api.getRuntimeSchedule(scheduleId);
      scheduleForm.resetFields();
      scheduleForm.setFieldsValue(
        buildScheduleFormValues(detail) as unknown as ScheduleFormFieldValues,
      );
      setEditingScheduleId(scheduleId);
      setDrawerOpen(true);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      message.error(detail);
    } finally {
      setDrawerLoading(false);
    }
  }, [scheduleForm]);

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditingScheduleId(null);
    scheduleForm.resetFields();
  };

  const handleScheduleSubmit = async (values: ScheduleFormValues) => {
    setSavingSchedule(true);
    try {
      const payload = buildSchedulePayload(values);
      if (editingScheduleId) {
        await api.updateRuntimeSchedule(editingScheduleId, payload);
      } else {
        await api.createRuntimeSchedule(payload);
      }
      message.success(AUTOMATION_TEXT.saved);
      closeDrawer();
      await Promise.all([loadSchedules(), refreshRuntimeSurface()]);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      message.error(detail);
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleDeleteSchedule = useCallback(async (schedule: RuntimeScheduleSummary) => {
    Modal.confirm({
      title: "确认删除",
      content: "确定要删除此定时任务吗？",
      okText: "删除",
      cancelText: "取消",
      onOk: async () => {
        setActingScheduleId(`delete:${schedule.id}`);
        try {
          await api.deleteRuntimeSchedule(schedule.id);
          message.success(AUTOMATION_TEXT.deleted);
          await Promise.all([loadSchedules(), refreshRuntimeSurface()]);
        } catch (error) {
          const detail = localizeRuntimeText(
            error instanceof Error ? error.message : String(error),
          );
          message.error(detail);
        } finally {
          setActingScheduleId(null);
        }
      },
    });
  }, [loadSchedules, refreshRuntimeSurface]);

  const invokeScheduleAction = useCallback(async (
    schedule: RuntimeScheduleSummary,
    action: "run" | "pause" | "resume",
  ) => {
    setActingScheduleId(`${action}:${schedule.id}`);
    try {
      if (action === "run") {
        await api.runRuntimeSchedule(schedule.id);
      } else if (action === "pause") {
        await api.pauseRuntimeSchedule(schedule.id);
      } else {
        await api.resumeRuntimeSchedule(schedule.id);
      }
      message.success(`${formatRuntimeActionLabel(action)}已完成`);
      await Promise.all([loadSchedules(), refreshRuntimeSurface()]);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      message.error(detail);
    } finally {
      setActingScheduleId(null);
    }
  }, [loadSchedules, refreshRuntimeSurface]);

  const handleHeartbeatSubmit = async (values: HeartbeatFormValues) => {
    setHeartbeatSaving(true);
    try {
      const result = await api.updateRuntimeHeartbeat({
        enabled: values.enabled ?? false,
        every: serializeEvery(values.everyNumber, values.everyUnit),
        target: values.target ?? "main",
        activeHours:
          values.useActiveHours && values.activeHoursStart && values.activeHoursEnd
            ? {
                start: values.activeHoursStart,
                end: values.activeHoursEnd,
              }
            : undefined,
      });
      setHeartbeatDetail(result.heartbeat);
      setHeartbeatError(null);
      message.success(AUTOMATION_TEXT.heartbeat.saveSuccess);
      await Promise.all([loadHeartbeat(), refreshRuntimeSurface()]);
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      setHeartbeatError(detail);
      message.error(detail);
    } finally {
      setHeartbeatSaving(false);
    }
  };

  const handleHeartbeatRun = async () => {
    setHeartbeatRunning(true);
    try {
      const result = await api.runRuntimeHeartbeat();
      setHeartbeatDetail(result.heartbeat);
      setHeartbeatError(null);
      if (result.result?.status === "success") {
        message.success(
          `${formatRuntimeActionLabel("run")}已完成：${localizeRuntimeText(
            String(result.result?.reason || result.result?.status || "运行"),
          )}`,
        );
      }
    } catch (error) {
      const detail = localizeRuntimeText(
        error instanceof Error ? error.message : String(error),
      );
      setHeartbeatError(detail);
      message.error(detail);
    } finally {
      setHeartbeatRunning(false);
    }
  };

  const columns = useMemo<ColumnsType<RuntimeScheduleSummary>>(
    () => [
      {
        title: "任务名称",
        dataIndex: "title",
        key: "title",
        width: 220,
        render: (_, record) =>
          record.route ? (
            <button
              type="button"
              className={styles.entryTitleButton}
              onClick={() =>
                void openDetail(
                  record.route || `/api/runtime-center/schedules/${record.id}`,
                  localizeRuntimeText(record.title || record.id),
                )
              }
            >
              {localizeRuntimeText(record.title || record.id)}
            </button>
          ) : (
            <span>{localizeRuntimeText(record.title || record.id)}</span>
          ),
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string) => (
          <Tag color={statusColor(value)}>
            {formatRuntimeStatus(value)}
          </Tag>
        ),
      },
      {
        title: "定时策略",
        key: "cron",
        width: 210,
        render: (_, record) => (
          <div className={styles.automationCell}>
            <code className={styles.mono}>{record.cron || "-"}</code>
            <Text type="secondary">
              {record.task_type ? formatScheduleTaskType(record.task_type) : "-"}
            </Text>
          </div>
        ),
      },
      {
        title: "宿主绑定",
        key: "hostBinding",
        width: 320,
        render: (_, record) => {
          const hostMeta = readScheduleHostMeta(record);
          if (!hostMeta) {
            return <Text type="secondary">暂无宿主绑定</Text>;
          }

          const warnings = getScheduleHostWarnings(hostMeta);
          const environmentRef = nonEmptyString(hostMeta.environment_ref);
          const environmentId = nonEmptyString(
            hostMeta.environment_id ?? hostMeta.host_snapshot?.environment_id,
          );
          const sessionMountId = nonEmptyString(hostMeta.session_mount_id);
          const appFamily = nonEmptyString(hostMeta.host_requirement?.app_family);
          const schedulerAction = nonEmptyString(
            hostMeta.host_snapshot?.coordination?.recommended_scheduler_action,
          );

          return (
            <div className={styles.automationCell}>
              <Text>{environmentRef || environmentId || "-"}</Text>
              <Text type="secondary">{sessionMountId || "-"}</Text>
              {appFamily ? <Text type="secondary">{appFamily}</Text> : null}
              {schedulerAction ? (
                <Text type="secondary">{`宿主协同：${schedulerAction}`}</Text>
              ) : null}
              {warnings.length > 0 ? (
                <div className={styles.automationCell}>
                  <Tag color="gold">宿主绑定警告</Tag>
                  {warnings.map((warning) => (
                    <Text key={warning} type="warning">
                      {warning}
                    </Text>
                  ))}
                </div>
              ) : null}
            </div>
          );
        },
      },
      {
        title: "所属角色",
        key: "owner",
        width: 180,
        render: (_, record) => (
          <div className={styles.automationCell}>
            <Text strong>{record.owner || "系统"}</Text>
            <Text type="secondary" style={{ fontSize: '12px' }}>ID: {record.id}</Text>
          </div>
        ),
      },
      {
        title: "执行时间线",
        key: "timeline",
        width: 220,
        render: (_, record) => (
          <div className={styles.automationCell}>
            <Text type="secondary">
              最近: {formatRuntimeTime(record.last_run_at)}
            </Text>
            <Text type="secondary">
              下次: {formatRuntimeTime(record.next_run_at)}
            </Text>
            {record.last_error && (
              <Text type="danger" ellipsis title={localizeRuntimeText(record.last_error)}>
                错误: {localizeRuntimeText(record.last_error)}
              </Text>
            )}
          </div>
        ),
      },
      {
        title: "操作",
        key: "actions",
        width: 200,
        fixed: 'right',
        render: (_, record) => (
          <Space wrap size={4}>
            {record.actions?.run && (
              <Button
                size="small"
                type="link"
                loading={actingScheduleId === `run:${record.id}`}
                onClick={() => void invokeScheduleAction(record, "run")}
              >
                运行
              </Button>
            )}
            {record.actions?.resume && (
              <Button
                size="small"
                type="link"
                loading={actingScheduleId === `resume:${record.id}`}
                onClick={() => void invokeScheduleAction(record, "resume")}
              >
                恢复
              </Button>
            )}
            {record.actions?.pause && (
              <Button
                size="small"
                type="link"
                loading={actingScheduleId === `pause:${record.id}`}
                onClick={() => void invokeScheduleAction(record, "pause")}
              >
                暂停
              </Button>
            )}
            <Button size="small" type="link" onClick={() => void openEditDrawer(record.id)}>
              编辑
            </Button>
            {record.actions?.delete && (
              <Button
                size="small"
                type="link"
                danger
                loading={actingScheduleId === `delete:${record.id}`}
                onClick={() => void handleDeleteSchedule(record)}
              >
                删除
              </Button>
            )}
          </Space>
        ),
      },
    ],
    [actingScheduleId, openDetail, openEditDrawer, handleDeleteSchedule, invokeScheduleAction],
  );

  return (
    <div className={styles.automationStack}>
      <div ref={heartbeatAnchorRef} className={styles.sectionAnchor} />
      
      {/* 心跳管理卡片 */}
      <Card 
        className={styles.card} 
        title={<span className={styles.cardTitle}>心跳控制</span>}
        extra={
          <Space>
             <Button
              loading={heartbeatRunning}
              onClick={() => void handleHeartbeatRun()}
            >
              立即运行
            </Button>
            <Button
              icon={<RefreshCw size={14} />}
              loading={heartbeatLoading}
              onClick={() => void loadHeartbeat()}
            >
              刷新
            </Button>
          </Space>
        }
      >
        <Alert
          showIcon
          type="info"
          className={styles.automationAlert}
          message="心跳现在是主脑监督脉冲，会定期触发运营周期检查与正式回流。"
          style={{ marginBottom: 24 }}
        />

        {heartbeatError && (
          <Alert
            showIcon
            type="error"
            message={heartbeatError}
            style={{ marginBottom: 24 }}
          />
        )}

        {heartbeatDetail && (
          <div className={styles.heartbeatStatusPanel}>
            <Row gutter={16} align="middle">
              <Col span={4}>
                <Tag color={statusColor(heartbeatDetail.runtime.status)} style={{ padding: '4px 12px' }}>
                  {formatRuntimeStatus(heartbeatDetail.runtime.status).toUpperCase()}
                </Tag>
              </Col>
              <Col span={10}>
                <Text type="secondary">最近运行: </Text>
                <Text>{formatRuntimeTime(heartbeatDetail.runtime.last_run_at)}</Text>
              </Col>
              <Col span={10}>
                <Text type="secondary">下次运行: </Text>
                <Text>{formatRuntimeTime(heartbeatDetail.runtime.next_run_at)}</Text>
              </Col>
            </Row>
            {heartbeatDetail.runtime.last_error && (
              <div style={{ marginTop: 8 }}>
                <Text type="danger">上次错误: {localizeRuntimeText(heartbeatDetail.runtime.last_error)}</Text>
              </div>
            )}
          </div>
        )}

        {heartbeatLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : (
          <Form
            form={heartbeatForm}
            layout="vertical"
            onFinish={(values) => void handleHeartbeatSubmit(values)}
          >
            <Row gutter={24}>
              <Col xs={24} sm={6}>
                <Form.Item name="enabled" label="启用状态" valuePropName="checked">
                  <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={10}>
                <Form.Item label="心跳频率" required>
                  <Space.Compact style={{ width: '100%' }}>
                    <Form.Item
                      name="everyNumber"
                      noStyle
                      rules={[{ required: true, message: '必填' }]}
                    >
                      <InputNumber min={1} style={{ width: '60%' }} />
                    </Form.Item>
                    <Form.Item name="everyUnit" noStyle>
                      <Select style={{ width: '40%' }}>
                        <Select.Option value="m">分钟</Select.Option>
                        <Select.Option value="h">小时</Select.Option>
                      </Select>
                    </Form.Item>
                  </Space.Compact>
                </Form.Item>
              </Col>
              <Col xs={24} sm={8}>
                <Form.Item name="target" label="上报目标">
                  <Select options={TARGET_OPTIONS} />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={24} align="bottom">
              <Col xs={24} sm={6}>
                <Form.Item name="useActiveHours" label="时段限制" valuePropName="checked">
                  <Switch checkedChildren="限制" unCheckedChildren="全天" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={18}>
                <Form.Item noStyle shouldUpdate>
                  {({ getFieldValue }) => getFieldValue("useActiveHours") ? (
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name="activeHoursStart" label="活跃开始">
                          <TimePickerHHmm />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name="activeHoursEnd" label="活跃结束">
                          <TimePickerHHmm />
                        </Form.Item>
                      </Col>
                    </Row>
                  ) : null}
                </Form.Item>
              </Col>
            </Row>

            <div style={{ textAlign: 'right', marginTop: 12 }}>
              <Button type="primary" htmlType="submit" loading={heartbeatSaving}>
                保存配置
              </Button>
            </div>
          </Form>
        )}
      </Card>

      {/* 定时任务管理卡片 */}
      <Card 
        className={styles.card}
        title={<span className={styles.cardTitle}>计划任务</span>}
        extra={
          <Space>
            <Button
              icon={<RefreshCw size={14} />}
              loading={scheduleRefreshing}
              onClick={() => void loadSchedules()}
            >
              刷新列表
            </Button>
            <Button type="primary" onClick={openCreateDrawer}>
              新建任务
            </Button>
          </Space>
        }
      >
        {scheduleError && (
          <Alert
            showIcon
            type="error"
            message={scheduleError}
            style={{ marginBottom: 24 }}
          />
        )}
        <Table
          rowKey="id"
          loading={scheduleLoading}
          columns={columns}
          dataSource={schedules}
          size="middle"
          scroll={{ x: 1000 }}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 任务编辑对话框 */}
      <FixedSopPanel
        focusScope={focusScope}
        openDetail={openDetail}
        onRuntimeChanged={onRuntimeChanged}
      />

      <Modal
        destroyOnClose
        open={drawerOpen}
        title={editingScheduleId ? "编辑计划任务" : "创建计划任务"}
        width={720}
        onCancel={closeDrawer}
        onOk={() => scheduleForm.submit()}
        confirmLoading={savingSchedule}
        okText="保存"
        cancelText="取消"
      >
        {drawerLoading ? (
          <Skeleton active paragraph={{ rows: 10 }} />
        ) : (
          <Form
            form={scheduleForm}
            layout="vertical"
            initialValues={DEFAULT_SCHEDULE_FORM_VALUES}
            onFinish={(values) => void handleScheduleSubmit(values)}
          >
            <Row gutter={16}>
              <Col span={14}>
                <Form.Item
                  name="name"
                  label="任务标题"
                  rules={[{ required: true, message: '请输入标题' }]}
                >
                  <Input placeholder="例如: 每日早报发送" />
                </Form.Item>
              </Col>
              <Col span={10}>
                <Form.Item
                  name="id"
                  label="任务标识码 (ID)"
                  rules={[{ required: true, message: '请输入唯一ID' }]}
                >
                  <Input disabled={!!editingScheduleId} placeholder="daily_report" />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name="enabled" label="启用状态" valuePropName="checked">
                  <Switch />
                </Form.Item>
              </Col>
              <Col span={18}>
                 <Row gutter={12}>
                  <Col span={10}>
                    <Form.Item name="cronType" label="计划类型">
                      <Select>
                        <Select.Option value="hourly">每小时</Select.Option>
                        <Select.Option value="daily">每天</Select.Option>
                        <Select.Option value="weekly">每周</Select.Option>
                        <Select.Option value="custom">自定义 (Cron)</Select.Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={14}>
                    <Form.Item noStyle shouldUpdate={(p, n) => p.cronType !== n.cronType}>
                      {({ getFieldValue }) => {
                        const type = getFieldValue("cronType");
                        if (type === "daily" || type === "weekly") {
                          return (
                            <Row gutter={8}>
                              {type === "weekly" ? (
                                <Col span={14}>
                                  <Form.Item name="cronDaysOfWeek" label="星期" rules={[{ required: true, message: '请选择' }]}>
                                    <Select mode="multiple" placeholder="选择天">
                                      <Select.Option value={1}>周一</Select.Option>
                                      <Select.Option value={2}>周二</Select.Option>
                                      <Select.Option value={3}>周三</Select.Option>
                                      <Select.Option value={4}>周四</Select.Option>
                                      <Select.Option value={5}>周五</Select.Option>
                                      <Select.Option value={6}>周六</Select.Option>
                                      <Select.Option value={0}>周日</Select.Option>
                                    </Select>
                                  </Form.Item>
                                </Col>
                              ) : null}
                              <Col span={type === "weekly" ? 10 : 24}>
                                <Form.Item name="cronTime" label="时间" rules={[{ required: true, message: '请选择' }]}>
                                  <TimePicker format="HH:mm" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                            </Row>
                          );
                        }
                        if (type === "custom") {
                          return (
                            <Form.Item name="cronCustom" label="Cron 表达式" rules={[{ required: true, message: '请输入' }]}>
                              <Input placeholder="* * * * *" />
                            </Form.Item>
                          );
                        }
                        return null;
                      }}
                    </Form.Item>
                  </Col>
                </Row>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name={["schedule", "timezone"]} label="执行时区">
                  <Select showSearch options={TIMEZONE_OPTIONS} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="task_type" label="任务类型" rules={[{ required: true }]}>
                  <Select>
                    <Select.Option value="agent">执行 Agent 指令</Select.Option>
                    <Select.Option value="text">发送文本消息</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            <Form.Item noStyle shouldUpdate={(p, n) => p.task_type !== n.task_type}>
              {({ getFieldValue }) => getFieldValue("task_type") === "agent" ? (
                <Form.Item name={["request", "input"]} label="Agent 指令参数 (JSON)" rules={[{ required: true }]}>
                  <Input.TextArea rows={4} className={styles.monoInput} placeholder='{ "goal": "..." }' />
                </Form.Item>
              ) : (
                <Form.Item name="text" label="消息正文" rules={[{ required: true }]}>
                  <Input.TextArea rows={3} placeholder="输入要发送的消息内容" />
                </Form.Item>
              )}
            </Form.Item>

            <fieldset style={{ border: `1px solid var(--baize-border-color)`, padding: '16px', borderRadius: '12px', marginBottom: '24px', width: '100%' }}>
              <legend style={{ padding: '0 8px', fontSize: '13px', color: 'var(--baize-text-muted)' }}>分发配置</legend>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name={["dispatch", "channel"]} label="频道" rules={[{ required: true }]}>
                    <Input placeholder="console" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={["dispatch", "target", "user_id"]} label="目标用户" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={["dispatch", "target", "session_id"]} label="目标会话" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
            </fieldset>

            <Row gutter={12}>
              <Col span={8}>
                <Form.Item name={["runtime", "max_concurrency"]} label="最大并发">
                  <InputNumber min={1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={["runtime", "timeout_seconds"]} label="超时(秒)">
                  <InputNumber min={1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name={["runtime", "misfire_grace_seconds"]} label="宽限期(秒)">
                  <InputNumber min={0} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        )}
      </Modal>
    </div>
  );
}
