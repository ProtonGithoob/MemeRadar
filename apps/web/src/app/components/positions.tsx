import Link from "next/link";

import { OperatorHeader } from "./operator-header";
import { ProtectedShell } from "./radar";
import { FreshnessBadge, SafetyBadge } from "./status-badges";
import type {
  PositionRecord,
  ReadFailureReason,
  ReadPage,
  ReadResult
} from "../lib/read-api";

function readableDate(value: string | null): string {
  if (value === null) return "UNKNOWN TIME";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function number(value: number | null, digits = 2): string {
  return value === null || !Number.isFinite(value) ? "UNKNOWN" : value.toFixed(digits);
}

function signed(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "UNKNOWN";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function shortIdentity(value: string, visible = 9): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function failureMessage(reason: ReadFailureReason): string {
  switch (reason) {
    case "NOT_CONFIGURED": return "POSITION READ API NOT CONFIGURED";
    case "UNAUTHORIZED": return "POSITION READ AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID POSITION READ RESPONSE";
    case "UNAVAILABLE": return "POSITION DATA UNAVAILABLE";
  }
}

function PositionMark({ position }: { position: PositionRecord }) {
  const mark = position.currentMark;
  return (
    <div className="position-panel position-panel--mark">
      <div className="panel-heading">
        <div><span className="card-label">OBSERVED MARK</span><h4>{mark ? number(mark.price, 6) : "UNKNOWN"}</h4></div>
        <FreshnessBadge value={mark?.qualityState ?? "UNKNOWN"} />
      </div>
      {mark ? (
        <dl className="position-meta">
          <div><dt>PROVIDER</dt><dd>{mark.provider}</dd></div>
          <div><dt>SOURCE</dt><dd title={mark.sourceId}>{shortIdentity(mark.sourceId, 14)}</dd></div>
          <div><dt>OBSERVED</dt><dd>{readableDate(mark.observedAt)}</dd></div>
          <div><dt>PARSER</dt><dd>{mark.parserVersion}</dd></div>
        </dl>
      ) : <p className="muted-copy">No market mark was returned. Current value and unrealized PnL remain UNKNOWN.</p>}
    </div>
  );
}

function PositionPerformance({ position }: { position: PositionRecord }) {
  const performance = position.performance;
  return (
    <div className="position-panel">
      <div className="panel-heading">
        <div><span className="card-label">DERIVED PERFORMANCE</span><h4>{signed(performance.totalPnl)} QUOTE PNL</h4></div>
        <small>AS OF {readableDate(performance.asOf)}</small>
      </div>
      <div className="position-metric-grid">
        <div><span>UNREALIZED</span><strong>{signed(performance.unrealizedPnl)}</strong></div>
        <div><span>REALIZED</span><strong>{signed(performance.realizedPnl)}</strong></div>
        <div><span>RETURN</span><strong>{performance.returnRatio === null ? "UNKNOWN" : `${signed(performance.returnRatio * 100)}%`}</strong></div>
        <div><span>MFE / MAE</span><strong>{signed(performance.mfe)} / {signed(performance.mae)}</strong></div>
      </div>
      <FreshnessBadge value={performance.qualityState} />
    </div>
  );
}

function ExitRisk({ position }: { position: PositionRecord }) {
  const risk = position.exitRisk;
  if (risk === null) {
    return <div className="position-panel"><span className="card-label">EXIT RISK</span><p className="muted-copy">No exit evaluation is available.</p></div>;
  }
  return (
    <div className="position-panel position-panel--risk">
      <div className="panel-heading">
        <div><span className="card-label">ADVISORY EXIT RISK</span><h4>{risk.action} / {Math.round(risk.exitFraction * 100)}%</h4></div>
        <FreshnessBadge value={risk.qualityState} />
      </div>
      <div className="position-metric-grid">
        <div><span>RISK SCORE</span><strong>{number(risk.score)}</strong></div>
        <div><span>CONFIDENCE</span><strong>{Math.round(risk.confidence * 100)}%</strong></div>
        <div><span>EVALUATED</span><strong>{readableDate(risk.evaluatedAt)}</strong></div>
        <div><span>RULES</span><strong>{risk.triggeredRules.length ? risk.triggeredRules.join(", ") : "NONE"}</strong></div>
      </div>
      <p className="position-reasons"><span>REASONS</span> {risk.reasonCodes.length ? risk.reasonCodes.join(", ") : "UNKNOWN"}</p>
      <p className="position-reasons"><span>EVIDENCE</span> {risk.evidenceRefs.length ? risk.evidenceRefs.join(", ") : "UNKNOWN"}</p>
    </div>
  );
}

function ClosedTrade({ position }: { position: PositionRecord }) {
  const trade = position.closedTrade;
  if (trade === null) return null;
  return (
    <div className="position-panel position-panel--closed" aria-label="Closed trade explanation">
      <div className="panel-heading">
        <div><span className="card-label">CLOSED TRADE EXPLANATION</span><h4>{trade.action} at {number(trade.averageExit, 6)}</h4></div>
        <small>{readableDate(trade.closedAt)}</small>
      </div>
      <p className="position-reasons"><span>REALIZED PNL</span> {signed(trade.realizedPnl)}</p>
      <p className="position-reasons"><span>REASONS</span> {trade.reasonCodes.join(", ")}</p>
      <p className="position-reasons"><span>BEFORE</span> {trade.beforeEvidenceRefs.length ? trade.beforeEvidenceRefs.join(", ") : "NONE"}</p>
      <p className="position-reasons"><span>AFTER</span> {trade.afterEvidenceRefs.length ? trade.afterEvidenceRefs.join(", ") : trade.evidenceRefs.join(", ")}</p>
    </div>
  );
}

function PositionCard({ position }: { position: PositionRecord }) {
  const displayName = position.symbol || position.name || "UNNAMED POSITION";
  return (
    <article className={`position-card position-card--${position.state.toLowerCase()}`}>
      <div className="position-card__heading">
        <div>
          <h4>{displayName}</h4>
          {position.symbol && position.name ? <span>{position.name}</span> : null}
          <code title={position.mintAddress}>{shortIdentity(position.mintAddress, 10)}</code>
        </div>
        <div className="position-card__badges">
          <SafetyBadge label="MODE" value={position.mode} tone="paper" />
          <SafetyBadge label="STATE" value={position.state} tone={position.state === "CLOSED" ? "advisory" : "safe"} />
        </div>
      </div>
      <div className="position-card__facts">
        <span>QTY <strong>{number(position.quantity, 6)}</strong></span>
        <span>ENTRY <strong>{number(position.averageEntry, 6)}</strong></span>
        <span>OPENED <strong>{readableDate(position.openedAt)}</strong></span>
      </div>
      <div className="position-evidence-grid">
        <PositionMark position={position} />
        <PositionPerformance position={position} />
        <ExitRisk position={position} />
        <ClosedTrade position={position} />
      </div>
    </article>
  );
}

function PositionsContent({ result }: { result: ReadResult<ReadPage<PositionRecord>> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">POSITION EVIDENCE / READ-ONLY</span>
        <strong>{failureMessage(result.reason)}</strong>
        <p>No position or market data was substituted. Retry after the read dependency is available.</p>
        <Link href="/positions">RETRY</Link>
      </div>
    );
  }
  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">PAPER PORTFOLIO</span>
        <strong>NO POSITIONS AVAILABLE</strong>
        <p>The bounded read API returned no position records. Empty is not a performance signal.</p>
      </div>
    );
  }
  return <div className="position-list" aria-label="Paper positions">{result.data.items.map((position) => <PositionCard key={position.id} position={position} />)}</div>;
}

export function PositionsDashboard({ result }: { result: ReadResult<ReadPage<PositionRecord>> }) {
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <section className="section-block intelligence-section" aria-labelledby="positions-title">
        <div className="section-heading">
          <div><p className="eyebrow">PAPER PORTFOLIO / OBSERVED + DERIVED EVIDENCE</p><h3 id="positions-title">Positions</h3></div>
          <p className="section-note">Marks and PnL are read-only projections; unknown data stays visible.</p>
        </div>
        <PositionsContent result={result} />
      </section>
      <section className="queue-card" aria-labelledby="position-boundary-title">
        <div className="queue-card__icon" aria-hidden="true">◌</div>
        <div><p className="eyebrow">PAPER / ADVISORY ONLY</p><h3 id="position-boundary-title">No execution controls in this view</h3><p>Exit risk and closed-trade explanations preserve evidence without authorizing orders.</p></div>
        <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
      </section>
    </main>
  );
}
