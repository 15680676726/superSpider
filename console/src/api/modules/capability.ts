export type CapabilityMutationPhase =
  | "pending"
  | "risk-check"
  | "executing"
  | "waiting-confirm"
  | "completed"
  | "failed"
  | "cancelled";

export interface CapabilityMutationResponse {
  id?: string;
  enabled?: boolean;
  toggled?: boolean;
  deleted?: boolean;
  success?: boolean;
  error?: string | null;
  summary?: string;
  task_id?: string;
  phase?: CapabilityMutationPhase | string;
  decision_request_id?: string | null;
}

export function capabilityMutationRequiresConfirmation(
  result: CapabilityMutationResponse | null | undefined,
): boolean {
  return result?.phase === "waiting-confirm";
}
