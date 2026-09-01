import Link from "next/link";

import { OperatorHeader } from "./operator-header";
import { ProtectedShell } from "./radar";
import { SafetyBadge } from "./status-badges";
import type {
  OperationalProviderRecord,
  OperationsRecord,
  ReadResult
} from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function stateTone(state: OperationsRecord["overallState"]): "safe" | "paper" | "disabled" | "advisory" {
  if (state === "HEALTHY") return "safe";
  if (state === "DEGRADED") return "advisory";
  return "disabled";
}

function quotaSummary(provider: OperationalProviderRecord): string {
  if (provider.quotaRemaining !== null && provider.quotaLimit !== null) {
    return `${provider.quotaRemaining} remaining / ${provider.quotaLimit} limit`;
  }
  return "QUOTA UNKNOWN";
}

function costSummary(provider: OperationalProviderRecord): string {
  if (provider.costTodayUsd !== null && provider.costBudgetUsd !== null) {
    return `$${provider.costTodayUsd.toFixed(2)} / $${provider.costBudgetUsd.toFixed(2)} budget`;
  }
  return "COST UNKNOWN";
}

function counterValue(metrics: Record<string, unknown>, name: string): number {
  const counters = metrics.counters;
  if (typeof counters !== "object" || counters === null || Array.isArray(counters)) return 0;
  const value = (counters as Record<string, unknown>)[name];
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

function failureMessage(result: ReadResult<OperationsRecord>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED": return "OPERATIONS OBSERVABILITY NOT CONFIGURED";
    case "UNAUTHORIZED": return "OPERATIONS OBSERVABILITY AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID OPERATIONS READ RESPONSE";
    case "UNAVAILABLE": return "OPERATIONS OBSERVABILITY UNAVAILABLE";
  }
}

function ProviderOperationRow({ provider }: { provider: OperationalProviderRecord }) {
  return (
    <article className={`operations-provider operations-provider--${provider.state.toLowerCase()}`}>
      <div>
        <strong>{provider.provider}</strong>
        <span>{provider.capability}</span>
        <small>CHECKED {readableDate(provider.checkedAt)}</small>
      </div>
      <div>
        <span className="card-label">STATE / SLO</span>
        <strong>{provider.state} / {provider.sloState}</strong>
        <small>{provider.reasonCodes.length > 0 ? provider.reasonCodes.join(", ") : "NO DEGRADATION REASON"}</small>
      </div>
      <div>
        <span className="card-label">QUOTA</span>
        <strong>{quotaSummary(provider)}</strong>
        <small>{provider.latencyMs === null ? "LATENCY UNKNOWN" : `${provider.latencyMs.toFixed(0)} ms latest`}</small>
        <small>{costSummary(provider)}</small>
      </div>
    </article>
  );
}

function OperationsContent({ result }: { result: ReadResult<OperationsRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">OPERATIONS / READ-ONLY</span>
        <strong>{failureMessage(result)}</strong>
        <p>No operational health was inferred from the failed read.</p>
        <Link href="/operations">RETRY</Link>
      </div>
    );
  }

  const { data } = result;
  return (
    <>
      <div className="operations-summary" aria-label="Operations summary">
        <div className="detail-panel">
          <span className="card-label">OVERALL STATE</span>
          <SafetyBadge label="OPERATIONS" value={data.overallState} tone={stateTone(data.overallState)} />
          <small>AS OF {readableDate(data.asOf)}</small>
        </div>
        <div className="detail-panel">
          <span className="card-label">PROVIDER SLO EVIDENCE</span>
          <SafetyBadge
            label="SLO"
            value={data.sloState}
            tone={data.sloState === "MEASURED" ? "paper" : "disabled"}
          />
          <small>{data.measurementMethod} / {data.policyVersion}</small>
        </div>
        <div className="detail-panel">
          <span className="card-label">ACTIVE ALERTS</span>
          <strong className="operations-big-value">{data.alerts.length}</strong>
          <small>Operational alerts are evidence quality, never trade signals.</small>
        </div>
      </div>

      <section className="section-block" aria-labelledby="operations-providers-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PROVIDER / QUOTA / LATENCY</p>
            <h3 id="operations-providers-title">Provider operations</h3>
          </div>
          <p className="section-note">Synthetic or missing measurements remain unverified.</p>
        </div>
        {data.providers.length === 0 ? (
          <div className="read-state" role="status">
            <strong>NO OPERATIONAL PROVIDER EVIDENCE</strong>
            <p>Empty is not healthy; configure a read-only provider health projection.</p>
          </div>
        ) : (
          <div className="operations-provider-list">
            {data.providers.map((provider) => (
              <ProviderOperationRow key={`${provider.provider}:${provider.capability}`} provider={provider} />
            ))}
          </div>
        )}
      </section>

      <section className="section-block" aria-labelledby="operations-alerts-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">DEGRADATION / BACKPRESSURE / RECOVERY</p>
            <h3 id="operations-alerts-title">Active operational alerts</h3>
          </div>
        </div>
        {data.alerts.length === 0 ? (
          <div className="read-state" role="status">
            <strong>NO ACTIVE OPERATIONAL ALERTS</strong>
            <p>Healthy telemetry is neutral and does not increase AlphaScore.</p>
          </div>
        ) : (
          <div className="operations-alert-list">
            {data.alerts.map((alert) => (
              <article className={`operations-alert operations-alert--${alert.severity.toLowerCase()}`} key={alert.dedupeKey}>
                <div>
                  <strong>{alert.code}</strong>
                  <span>{alert.provider ?? "SYSTEM"}{alert.capability ? ` / ${alert.capability}` : ""}</span>
                </div>
                <div>
                  <span className="card-label">{alert.severity}</span>
                  <p>{alert.message}</p>
                  <small>{alert.reasonCodes.join(", ") || "NO REASON CODE"}</small>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="section-block" aria-labelledby="operations-metrics-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">BOUNDED TELEMETRY</p>
            <h3 id="operations-metrics-title">Reliability counters</h3>
          </div>
        </div>
        <div className="operations-counter-grid">
          {[
            ["QUEUE SATURATION", "queue_saturations"],
            ["OUTBOX DEAD LETTERS", "outbox_dead_letters"],
            ["RECOVERY FAILURES", "recovery_failures"],
            ["STREAM RECONNECTS", "stream_reconnects"]
          ].map(([label, name]) => (
            <div className="detail-panel" key={name}>
              <span className="card-label">{label}</span>
              <strong className="operations-big-value">{counterValue(data.metrics, name)}</strong>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

export function OperationsDashboard({ result }: { result: ReadResult<OperationsRecord> }) {
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <section className="section-block intelligence-section" aria-labelledby="operations-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">OBSERVABILITY / OPERATIONS / READ-ONLY</p>
            <h3 id="operations-title">Operations</h3>
          </div>
          <p className="section-note">Operational health is evidence quality, never a positive trade signal.</p>
        </div>
        <OperationsContent result={result} />
      </section>
      <section className="queue-card" aria-labelledby="operations-boundary-title">
        <div className="queue-card__icon" aria-hidden="true">⌁</div>
        <div>
          <p className="eyebrow">PROTECTED MODES</p>
          <h3 id="operations-boundary-title">Analysis-only operations</h3>
          <p>Provider degradation, queue pressure and alert failures stay visible without changing score or execution state.</p>
        </div>
        <SafetyBadge label="MODE" value="ANALYSIS ONLY" tone="safe" />
      </section>
    </main>
  );
}
