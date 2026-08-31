import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./status-badges";
import { OperatorHeader } from "./operator-header";
import type {
  CandidateRecord,
  RadarFilters,
  ReadPage,
  ReadResult
} from "../lib/read-api";

const operatingModes = [
  {
    label: "ANALYSIS ONLY",
    value: "Enabled",
    detail: "Evidence collection remains on.",
    tone: "safe"
  },
  {
    label: "PAPER TRADING",
    value: "Enabled",
    detail: "Simulated outcomes only.",
    tone: "paper"
  },
  {
    label: "MANUAL EXECUTION",
    value: "Disabled",
    detail: "Operator approval path is locked.",
    tone: "disabled"
  },
  {
    label: "AUTO EXECUTION",
    value: "Disabled",
    detail: "No autonomous orders are possible.",
    tone: "disabled"
  }
] as const;

const candidateStates = [
  "DISCOVERED",
  "ENRICHING",
  "RISK_REJECTED",
  "WATCH",
  "STRONG_SETUP",
  "ENTRY_READY",
  "PAPER_OPEN",
  "LIVE_PENDING_APPROVAL",
  "OPEN",
  "EXIT_SIGNALLED",
  "CLOSED"
] as const;

const riskStates = ["PASS", "WARN", "BLOCK", "UNKNOWN"] as const;

function shortIdentity(value: string, visible = 8): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function resultMessage(result: ReadResult<ReadPage<CandidateRecord>>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "READ API NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "READ API AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID READ RESPONSE";
    case "UNAVAILABLE":
      return "RADAR UNAVAILABLE";
  }
}

function ProtectedShell() {
  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__copy">
          <p className="eyebrow">EVIDENCE BEFORE EXECUTION</p>
          <h2 id="hero-title">A calmer view of a noisy market.</h2>
          <p className="lede">
            MemeRadar correlates normalized observations, risk evidence and explainable scoring.
            The operator surface stays useful even when providers are unavailable.
          </p>
          <div className="badge-row" aria-label="Data boundaries">
            <SafetyBadge label="LIVE DATA" value="READ ONLY" tone="disabled" />
            <SafetyBadge label="ADVISORY OUTPUT" value="ONLY" tone="advisory" />
          </div>
        </div>
        <div className="status-orb" aria-label="Analysis system status: protected">
          <span aria-hidden="true" />
          <strong>PROTECTED</strong>
          <small>NO LIVE ORDERS</small>
        </div>
      </section>

      <section className="section-block" aria-labelledby="modes-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">OPERATING POLICY</p>
            <h3 id="modes-title">Protected modes</h3>
          </div>
          <p className="section-note">These values are enforced by the API configuration.</p>
        </div>
        <div className="mode-grid">
          {operatingModes.map((mode) => (
            <article className={`mode-card mode-card--${mode.tone}`} key={mode.label}>
              <span className="card-label">{mode.label}</span>
              <strong className={`mode-value mode-value--${mode.tone}`}>{mode.value}</strong>
              <small>{mode.detail}</small>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function Filters({ filters }: { filters: RadarFilters }) {
  return (
    <form className="radar-filters" method="get" action="/" aria-label="Radar filters">
      <label>
        <span>State</span>
        <select name="state" defaultValue={filters.state ?? ""} aria-label="State">
          <option value="">All states</option>
          {candidateStates.map((state) => <option key={state} value={state}>{state}</option>)}
        </select>
      </label>
      <label>
        <span>Risk</span>
        <select
          name="risk_disposition"
          defaultValue={filters.riskDisposition ?? ""}
          aria-label="Risk"
        >
          <option value="">All risk states</option>
          {riskStates.map((risk) => <option key={risk} value={risk}>{risk}</option>)}
        </select>
      </label>
      <label>
        <span>Minimum score</span>
        <input
          name="min_score"
          type="number"
          min="0"
          max="100"
          step="1"
          inputMode="numeric"
          defaultValue={filters.minScore ?? ""}
          aria-label="Minimum score"
        />
      </label>
      <button className="filter-submit" type="submit">APPLY FILTERS</button>
      <a className="filter-reset" href="/">RESET</a>
    </form>
  );
}

export function CandidateRow({ candidate }: { candidate: CandidateRecord }) {
  const displayName = candidate.symbol || candidate.name || "UNNAMED TOKEN";
  return (
    <article className="candidate-card">
      <div className="candidate-card__identity">
        <a className="candidate-symbol" href={`/tokens/${candidate.tokenId}`}>
          {displayName}
        </a>
        {candidate.name && candidate.symbol ? <span>{candidate.name}</span> : null}
        <code title={candidate.mintAddress}>{shortIdentity(candidate.mintAddress, 10)}</code>
        <small>DISCOVERED {readableDate(candidate.discoveredAt)}</small>
      </div>
      <div className="candidate-card__state">
        <span className="card-label">STATE</span>
        <strong>{candidate.state}</strong>
        <small>source {shortIdentity(candidate.discoverySource, 14)}</small>
      </div>
      <div className="candidate-card__metrics">
        <ScoreBadge value={candidate.score} />
        <span className="confidence-label">
          CONFIDENCE {candidate.scoreConfidence === null ? "UNKNOWN" : `${Math.round(candidate.scoreConfidence * 100)}%`}
        </span>
      </div>
      <div className="candidate-card__risk">
        <RiskBadge value={candidate.riskDisposition} />
        <FreshnessBadge value={candidate.riskQualityState} />
        <small>{candidate.riskReasonCodes.length} risk reason{candidate.riskReasonCodes.length === 1 ? "" : "s"}</small>
      </div>
    </article>
  );
}

function RadarContent({ result }: { result: ReadResult<ReadPage<CandidateRecord>> }) {
  const message = resultMessage(result);
  if (message) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">READ-ONLY BOUNDARY</span>
        <strong>{message}</strong>
        <p>No candidate data was substituted. Retry after the read dependency is available.</p>
        <a href="/">RETRY</a>
      </div>
    );
  }

  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">RADAR QUEUE</span>
        <strong>NO CANDIDATES MATCH FILTERS</strong>
        <p>The read API returned an empty ranked page. No sample candidate is shown.</p>
      </div>
    );
  }

  return (
    <div className="candidate-list" aria-label="Ranked candidates">
      {result.data.items.map((candidate) => <CandidateRow candidate={candidate} key={candidate.id} />)}
    </div>
  );
}

export function RadarDashboard({
  filters,
  result
}: {
  filters: RadarFilters;
  result: ReadResult<ReadPage<CandidateRecord>>;
}) {
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <section className="section-block radar-section" aria-labelledby="radar-title">
        <div className="section-heading radar-heading">
          <div>
            <p className="eyebrow">RANKED OBSERVATIONS / READ-ONLY</p>
            <h3 id="radar-title">Radar</h3>
          </div>
          <p className="section-note">Ranking and state come from the bounded read API.</p>
        </div>
        <Filters filters={filters} />
        <RadarContent result={result} />
      </section>
      <section className="queue-card" aria-labelledby="queue-title">
        <div className="queue-card__icon" aria-hidden="true">◎</div>
        <div>
          <p className="eyebrow">OPERATOR BOUNDARY / ADVISORY</p>
          <h3 id="queue-title">No browser-side execution controls</h3>
          <p>Read data, provider labels and narratives cannot authorize an order.</p>
        </div>
        <span className="queue-card__state">NO LIVE ORDERS</span>
      </section>
    </main>
  );
}
