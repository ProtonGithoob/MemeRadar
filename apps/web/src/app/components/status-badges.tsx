import type { RealtimeStatus } from "../lib/realtime";

type SafetyTone = "safe" | "paper" | "disabled" | "advisory";
type RiskState = "PASS" | "WARN" | "BLOCK" | "UNKNOWN";
type FreshnessState = "FRESH" | "STALE" | "UNKNOWN" | "INVALID" | "CONFLICTED";

const riskDescriptions: Record<RiskState, string> = {
  PASS: "evidence acceptable",
  WARN: "review required",
  BLOCK: "blocked",
  UNKNOWN: "not safe"
};

const freshnessDescriptions: Record<FreshnessState, string> = {
  FRESH: "current",
  STALE: "not current",
  UNKNOWN: "not safe",
  INVALID: "invalid evidence",
  CONFLICTED: "provider disagreement"
};

function boundedReason(reason: string | undefined): string | undefined {
  if (!reason) return undefined;
  return reason.length > 96 ? `${reason.slice(0, 93)}...` : reason;
}

export function SafetyBadge({
  label,
  value,
  tone
}: {
  label: string;
  value: string;
  tone: SafetyTone;
}) {
  return (
    <span
      className={`status-badge status-badge--${tone}`}
      data-state={tone}
      role="status"
      aria-label={`${label}: ${value}`}
    >
      <span className="status-badge__label">{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

export function ScoreBadge({ value }: { value: number | null | undefined }) {
  const valid = typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
  if (!valid) {
    return (
      <span
        className="status-badge status-badge--unavailable"
        data-state="unavailable"
        role="status"
        aria-label="Score unavailable"
      >
        <span className="status-badge__label">ALPHA SCORE</span>
        <strong>SCORE UNAVAILABLE</strong>
      </span>
    );
  }

  const displayValue = Number.isInteger(value) ? String(value) : value.toFixed(1);
  const scoreState = value >= 70 ? "high" : value >= 40 ? "watch" : "low";
  return (
    <span
      className="status-badge status-badge--score"
      data-state={scoreState}
      role="status"
      aria-label={`Score: ${displayValue} out of 100`}
    >
      <span className="status-badge__label">ALPHA SCORE</span>
      <strong>SCORE {displayValue} / 100</strong>
    </span>
  );
}

export function RiskBadge({ value }: { value: RiskState }) {
  const state = value.toLowerCase();
  return (
    <span
      className={`status-badge status-badge--risk-${state}`}
      data-state={state}
      role="status"
      aria-label={`Risk: ${value} (${riskDescriptions[value]})`}
    >
      <span className="status-badge__label">RISK</span>
      <strong>{value}</strong>
    </span>
  );
}

export function FreshnessBadge({ value }: { value: FreshnessState }) {
  const state = value.toLowerCase();
  return (
    <span
      className={`status-badge status-badge--freshness-${state}`}
      data-state={state}
      role="status"
      aria-label={`Freshness: ${value} (${freshnessDescriptions[value]})`}
    >
      <span className="status-badge__label">EVIDENCE FRESHNESS</span>
      <strong>{value}</strong>
    </span>
  );
}

export function ConnectionBadge({ state, reason }: Pick<RealtimeStatus, "state" | "reason">) {
  const displayReason = boundedReason(reason);
  const stateValue = state.toLowerCase();
  return (
    <span
      className={`status-badge status-badge--connection-${stateValue}`}
      data-state={stateValue}
      role="status"
      aria-label={`Realtime stream: ${state}${displayReason ? ` — ${displayReason}` : ""}`}
    >
      <span className="status-badge__label">REALTIME</span>
      <strong>STREAM {state}</strong>
      {displayReason ? <small>{displayReason}</small> : null}
    </span>
  );
}
