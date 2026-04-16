import type {
  IndustryStaffingGap,
  IndustryStaffingState,
  IndustryTemporarySeat,
} from "../api/modules/industry";
import {
  presentEmploymentModeLabel,
  presentRuntimeStatusLabel,
} from "./executionPresentation";

export interface StaffingPresentationCard {
  title: string;
  detail: string;
  badges: string[];
  meta: string[];
}

export interface StaffingPresentation {
  activeGap: StaffingPresentationCard | null;
  pendingProposals: string[];
  temporarySeats: string[];
  researcher:
    | {
        headline: string;
        detail: string;
        badges: string[];
      }
    | null;
  hasAnyState: boolean;
}

type SeatLifecycleParams = {
  staffing?: IndustryStaffingState | null;
  agentId?: string | null;
  employmentMode?: string | null;
};

function nonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function presentResearcherLabel(value: string | null | undefined): string {
  const label = nonEmpty(value);
  if (!label || label === "Researcher") {
    return "研究位";
  }
  return label;
}

function describeGap(gap: IndustryStaffingGap): StaffingPresentationCard {
  const roleName =
    nonEmpty(gap.target_role_name) ||
    nonEmpty(gap.target_role_id) ||
    "Unassigned seat";
  const kind = nonEmpty(gap.kind) || "routing-pending";
  const detail =
    nonEmpty(gap.reason) ||
    nonEmpty(gap.summary) ||
    nonEmpty(gap.title) ||
    "The main brain surfaced a staffing gap for this execution path.";
  const badges = [kind];
  if (gap.requires_confirmation) {
    badges.push("Needs approval");
  }
  if (nonEmpty(gap.proposal_status)) {
    badges.push(nonEmpty(gap.proposal_status)!);
  }
  const meta = [
    ...(gap.requested_surfaces || []),
    ...(nonEmpty(gap.decision_request_id) ? [gap.decision_request_id!] : []),
    ...(nonEmpty(gap.status) ? [presentRuntimeStatusLabel(gap.status)] : []),
  ];
  return {
    title: roleName,
    detail,
    badges,
    meta,
  };
}

function describeTemporarySeat(seat: IndustryTemporarySeat): string {
  const title = nonEmpty(seat.role_name) || nonEmpty(seat.role_id) || "Temporary seat";
  const parts = [
    title,
    presentRuntimeStatusLabel(seat.status),
    nonEmpty(seat.current_assignment?.title),
    "auto-retire",
  ].filter(Boolean);
  return parts.join(" | ");
}

export function buildStaffingPresentation(
  staffing?: IndustryStaffingState | null,
): StaffingPresentation {
  const activeGap = staffing?.active_gap ? describeGap(staffing.active_gap) : null;
  const pendingProposals = (staffing?.pending_proposals || []).map((proposal) => {
    const roleName =
      nonEmpty(proposal.target_role_name) ||
      nonEmpty(proposal.target_role_id) ||
      "Seat proposal";
    const decision = nonEmpty(proposal.decision_request_id);
    const status = nonEmpty(proposal.status)
      ? presentRuntimeStatusLabel(proposal.status)
      : null;
    return [roleName, decision, status].filter(Boolean).join(" | ");
  });
  const temporarySeats = (staffing?.temporary_seats || []).map(describeTemporarySeat);
  const researcher = staffing?.researcher
    ? {
        headline: [
          presentResearcherLabel(staffing.researcher.role_name),
          presentRuntimeStatusLabel(staffing.researcher.status),
        ].join(" | "),
        detail: [
          nonEmpty(staffing.researcher.current_assignment?.title),
          typeof staffing.researcher.pending_signal_count === "number"
            ? `待主脑处理研究汇报 ${staffing.researcher.pending_signal_count}`
            : null,
          nonEmpty(staffing.researcher.latest_report?.headline),
        ]
          .filter(Boolean)
          .join(" | "),
        badges: [
          ...(staffing.researcher.waiting_for_main_brain ? ["待主脑处理"] : []),
        ],
      }
    : null;
  return {
    activeGap,
    pendingProposals,
    temporarySeats,
    researcher,
    hasAnyState: Boolean(
      activeGap || pendingProposals.length || temporarySeats.length || researcher,
    ),
  };
}

export function presentSeatLifecycleState({
  staffing,
  agentId,
  employmentMode,
}: SeatLifecycleParams): string {
  const normalizedAgentId = nonEmpty(agentId);
  const hasTargetedCareerProposal = Boolean(
    normalizedAgentId &&
      (staffing?.pending_proposals || []).some(
        (proposal) =>
          nonEmpty(proposal.target_agent_id) === normalizedAgentId &&
          nonEmpty(proposal.kind) === "career-seat-proposal",
      ),
  );
  if (hasTargetedCareerProposal && employmentMode === "temporary") {
    return "Pending promotion";
  }
  if (
    normalizedAgentId &&
    (staffing?.pending_proposals || []).some(
      (proposal) => nonEmpty(proposal.target_agent_id) === normalizedAgentId,
    )
  ) {
    return "Pending approval";
  }
  if (
    normalizedAgentId &&
    (staffing?.active_gap?.requires_confirmation ?? false) &&
    nonEmpty(staffing?.active_gap?.target_agent_id) === normalizedAgentId
  ) {
    return "Pending approval";
  }
  if (
    normalizedAgentId &&
    (staffing?.temporary_seats || []).some(
      (seat) => nonEmpty(seat.agent_id) === normalizedAgentId,
    )
  ) {
    return "Temporary seat";
  }
  if (employmentMode === "temporary") {
    return "Temporary seat";
  }
  return "Permanent seat";
}

export function presentSeatModeLabel(mode?: string | null): string {
  return presentEmploymentModeLabel(mode || "career");
}
