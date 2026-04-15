import { useState, useCallback, useMemo } from "react";
import { Button, Modal, message } from "@/ui";
import api from "../../../api";
import { useEnvVars } from "./useEnvVars";
import {
  PageHeader,
  MemorySettingsCard,
  EmptyState,
  AddButton,
  Toolbar,
  EnvRow,
  type Row,
} from "./components";
import styles from "./index.module.less";

const RETIRED_MEMORY_ENV_KEYS = new Set([
  "COPAW_MEMORY_QMD_PREWARM",
  "COPAW_MEMORY_QMD_QUERY_MODE",
  "EMBEDDING_API_KEY",
  "EMBEDDING_BASE_URL",
  "EMBEDDING_MODEL_NAME",
  "EMBEDDING_FOLLOW_ACTIVE_PROVIDER",
]);

function shiftIndices(prev: Set<number>, removedIdx: number): Set<number> {
  const next = new Set<number>();
  prev.forEach((i) => {
    if (i < removedIdx) next.add(i);
    else if (i > removedIdx) next.add(i - 1);
  });
  return next;
}

function rowsToEnvDict(rows: Row[]): Record<string, string> {
  const dict: Record<string, string> = {};
  rows.forEach((row) => {
    const key = row.key.trim();
    if (key) {
      dict[key] = row.value;
    }
  });
  return dict;
}

