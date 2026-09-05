import Link from "next/link";

import type {
  CandidateRecord,
  EarlyRadarRecord,
  RadarFilters,
  ReadPage,
  ReadResult
} from "../lib/read-api";
import { RadarTable, type RadarRow } from "./radar-table";

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

export function readFailureMessage(
  result: ReadResult<unknown>,
  unavailableLabel = "RADAR UNAVAILABLE"
): string {
  if (result.ok) return "";
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "READ API NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "READ API AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID READ RESPONSE";
    case "UNAVAILABLE":
      return unavailableLabel;
  }
}

export function joinRadarRows(
  candidates: CandidateRecord[],
  earlyItems: EarlyRadarRecord[]
): RadarRow[] {
  const earlyByToken = new Map(earlyItems.map((item) => [item.tokenId, item]));
  return candidates.map((candidate) => ({
    candidate,
    early: earlyByToken.get(candidate.tokenId) ?? null
  }));
}

function Filters({ filters }: { filters: RadarFilters }) {
  return (
    <form action="/radar" aria-label="Radar filters" className="radar-filters" method="get">
      <label>
        <span>State</span>
        <select aria-label="State" defaultValue={filters.state ?? ""} name="state">
          <option value="">All states</option>
          {candidateStates.map((state) => <option key={state} value={state}>{state}</option>)}
        </select>
      </label>
      <label>
        <span>Risk</span>
        <select aria-label="Risk" defaultValue={filters.riskDisposition ?? ""} name="risk_disposition">
          <option value="">All risk states</option>
          {riskStates.map((risk) => <option key={risk} value={risk}>{risk}</option>)}
        </select>
      </label>
      <label>
        <span>Minimum score</span>
        <input
          aria-label="Minimum score"
          defaultValue={filters.minScore ?? ""}
          inputMode="numeric"
          max="100"
          min="0"
          name="min_score"
          step="1"
          type="number"
        />
      </label>
      <button className="filter-submit" type="submit">APPLY FILTERS</button>
      <Link className="filter-reset" href="/radar">RESET</Link>
    </form>
  );
}

export function RadarExplorer({
  filters,
  result,
  earlyResult
}: {
  filters: RadarFilters;
  result: ReadResult<ReadPage<CandidateRecord>>;
  earlyResult?: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Ranked observations / read-only</p>
          <h2>Radar</h2>
        </div>
        <small>Ranking and state come from the bounded read API. API order is preserved until you sort.</small>
      </div>
      <Filters filters={filters} />
      <RadarContent earlyResult={earlyResult} result={result} />
    </>
  );
}

export function RadarContent({
  result,
  earlyResult
}: {
  result: ReadResult<ReadPage<CandidateRecord>>;
  earlyResult?: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">Read-only boundary</span>
        <strong>{readFailureMessage(result)}</strong>
        <p>No candidate data was substituted. Retry after the read dependency is available.</p>
        <Link href="/radar">RETRY</Link>
      </div>
    );
  }

  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">Radar queue</span>
        <strong>NO CANDIDATES MATCH FILTERS</strong>
        <p>The read API returned an empty ranked page. No sample candidate is shown.</p>
      </div>
    );
  }

  const earlyItems = earlyResult?.ok ? earlyResult.data.items : [];
  return <RadarTable rows={joinRadarRows(result.data.items, earlyItems)} />;
}
