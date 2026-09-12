import Link from "next/link";

import { SafetyBadge } from "./status-badges";
import type { ReadinessGateRecord, ReadinessRecord, ReadResult } from "../lib/read-api";

function tone(status: ReadinessGateRecord["status"]): "safe" | "paper" | "disabled" | "advisory" {
  if (status === "PASS") return "safe";
  if (status === "PARTIAL") return "paper";
  if (status === "BLOCKED_EXTERNAL" || status === "INSUFFICIENT_SAMPLES") return "advisory";
  return "disabled";
}

function failure(result: ReadResult<ReadinessRecord>): string {
  if (result.ok) return "";
  if (result.reason === "UNAUTHORIZED") return "READINESS AUTHORIZATION UNAVAILABLE";
  if (result.reason === "NOT_CONFIGURED") return "READINESS NOT CONFIGURED";
  if (result.reason === "INVALID_RESPONSE") return "INVALID READINESS RESPONSE";
  return "READINESS UNAVAILABLE";
}

function counts(gate: ReadinessGateRecord): string {
  const values = Object.entries(gate.evidenceCounts);
  return values.length === 0
    ? "NO EVIDENCE COUNTS"
    : values.map(([key, value]) => `${key.replaceAll("_", " ")}=${value}`).join(" · ");
}

function alphaTimestamp(value: string | null): string {
  return value === null ? "UNKNOWN" : new Date(value).toISOString();
}

function alphaCount(value: number | null): string {
  return value === null ? "UNKNOWN" : String(value);
}

export function ReadinessDashboard({ result }: { result: ReadResult<ReadinessRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">PRODUCTION READINESS / READ-ONLY</span>
        <strong>{failure(result)}</strong>
        <p>No readiness state was inferred from a failed read.</p>
        <Link href="/readiness">RETRY</Link>
      </div>
    );
  }
  const { data } = result;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">GATED RELEASE EVIDENCE</p>
          <h2>Operator readiness</h2>
        </div>
        <small>{data.classification} · AS OF {new Date(data.asOf).toISOString()}</small>
      </div>
      <section className="section-block intelligence-section" aria-labelledby="alpha-validation-title">
        <div className="section-heading">
          <div><p className="eyebrow">ALPHA VALIDATION / LIVE SHADOW</p><h3 id="alpha-validation-title">Alpha evidence readiness</h3></div>
          <SafetyBadge label="STATUS" value={data.alphaValidation.status} tone="advisory" />
        </div>
        <p>MadeOnSol evidence is research-only. Provider health does not validate alpha or authorize execution.</p>
        <div className="operations-summary">
          <div><span className="card-label">REAL OBSERVATIONS</span><strong>{data.alphaValidation.realObservationCount}</strong></div>
          <div><span className="card-label">UNIQUE ROBINHOOD TOKENS</span><strong>{data.alphaValidation.uniqueRobinhoodTokenCount}</strong></div>
          <div><span className="card-label">CALLER / KOL OBSERVATIONS</span><strong>{data.alphaValidation.callerKolObservationCount}</strong></div>
          <div><span className="card-label">SMART-WALLET OBSERVATIONS</span><strong>{data.alphaValidation.smartWalletObservationCount}</strong></div>
          <div><span className="card-label">DEPLOYER OBSERVATIONS</span><strong>{data.alphaValidation.deployerObservationCount}</strong></div>
          <div><span className="card-label">HOLDER / DISTRIBUTION OBSERVATIONS</span><strong>{data.alphaValidation.holderDistributionObservationCount}</strong></div>
          <div><span className="card-label">BUNDLE / LP / SECURITY OBSERVATIONS</span><strong>{data.alphaValidation.bundleLpSecurityObservationCount}</strong></div>
          <div><span className="card-label">LABELED WINNERS</span><strong>{alphaCount(data.alphaValidation.labeledWinnerCount)}</strong></div>
          <div><span className="card-label">LABELED RUGS / FAILURES</span><strong>{alphaCount(data.alphaValidation.labeledRugCount)}</strong></div>
          <div><span className="card-label">FIRST REAL OBSERVATION</span><strong>{alphaTimestamp(data.alphaValidation.firstRealObservation)}</strong></div>
          <div><span className="card-label">LATEST REAL OBSERVATION</span><strong>{alphaTimestamp(data.alphaValidation.latestRealObservation)}</strong></div>
          <div><span className="card-label">RATE LIMITS</span><strong>{alphaCount(data.alphaValidation.rateLimitCount)}</strong></div>
          <div><span className="card-label">PROVIDER ERRORS</span><strong>{alphaCount(data.alphaValidation.errorCount)}</strong></div>
        </div>
        <small>Reasons: {data.alphaValidation.reasonCodes.join(" · ") || "NONE RECORDED"}</small>
      </section>
      <section className="section-block intelligence-section" aria-labelledby="readiness-gates-title">
        <div className="section-heading">
          <div><p className="eyebrow">PR-1 THROUGH PR-7</p><h3 id="readiness-gates-title">Acceptance gates</h3></div>
          <Link href="/operations">OPEN OPERATIONS</Link>
        </div>
        <div className="wallet-list" aria-label="Production readiness gates">
          {data.gates.map((gate) => (
            <article className="detail-panel" key={gate.id}>
              <div className="section-heading">
                <div><span className="card-label">{gate.id}</span><h4>{gate.name}</h4></div>
                <SafetyBadge label="STATUS" value={gate.status} tone={tone(gate.status)} />
              </div>
              <div className="operations-summary">
                <div><span className="card-label">EVIDENCE COUNTS</span><strong>{counts(gate)}</strong></div>
                <div><span className="card-label">BLOCKERS</span><strong>{gate.blockers.join(" · ") || "NONE RECORDED"}</strong></div>
                <div><span className="card-label">NEXT ACTION</span><strong>{gate.nextAction}</strong></div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="operations-summary" aria-label="Readiness boundaries">
        <div className="detail-panel"><span className="card-label">HOSTED CI</span><strong>{String(data.hostedCi.status ?? "UNKNOWN")}</strong><small>{String(data.hostedCi.executed_steps ?? "UNKNOWN")} executed steps</small></div>
        <div className="detail-panel"><span className="card-label">PROVIDER / RUNTIME BLOCKERS</span><strong>{data.providerRuntimeBlockers.join(" · ") || "NONE RECORDED"}</strong></div>
        <div className="detail-panel"><span className="card-label">LIVE MONEY</span><strong>{String(data.liveMoney.status ?? "UNKNOWN")}</strong><small>Execution eligible: {data.liveMoney.execution_eligible === false ? "NO" : "UNKNOWN"}</small></div>
      </section>
      <section className="boundary-strip" aria-label="Protected readiness modes">
        <div><p className="eyebrow">PROTECTED MODES</p><h3>Readiness cannot loosen execution controls</h3><p>Analysis-only and paper-trading protections remain enforced by the backend.</p></div>
        <SafetyBadge label="MODES" value="LOCKED" tone="disabled" />
      </section>
    </>
  );
}
