import { Alert, Card, Descriptions, Space, Tag, Typography } from "antd";

import { runtimeStatusColor } from "../../runtime/tagSemantics";
import styles from "./index.module.less";
import {
  formatRuntimeSectionLabel,
  formatRuntimeStatus,
  formatMainBrainSignalLabel,
  localizeRuntimeText,
} from "./text";
import { isRecord } from "./runtimeDetailPrimitives";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
import type { RuntimeCockpitSignal } from "./runtimeIndustrySections";

const { Text } = Typography;

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function boolValue(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function textValue(value: unknown): string | null {
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized ? localizeRuntimeText(normalized) : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function signalRecordValue(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function firstTextValue(...values: unknown[]): string | null {
  for (const value of values) {
    const record = signalRecordValue(value);
    if (record) {
      const nested = firstTextValue(
        record.title,
        record.name,
        record.label,
        record.summary,
        record.value,
        record.count,
        record.total,
      );
      if (nested) {
        return nested;
      }
      continue;
    }
    const text = textValue(value);
    if (text) {
      return text;
    }
  }
  return null;
}

function detailText(value: unknown): string | null {
  const record = signalRecordValue(value);
  if (!record) {
    return null;
  }
  return firstTextValue(
    record.detail,
    record.note,
    record.summary,
    record.description,
    record.reason,
    record.status,
  );
}

function routeText(value: unknown): string | null {
  const record = signalRecordValue(value);
  if (!record) {
    return null;
  }
  return textValue(record.route);
}

function buildSignal(
  key: string,
  value: string,
  detail: string | null,
  route: string | null,
  tone?: RuntimeCockpitSignal["tone"],
  routeTitle?: string,
): RuntimeCockpitSignal {
  return {
    key,
    label: formatMainBrainSignalLabel(key),
    value,
    detail,
    route,
    routeTitle,
    tone,
  };
}

export function buildRuntimeEnvironmentCockpitSignals(
  payload: RuntimeCenterOverviewPayload | null,
): RuntimeCockpitSignal[] {
  const cards = new Map((payload?.cards ?? []).map((card) => [card.key, card]));
  const mainBrainCard = cards.get("main-brain") ?? null;
  const governanceCard = cards.get("governance") ?? null;
  const mainBrainMeta = signalRecordValue(mainBrainCard?.meta) ?? {};
  const governanceMeta = signalRecordValue(governanceCard?.meta) ?? {};
  const governanceEntry = governanceCard?.entries?.[0] ?? null;
  const surface = payload?.surface ?? null;

  const carrierSource = mainBrainMeta.carrier ?? surface?.status ?? "unavailable";
  const environmentSource =
    mainBrainMeta.environment ?? governanceMeta.host_twin_summary ?? governanceCard?.summary;

  const carrierRoute = routeText(carrierSource) || textValue(governanceEntry?.route);
  const environmentRoute = routeText(environmentSource) || textValue(governanceEntry?.route);

  const carrierTone =
    surface?.status === "state-service"
      ? "success"
      : surface?.status === "degraded"
        ? "warning"
        : "default";

  return [
    buildSignal(
      "carrier",
      firstTextValue(carrierSource) || formatRuntimeStatus(surface?.status ?? "unavailable"),
      detailText(carrierSource) ||
        firstTextValue(surface?.source, surface?.note, surface?.services?.join(" / ")),
      carrierRoute || governanceEntry?.route || null,
      carrierTone,
      "Carrier detail",
    ),
    buildSignal(
      "environment",
      firstTextValue(environmentSource) ||
        firstTextValue(governanceCard?.summary) ||
        "Environment ready",
      detailText(environmentSource) ||
        summarizeHostTwin(governanceMeta.host_twin_summary) ||
        firstTextValue(surface?.note),
      environmentRoute || governanceEntry?.route || null,
      governanceCard?.status === "state-service"
        ? "success"
        : governanceCard?.status === "degraded"
          ? "warning"
          : "default",
      "Environment detail",
    ),
  ];
}

function summarizeHostTwin(value: unknown): string | null {
  const record = signalRecordValue(value);
  if (!record) {
    return null;
  }
  return firstTextValue(
    record.recommended_scheduler_action,
    record.selected_seat_ref,
    record.seat_selection_policy,
    record.active_app_family_count,
    record.contention_severity,
    record.blocked_surface_count,
  );
}

export function renderHostTwinSection(
  sectionKey: string,
  hostTwin: Record<string, unknown>,
) {
  const ownership = recordValue(hostTwin.ownership) || {};
  const continuity = recordValue(hostTwin.continuity) || {};
  const legalRecovery = recordValue(hostTwin.legal_recovery) || {};
  const coordination = recordValue(hostTwin.coordination) || {};
  const surfaceMutability = recordValue(hostTwin.surface_mutability) || {};
  const latestBlockingEvent = recordValue(hostTwin.latest_blocking_event);
  const executionMutationReady = recordValue(hostTwin.execution_mutation_ready) || {};
  const appFamilyTwins = recordValue(hostTwin.app_family_twins) || {};
  const trustedAnchors = Array.isArray(hostTwin.trusted_anchors)
    ? hostTwin.trusted_anchors.filter(isRecord)
    : [];
  const blockedSurfaces = Array.isArray(hostTwin.blocked_surfaces)
    ? hostTwin.blocked_surfaces.filter(isRecord)
    : [];
  const blockerFamilies = stringList(hostTwin.active_blocker_families);
  const activeFamilies = Object.entries(appFamilyTwins).filter(([, value]) => {
    const record = recordValue(value);
    return record?.active === true;
  });
  const surfaceMutabilityEntries = Object.entries(surfaceMutability).filter(([, value]) =>
    recordValue(value),
  );
  const mutationReadyEntries = Object.entries(executionMutationReady).filter(
    ([, value]) => typeof value === "boolean",
  ) as Array<[string, boolean]>;
  const summaryRows = [
    ["Handoff owner", stringValue(ownership.handoff_owner_ref)],
    ["Account scope", stringValue(ownership.account_scope_ref)],
    ["Workspace scope", stringValue(ownership.workspace_scope)],
    ["Owner mode", stringValue(ownership.active_owner_kind)],
    ["Seat owner", stringValue(coordination.seat_owner_ref)],
    ["Workspace owner", stringValue(coordination.workspace_owner_ref)],
    ["Writer owner", stringValue(coordination.writer_owner_ref)],
    ["Selected seat", stringValue(coordination.selected_seat_ref)],
    ["Seat policy", stringValue(coordination.seat_selection_policy)],
    ["Scheduler action", stringValue(coordination.recommended_scheduler_action)],
    ["Recovery path", stringValue(legalRecovery.path)],
    ["Resume kind", stringValue(continuity.resume_kind)],
    ["Recovery checkpoint", stringValue(legalRecovery.checkpoint_ref)],
    ["Verification", stringValue(legalRecovery.verification_channel)],
  ].filter(([, value]) => value) as Array<[string, string]>;
  const contentionForecast = recordValue(coordination.contention_forecast);

  return (
    <section key={sectionKey} className={styles.detailSection}>
      <div className={styles.detailSectionTitle}>{formatRuntimeSectionLabel(sectionKey)}</div>
      <Card size="small">
        <Space wrap size={[6, 6]} style={{ marginBottom: 12 }}>
          {stringValue(continuity.status) ? (
            <Tag color={runtimeStatusColor(stringValue(continuity.status) || "unknown")}>
              {`Continuity ${formatRuntimeStatus(stringValue(continuity.status) || "unknown")}`}
            </Tag>
          ) : null}
          {stringValue(coordination.recommended_scheduler_action) ? (
            <Tag color="warning">
              {`Scheduler ${stringValue(coordination.recommended_scheduler_action)}`}
            </Tag>
          ) : null}
          {activeFamilies.length > 0 ? (
            <Tag color="blue">{`Active families ${activeFamilies.length}`}</Tag>
          ) : null}
          {blockedSurfaces.length > 0 ? (
            <Tag color="error">{`Blocked surfaces ${blockedSurfaces.length}`}</Tag>
          ) : null}
          {blockerFamilies.map((family) => (
            <Tag key={family} color="error">
              {family}
            </Tag>
          ))}
        </Space>

        {boolValue(continuity.requires_human_return) ? (
          <Alert
            showIcon
            type="warning"
            message="Human return required"
            description={
              stringValue(legalRecovery.return_condition) ||
              "The current host twin requires a human handoff before mutation can continue."
            }
            style={{ marginBottom: 12 }}
          />
        ) : null}

        {summaryRows.length > 0 ? (
          <Descriptions
            size="small"
            column={1}
            bordered
            items={summaryRows.map(([label, value]) => ({
              key: `${sectionKey}:${label}`,
              label,
              children: value,
            }))}
          />
        ) : null}

        {contentionForecast ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Coordination</div>
            <Text type="secondary">
              {[
                stringValue(contentionForecast.severity),
                stringValue(contentionForecast.reason),
              ]
                .filter(Boolean)
                .join(" · ")}
            </Text>
          </div>
        ) : null}

        {latestBlockingEvent ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Blocking Event</div>
            <Text type="secondary">
              {[
                stringValue(latestBlockingEvent.event_family),
                stringValue(latestBlockingEvent.event_name),
                stringValue(latestBlockingEvent.recommended_runtime_response),
              ]
                .filter(Boolean)
                .join(" · ")}
            </Text>
          </div>
        ) : null}

        {mutationReadyEntries.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Mutation Readiness</div>
            <Space wrap size={[6, 6]}>
              {mutationReadyEntries.map(([surfaceKey, ready]) => (
                <Tag key={`${sectionKey}:mutation:${surfaceKey}`} color={ready ? "success" : "error"}>
                  {`${surfaceKey} ${ready ? "ready" : "blocked"}`}
                </Tag>
              ))}
            </Space>
          </div>
        ) : null}

        {activeFamilies.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>App Family Twins</div>
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              {activeFamilies.map(([familyKey, value]) => {
                const family = recordValue(value) || {};
                return (
                  <Card key={familyKey} size="small">
                    <Space wrap size={[6, 6]} style={{ marginBottom: 6 }}>
                      <Tag color="processing">{familyKey}</Tag>
                      {stringValue(family.contract_status) ? (
                        <Tag>{stringValue(family.contract_status)}</Tag>
                      ) : null}
                    </Space>
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      {stringValue(family.surface_ref) ? (
                        <Text type="secondary">{stringValue(family.surface_ref)}</Text>
                      ) : null}
                      {stringValue(family.family_scope_ref) ? (
                        <Text type="secondary">{stringValue(family.family_scope_ref)}</Text>
                      ) : null}
                      {stringValue(family.writer_lock_scope) ? (
                        <Text type="secondary">{stringValue(family.writer_lock_scope)}</Text>
                      ) : null}
                    </Space>
                  </Card>
                );
              })}
            </Space>
          </div>
        ) : null}

        {surfaceMutabilityEntries.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Surface Mutability</div>
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {surfaceMutabilityEntries.map(([surfaceKey, value]) => {
                const surface = recordValue(value) || {};
                return (
                  <Text key={`${sectionKey}:surface:${surfaceKey}`} type="secondary">
                    {[
                      surfaceKey,
                      stringValue(surface.surface_ref),
                      stringValue(surface.mutability),
                      stringValue(surface.blocker_family),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </Text>
                );
              })}
            </Space>
          </div>
        ) : null}

        {trustedAnchors.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Trusted Anchors</div>
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {trustedAnchors.map((anchor, index) => (
                <Space
                  key={`${sectionKey}:anchor:${index}`}
                  direction="vertical"
                  size={0}
                  style={{ width: "100%" }}
                >
                  {stringValue(anchor.anchor_kind) ? (
                    <Text type="secondary">{stringValue(anchor.anchor_kind)}</Text>
                  ) : null}
                  {stringValue(anchor.anchor_ref) ? (
                    <Text type="secondary">{stringValue(anchor.anchor_ref)}</Text>
                  ) : null}
                  {stringValue(anchor.surface_ref) ? (
                    <Text type="secondary">{stringValue(anchor.surface_ref)}</Text>
                  ) : null}
                </Space>
              ))}
            </Space>
          </div>
        ) : null}

        {blockedSurfaces.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <div className={styles.detailSectionTitle}>Blocked Surfaces</div>
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              {blockedSurfaces.map((item, index) => (
                <Text key={`${sectionKey}:blocked:${index}`} type="secondary">
                  {[
                    stringValue(item.surface_kind),
                    stringValue(item.surface_ref),
                    stringValue(item.reason),
                    stringValue(item.event_family),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </Text>
              ))}
            </Space>
          </div>
        ) : null}
      </Card>
    </section>
  );
}