function EnvironmentsPage() {
  const { envVars, loading, error, fetchAll } = useEnvVars();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [keyErrors, setKeyErrors] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const workingRows: Row[] = useMemo(
    () => rows ?? envVars.map((e) => ({ key: e.key, value: e.value })),
    [rows, envVars],
  );
  const envValueMap = useMemo(() => rowsToEnvDict(workingRows), [workingRows]);
  const memoryRecallBackendRaw = envValueMap.COPAW_MEMORY_RECALL_BACKEND ?? "";
  const retiredMemoryRowIndexes = useMemo(
    () =>
      workingRows
        .map((row, index) => ({ row, index }))
        .filter(({ row }) => RETIRED_MEMORY_ENV_KEYS.has(row.key.trim()))
        .map(({ index }) => index),
    [workingRows],
  );
  const retiredMemoryKeys = useMemo(
    () =>
      retiredMemoryRowIndexes
        .map((index) => workingRows[index]?.key.trim())
        .filter((value): value is string => Boolean(value)),
    [retiredMemoryRowIndexes, workingRows],
  );
  const visibleRowIndexes = useMemo(
    () =>
      workingRows
        .map((row, index) => ({ row, index }))
        .filter(({ row }) => !RETIRED_MEMORY_ENV_KEYS.has(row.key.trim()))
        .map(({ index }) => index),
    [workingRows],
  );

  const dirty = rows !== null;
  const someSelected = selected.size > 0;
  const allSelected =
    visibleRowIndexes.length > 0 &&
    visibleRowIndexes.every((index) => selected.has(index));
  const ensureLocal = useCallback((): Row[] => {
    if (rows) return [...rows];
    return envVars.map((e) => ({ key: e.key, value: e.value }));
  }, [rows, envVars]);

  const toggleSelect = useCallback((idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(visibleRowIndexes));
    }
  }, [allSelected, visibleRowIndexes]);

  const applyEnvPatch = useCallback(
    (patch: Record<string, string | null>) => {
      const next = ensureLocal();

      Object.entries(patch).forEach(([key, value]) => {
        const rowIndex = next.findIndex((row) => row.key.trim() === key);
        const shouldDelete = value === null || value.trim() === "";

        if (shouldDelete) {
          if (rowIndex >= 0) {
            next.splice(rowIndex, 1);
          }
          return;
        }

        if (rowIndex >= 0) {
          next[rowIndex] = {
            ...next[rowIndex],
            key,
            value,
          };
          return;
        }

        next.push({
          key,
          value,
          isNew: true,
        });
      });

      setRows(next.length === 0 && envVars.length === 0 ? null : next);
      setSelected(new Set());
      setKeyErrors({});
    },
    [ensureLocal, envVars.length],
  );

  const handleManagedFtsEnabledChange = useCallback(
    (value: boolean) => {
      applyEnvPatch({
        FTS_ENABLED: value ? "true" : "false",
      });
    },
    [applyEnvPatch],
  );

  const handleManagedBackendChange = useCallback(
    (value: string) => {
      applyEnvPatch({
        MEMORY_STORE_BACKEND: value,
      });
    },
    [applyEnvPatch],
  );

  const handleApplyRecommendedMemoryDefaults = useCallback(() => {
    applyEnvPatch({
      COPAW_MEMORY_RECALL_BACKEND: "truth-first",
      COPAW_MEMORY_QMD_PREWARM: null,
      COPAW_MEMORY_QMD_QUERY_MODE: null,
      EMBEDDING_API_KEY: null,
      EMBEDDING_BASE_URL: null,
      EMBEDDING_MODEL_NAME: null,
      EMBEDDING_FOLLOW_ACTIVE_PROVIDER: null,
      FTS_ENABLED: "true",
      MEMORY_STORE_BACKEND: "auto",
    });
  }, [applyEnvPatch]);

  const updateRow = useCallback(
    (idx: number, field: "key" | "value", val: string) => {
      const next = ensureLocal();
      next[idx] = { ...next[idx], [field]: val };
      setRows(next);
      if (field === "key") {
        setKeyErrors((prev) => {
          const copy = { ...prev };
          delete copy[idx];
          return copy;
        });
      }
    },
    [ensureLocal],
  );

  const addRow = useCallback(() => {
    const next = ensureLocal();
    next.push({ key: "", value: "", isNew: true });
    setRows(next);
  }, [ensureLocal]);

  const insertRowAfter = useCallback(
    (idx: number) => {
      const next = ensureLocal();
      next.splice(idx + 1, 0, { key: "", value: "", isNew: true });
      setRows(next);
      setSelected((prev) => {
        const rebuilt = new Set<number>();
        prev.forEach((i) => rebuilt.add(i <= idx ? i : i + 1));
        return rebuilt;
      });
    },
    [ensureLocal],
  );

  const removeRow = useCallback(
    (idx: number) => {
      const row = workingRows[idx];

      if (row.isNew) {
        const next = ensureLocal();
        next.splice(idx, 1);
        setRows(next.length === 0 && envVars.length === 0 ? null : next);
        setSelected((prev) => shiftIndices(prev, idx));
        return;
      }

      Modal.confirm({
        title: "删除变量",
        content: `确定删除“${row.key}”吗？`,
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: async () => {
          try {
            await api.deleteEnv(row.key);
            message.success(`“${row.key}”已删除`);
            setRows(null);
            setSelected(new Set());
            setKeyErrors({});
            fetchAll();
          } catch (err) {
            message.error(
              err instanceof Error ? err.message : "删除失败",
            );
          }
        },
      });
    },
    [workingRows, ensureLocal, envVars.length, fetchAll],
  );

  const removeSelected = useCallback(() => {
    if (selected.size === 0) return;
    const indices = Array.from(selected).sort((a, b) => a - b);
    const names = indices.map((i) => workingRows[i]?.key).filter(Boolean);
    const hasPersistedRows = indices.some((i) => !workingRows[i]?.isNew);

    if (!hasPersistedRows) {
      const next = ensureLocal().filter((_, i) => !selected.has(i));
      setRows(next.length === 0 && envVars.length === 0 ? null : next);
      setSelected(new Set());
      return;
    }

    const label =
      names.length <= 3
        ? names.map((n) => `“${n}”`).join("、")
        : `${names.length} 个变量`;

    Modal.confirm({
      title: "删除选中项",
      content: `确定删除 ${label} 吗？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          const persistedKeysToDelete = indices
            .map((i) => workingRows[i])
            .filter((row) => row && !row.isNew)
            .map((row) => row.key.trim())
            .filter(Boolean);

          if (persistedKeysToDelete.length > 0) {
            await Promise.all(
              persistedKeysToDelete.map((key) => api.deleteEnv(key)),
            );
          }

          message.success(`${label}已删除`);
          setRows(null);
          setSelected(new Set());
          setKeyErrors({});
          fetchAll();
        } catch (err) {
          message.error(
            err instanceof Error ? err.message : "删除失败",
          );
        }
      },
    });
  }, [selected, workingRows, ensureLocal, envVars.length, fetchAll]);

  const validate = useCallback((): boolean => {
    const errors: Record<number, string> = {};
    const seen = new Set<string>();
    for (let i = 0; i < workingRows.length; i++) {
      const k = workingRows[i].key.trim();
      if (!k) {
        errors[i] = "变量名为必填项";
      } else if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) {
        errors[i] = "变量名格式无效";
      } else if (seen.has(k)) {
        errors[i] = "变量名重复";
      }
      seen.add(k);
    }
    setKeyErrors(errors);
    return Object.keys(errors).length === 0;
  }, [workingRows]);

  const handleSave = useCallback(async () => {
    if (!validate()) {
      message.error(
        "保存前请先修复非法的环境变量行。",
      );
      return;
    }

    const dict = rowsToEnvDict(workingRows);
    setSaving(true);
    try {
      await api.saveEnvs(dict);
      message.success("环境变量已保存");
      setRows(null);
      setKeyErrors({});
      setSelected(new Set());
      fetchAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [validate, workingRows, fetchAll]);

  const handleReset = useCallback(() => {
    setRows(null);
    setKeyErrors({});
    setSelected(new Set());
  }, []);

  return (
    <div className={`${styles.page} page-container`}>
      <PageHeader />

      {loading ? (
        <div className={styles.centerState}>
          <span className={styles.stateText}>{"加载中..."}</span>
        </div>
      ) : error ? (
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchAll} style={{ marginTop: 12 }}>
            {"重试"}
          </Button>
        </div>
      ) : (
        <div className={styles.contentStack}>
          <MemorySettingsCard
            memoryRecallBackendRaw={memoryRecallBackendRaw}
            retiredMemoryKeys={retiredMemoryKeys}
            ftsEnabled={
              (envValueMap.FTS_ENABLED ?? "true").toLowerCase() === "true"
            }
            memoryStoreBackend={envValueMap.MEMORY_STORE_BACKEND ?? "auto"}
            dirty={dirty}
            saving={saving}
            onFtsEnabledChange={handleManagedFtsEnabledChange}
            onMemoryStoreBackendChange={handleManagedBackendChange}
            onApplyRecommendedDefaults={handleApplyRecommendedMemoryDefaults}
            onSave={handleSave}
          />

          <div className={styles.tableCard}>
            <Toolbar
              workingRowsLength={visibleRowIndexes.length}
              allSelected={allSelected}
              someSelected={someSelected}
              selectedSize={selected.size}
              dirty={dirty}
              saving={saving}
              indeterminate={someSelected && !allSelected}
              onToggleSelectAll={toggleSelectAll}
              onRemoveSelected={removeSelected}
              onReset={handleReset}
              onSave={handleSave}
            />

            <div className={styles.rowList}>
              {visibleRowIndexes.map((idx) => (
                <EnvRow
                  key={idx}
                  row={workingRows[idx]}
                  idx={idx}
                  checked={selected.has(idx)}
                  error={keyErrors[idx]}
                  onToggle={toggleSelect}
                  onChange={updateRow}
                  onInsert={insertRowAfter}
                  onRemove={removeRow}
                />
              ))}

              {visibleRowIndexes.length === 0 && <EmptyState />}
            </div>

            <AddButton onClick={addRow} />
          </div>
        </div>
      )}
    </div>
  );
}

export default EnvironmentsPage;
