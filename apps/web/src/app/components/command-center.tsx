import Link from "next/link";

import type {
  CandidateRecord,
  EarlyRadarRecord,
  OperationsRecord,
  ReadPage,
  ReadResult
} from "../lib/read-api";
import { joinRadarRows, readFailureMessage } from "./radar";
import { RadarTable } from "./radar-table";

const FUNNEL_STATES = ["WATCH", "EARLY_WATCH", "STRONG_SETUP", "HIGH_CONFLUENCE", "ENTRY_READY"] as const;

function MetricCard({
  label,
  value,
  tone,
  detail
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "danger" | "disabled";
  detail?: string;
}) {
  return (
    <div className="metric-card">
      <span className="metric-card__label">{label}</span>
      <strong className={`metric-card__value${tone ? ` metric-card__value--${tone}` : ""}`}>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function StatusStrip({ operations }: { operations: ReadResult<OperationsRecord> }) {
  if (!operations.ok) {
    return (
      <div className="metric-strip" aria-label="System status">
        <MetricCard label="STACK" tone="warn" value="UNKNOWN" detail={readFailureMessage(operations, "OPERATIONS UNAVAILABLE")} />
        <MetricCard label="PROVIDERS" tone="warn" value="UNKNOWN" />
        <MetricCard label="ALERTS" value="UNKNOWN" />
        <MetricCard label="SLO" tone="warn" value="UNVERIFIED" />
      </div>
    );
  }
  const data = operations.data;
  const down = data.providers.filter((provider) => provider.state === "DOWN").length;
  const degraded = data.providers.filter((provider) => provider.state === "DEGRADED").length;
  const criticalAlerts = data.alerts.filter((alert) => alert.severity === "CRITICAL").length;
  return (
    <div className="metric-strip" aria-label="System status">
      <MetricCard
        label="STACK"
        tone={data.overallState === "HEALTHY" ? "ok" : data.overallState === "DEGRADED" ? "warn" : "danger"}
        value={data.overallState}
        detail={`as of ${data.asOf}`}
      />
      <MetricCard
        label="PROVIDERS"
        tone={down > 0 ? "danger" : degraded > 0 ? "warn" : "ok"}
        value={down > 0 ? `${down} DOWN` : degraded > 0 ? `${degraded} DEGRADED` : "READY"}
        detail={`${data.providers.length} tracked`}
      />
      <MetricCard
        label="ACTIVE ALERTS"
        tone={criticalAlerts > 0 ? "danger" : data.alerts.length > 0 ? "warn" : "ok"}
        value={String(data.alerts.length)}
        detail={criticalAlerts > 0 ? `${criticalAlerts} critical` : "no critical"}
      />
      <MetricCard label="SLO" tone={data.sloState === "VIOLATED" ? "danger" : "warn"} value={data.sloState} detail={data.measurementMethod} />
    </div>
  );
}

function Funnel({ earlyResult }: { earlyResult: ReadResult<ReadPage<EarlyRadarRecord>> }) {
  if (!earlyResult.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{readFailureMessage(earlyResult, "EARLY RADAR UNAVAILABLE")}</strong>
        <p>Funnel counts were not substituted.</p>
      </div>
    );
  }
  const counts = new Map<string, number>();
  for (const item of earlyResult.data.items) {
    counts.set(item.earlyState, (counts.get(item.earlyState) ?? 0) + 1);
  }
  return (
    <div aria-label="Early alpha funnel" className="cc-funnel">
      {FUNNEL_STATES.map((state) => {
        const count = counts.get(state) ?? 0;
        const hot = state === "ENTRY_READY" || state === "HIGH_CONFLUENCE";
        return (
          <div className={hot && count > 0 ? "cc-funnel__step cc-funnel__step--hot" : "cc-funnel__step"} key={state}>
            <strong>{count}</strong>
            <span>{state}</span>
          </div>
        );
      })}
    </div>
  );
}

function AlertsRail({ operations }: { operations: ReadResult<OperationsRecord> }) {
  if (!operations.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{readFailureMessage(operations, "OPERATIONS UNAVAILABLE")}</strong>
        <p>Operational alerts are unavailable; nothing was fabricated.</p>
      </div>
    );
  }
  if (operations.data.alerts.length === 0) {
    return (
      <div className="read-state" role="status">
        <strong>NO ACTIVE OPERATIONAL ALERTS</strong>
        <p>The operations projection reported no degradation alerts.</p>
      </div>
    );
  }
  return (
    <div className="cc-alerts" aria-label="Active operational alerts">
      {operations.data.alerts.map((alert) => (
        <div className={`cc-alert cc-alert--${alert.severity.toLowerCase()}`} key={alert.dedupeKey}>
          <strong>{alert.severity}</strong>
          <span>{alert.message}</span>
          <small>{alert.provider ?? alert.code}</small>
        </div>
      ))}
    </div>
  );
}

export function CommandCenter({
  result,
  earlyResult,
  operations
}: {
  result: ReadResult<ReadPage<CandidateRecord>>;
  earlyResult: ReadResult<ReadPage<EarlyRadarRecord>>;
  operations: ReadResult<OperationsRecord>;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evidence-first / analysis-only / paper trading</p>
          <h2>Overview</h2>
        </div>
        <small>All surfaces are read-only; no browser execution authority exists.</small>
      </div>

      <StatusStrip operations={operations} />

      <section className="section-block" aria-labelledby="funnel-title">
        <div className="section-heading">
          <h3 id="funnel-title">Early alpha funnel</h3>
          <p className="section-note">Counts reflect the latest bounded early-radar page.</p>
        </div>
        <Funnel earlyResult={earlyResult} />
      </section>

      <section className="section-block" aria-labelledby="live-radar-title">
        <div className="section-heading">
          <h3 id="live-radar-title">Live radar</h3>
          <p className="section-note">
            <Link href="/radar">OPEN FULL RADAR</Link>
          </p>
        </div>
        <RadarSummary earlyResult={earlyResult} result={result} />
      </section>

      <section className="section-block" aria-labelledby="alerts-title">
        <div className="section-heading">
          <h3 id="alerts-title">Alerts &amp; changes</h3>
          <p className="section-note"><Link href="/operations">OPEN OPERATIONS</Link></p>
        </div>
        <AlertsRail operations={operations} />
      </section>

      <div className="boundary-strip" role="note">
        <strong>NO LIVE ORDERS</strong>
        <span>Advisory output only. Read data, provider labels and narratives cannot authorize an order.</span>
      </div>
    </>
  );
}

function RadarSummary({
  result,
  earlyResult
}: {
  result: ReadResult<ReadPage<CandidateRecord>>;
  earlyResult: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{readFailureMessage(result)}</strong>
        <p>No candidate data was substituted. Retry after the read dependency is available.</p>
        <Link href="/radar">OPEN RADAR</Link>
      </div>
    );
  }
  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <strong>NO CANDIDATES MATCH FILTERS</strong>
        <p>The read API returned an empty ranked page. No sample candidate is shown.</p>
      </div>
    );
  }
  const earlyItems = earlyResult.ok ? earlyResult.data.items : [];
  return <RadarTable rows={joinRadarRows(result.data.items, earlyItems)} />;
}
