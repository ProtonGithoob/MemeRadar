"use client";

import Link from "next/link";
import { useState } from "react";

import type { EarlyRadarRecord, ReadPage, ReadResult } from "../lib/read-api";
import {
  Pill,
  evidenceTone,
  formatAgeSeconds,
  formatConfidence,
  formatScore,
  formatUsd,
  riskTone,
  shortIdentity
} from "./format";
import { PageHeader } from "./ui";

function readFailureMessage(result: ReadResult<unknown>): string {
  if (result.ok) return "";
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "EARLY RADAR NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "EARLY RADAR AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID EARLY RADAR RESPONSE";
    case "UNAVAILABLE":
      return "EARLY RADAR UNAVAILABLE";
  }
}

function displayMetric(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "UNKNOWN";
  return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function displayAlert(value: boolean | null): string {
  return value === null ? "NOT CONFIRMED" : value ? "DELIVERED" : "NOT DELIVERED";
}

function displayGate(value: boolean | null | undefined, pass: string, fail: string): string {
  return value == null ? "UNKNOWN" : value ? pass : fail;
}

/** Where a candidate stands against the backend's Telegram alert gate. */
export type AlertGate = "ALERT_READY" | "WAITING" | "BLOCKED" | "UNKNOWN";

const GATE_LABEL: Record<AlertGate, string> = {
  ALERT_READY: "ALERT READY",
  WAITING: "WAITING",
  BLOCKED: "BLOCKED",
  UNKNOWN: "UNKNOWN"
};
const GATE_TONE: Record<AlertGate, "low" | "medium" | "high" | "unknown"> = {
  ALERT_READY: "low",
  WAITING: "medium",
  BLOCKED: "high",
  UNKNOWN: "unknown"
};

/**
 * Classify a candidate. Alert readiness is decided only by the backend
 * (`qualifiedIds`); the browser never infers it from individual fields.
 */
export function alertGate(entry: EarlyRadarRecord, qualifiedIds: ReadonlySet<string> | null): AlertGate {
  if (qualifiedIds?.has(entry.candidateId)) return "ALERT_READY";
  if (entry.hardBlockReasons.length > 0 || entry.riskDisposition === "BLOCK" || entry.earlyState === "REJECT/LOW") {
    return "BLOCKED";
  }
  return qualifiedIds === null ? "UNKNOWN" : "WAITING";
}

/** Evidence the backend reported as missing or unverified for this candidate. */
export function missingEvidence(entry: EarlyRadarRecord): string[] {
  return entry.reasonCodes.filter((code) => /(_UNKNOWN|_MISSING|_UNVERIFIED)$/.test(code));
}

type PresetKey =
  | "ALL"
  | "ALERT_READY"
  | "HAS_TAPE"
  | "FRESH_1M"
  | "FRESH_5M"
  | "HIGH_CONFLUENCE"
  | "ENTRY_READY"
  | "CREATOR_RISK"
  | "BUNDLE_RISK"
  | "UNKNOWN_CRITICAL";

type SortKey =
  | "NEWEST"
  | "ACCELERATION"
  | "EARLY_SCORE"
  | "SMART_WALLETS"
  | "LOWEST_RISK"
  | "ORGANIC_MOMENTUM";

const PRESETS: Array<{ key: PresetKey; label: string; match: (entry: EarlyRadarRecord) => boolean }> = [
  { key: "ALL", label: "All tracked", match: () => true },
  // Matched against the backend-qualified set in the workspace, not here.
  { key: "ALERT_READY", label: "Alert ready", match: () => true },
  { key: "HAS_TAPE", label: "Has trade tape", match: (entry) => (entry.tapeTradeCount ?? 0) > 0 },
  {
    key: "FRESH_1M",
    label: "Fresh <1m",
    match: (entry) => entry.launchAgeSeconds !== null && entry.launchAgeSeconds < 60
  },
  {
    key: "FRESH_5M",
    label: "Fresh <5m",
    match: (entry) => entry.launchAgeSeconds !== null && entry.launchAgeSeconds < 300
  },
  { key: "HIGH_CONFLUENCE", label: "High Confluence", match: (entry) => entry.earlyState === "HIGH_CONFLUENCE" },
  { key: "ENTRY_READY", label: "Entry Ready", match: (entry) => entry.earlyState === "ENTRY_READY" },
  {
    key: "CREATOR_RISK",
    label: "Creator Risk",
    match: (entry) => ["medium", "high"].includes(evidenceTone(entry.creatorRisk))
  },
  {
    key: "BUNDLE_RISK",
    label: "Bundle Risk",
    match: (entry) => ["medium", "high"].includes(evidenceTone(entry.bundleRisk))
  },
  {
    key: "UNKNOWN_CRITICAL",
    label: "Unknown Critical Data",
    match: (entry) => entry.earlyScore === null || entry.riskDisposition === "UNKNOWN"
  }
];

const SORTS: Array<{ key: SortKey; label: string }> = [
  { key: "NEWEST", label: "Newest" },
  { key: "ACCELERATION", label: "Highest acceleration" },
  { key: "EARLY_SCORE", label: "Highest EarlyScore" },
  { key: "SMART_WALLETS", label: "Highest smart-wallet confluence" },
  { key: "LOWEST_RISK", label: "Lowest risk" },
  { key: "ORGANIC_MOMENTUM", label: "Highest organic momentum" }
];

const RISK_RANK: Record<string, number> = { PASS: 0, LOW: 0, WARN: 1, MEDIUM: 1, UNKNOWN: 2, HIGH: 3, BLOCK: 4 };

function descending(value: number | null): number {
  return value ?? Number.NEGATIVE_INFINITY;
}

function sortEntries(entries: EarlyRadarRecord[], sort: SortKey): EarlyRadarRecord[] {
  return [...entries].sort((left, right) => {
    if (sort === "NEWEST") return Date.parse(right.firstSeenAt) - Date.parse(left.firstSeenAt);
    if (sort === "EARLY_SCORE") return descending(right.earlyScore) - descending(left.earlyScore);
    if (sort === "SMART_WALLETS") {
      return descending(right.independentSmartWalletCount ?? right.smartMoneyConfluence)
        - descending(left.independentSmartWalletCount ?? left.smartMoneyConfluence);
    }
    if (sort === "ORGANIC_MOMENTUM") {
      return descending(right.organicMomentum) - descending(left.organicMomentum);
    }
    if (sort === "LOWEST_RISK") {
      const rank = (entry: EarlyRadarRecord) => Math.max(
        RISK_RANK[entry.riskDisposition] ?? 2,
        RISK_RANK[entry.creatorRisk] ?? 2,
        RISK_RANK[entry.bundleRisk] ?? 2,
        RISK_RANK[entry.holderRisk] ?? 2
      );
      return rank(left) - rank(right);
    }
    const acceleration = (entry: EarlyRadarRecord) => Math.max(
      entry.buyerAcceleration ?? Number.NEGATIVE_INFINITY,
      entry.volumeAcceleration ?? Number.NEGATIVE_INFINITY,
      entry.liquidityAcceleration ?? Number.NEGATIVE_INFINITY
    );
    return acceleration(right) - acceleration(left);
  });
}

const LIQUIDITY_SOURCE_LABELS: Record<string, string> = {
  EXECUTABLE_QUOTE_DEPTH: "Executable round trip at trade size (within impact limit)"
};

/** Liquidity provenance; an unrecorded source is UNKNOWN, never assumed. */
export function displayLiquiditySource(source: string | null | undefined): string {
  if (!source) return "UNKNOWN";
  return LIQUIDITY_SOURCE_LABELS[source] ?? source;
}

/** Decoded trade tape behind the momentum figures; missing counts stay UNKNOWN. */
export function displayTape(trades: number | null | undefined, buyers: number | null | undefined): string {
  if (trades == null && buyers == null) return "UNKNOWN";
  const tradeText = trades == null ? "UNKNOWN trades" : `${trades} trades`;
  const buyerText = buyers == null ? "UNKNOWN buyers" : `${buyers} unique buyers`;
  return `${tradeText} · ${buyerText}`;
}

function UltraEarlyRow({ entry, gate }: { entry: EarlyRadarRecord; gate: AlertGate }) {
  const missing = missingEvidence(entry);
  const displayName = entry.symbol || entry.name || shortIdentity(entry.mintAddress);
  return (
    <tr>
      <td>
        <div className="dt-token">
          <Link href={`/tokens/${entry.tokenId}`}>{displayName}</Link>
          <code title={entry.mintAddress}>{shortIdentity(entry.mintAddress)}</code>
        </div>
      </td>
      <td className="num">{entry.launchAgeSeconds === null ? "UNKNOWN" : formatAgeSeconds(entry.launchAgeSeconds)}</td>
      <td><Pill label={GATE_LABEL[gate]} tone={GATE_TONE[gate]} /></td>
      <td><Pill label={entry.earlyState} tone="info" /></td>
      <td className="num">{entry.earlyScore === null ? "UNKNOWN" : formatScore(entry.earlyScore)}</td>
      <td className="num">{entry.organicMomentum == null ? "UNKNOWN" : formatScore(entry.organicMomentum)}</td>
      <td className="num">{displayTape(entry.tapeTradeCount, entry.tapeUniqueBuyers)}</td>
      <td><Pill label={entry.riskDisposition} tone={riskTone(entry.riskDisposition)} /></td>
      <td className="num">{formatUsd(entry.liquidityUsd)}</td>
      <td><Pill label={entry.sellability} tone={evidenceTone(entry.sellability)} /></td>
      <td className="num">{entry.priceImpactBps === null ? "UNKNOWN" : displayMetric(entry.priceImpactBps)}</td>
      <td><Pill label={displayAlert(entry.alerted)} tone={entry.alerted ? "low" : "unknown"} /></td>
      <td>
        <details className="early-evidence">
          <summary>Inspect</summary>
          <div className="early-evidence__panel">
            <dl>
              <div><dt>Alert gate</dt><dd>{GATE_LABEL[gate]}</dd></div>
              <div><dt>Score confidence</dt><dd>{formatConfidence(entry.earlyScoreConfidence)}</dd></div>
              <div><dt>Decision market cap</dt><dd>{formatUsd(entry.currentMarketCap)}</dd></div>
              <div><dt>Protocol source</dt><dd>{entry.firstSeenSource}</dd></div>
              <div><dt>Venue</dt><dd>{entry.venue}</dd></div>
              <div><dt>Protocol identity</dt><dd>{displayGate(entry.protocolIdentityVerified, "VERIFIED", "UNVERIFIED")}</dd></div>
              <div><dt>Mint authority</dt><dd>{displayGate(entry.mintAuthoritySafe, "SAFE", "ACTIVE")}</dd></div>
              <div><dt>Freeze authority</dt><dd>{displayGate(entry.freezeAuthoritySafe, "SAFE", "ACTIVE")}</dd></div>
              <div><dt>Quote semantics</dt><dd>{entry.quoteSemantics ?? "UNKNOWN"}</dd></div>
              <div><dt>Input quote impact</dt><dd>{entry.buyImpactBps == null ? "UNKNOWN" : `${displayMetric(entry.buyImpactBps)} bps`}</dd></div>
              <div><dt>Exit quote impact</dt><dd>{entry.priceImpactBps == null ? "UNKNOWN" : `${displayMetric(entry.priceImpactBps)} bps`}</dd></div>
              <div><dt>Liquidity evidence</dt><dd>{displayLiquiditySource(entry.liquiditySource)}</dd></div>
              <div><dt>Organic momentum</dt><dd>{entry.organicMomentum == null ? "UNKNOWN" : formatScore(entry.organicMomentum)}</dd></div>
              <div><dt>Trade tape</dt><dd>{displayTape(entry.tapeTradeCount, entry.tapeUniqueBuyers)}</dd></div>
              <div><dt>Evidence quality</dt><dd>{entry.firstSeenQuality}</dd></div>
            </dl>
            {gate !== "ALERT_READY" && (
              <>
                <strong>Missing for an alert</strong>
                {entry.hardBlockReasons.length + missing.length ? (
                  <ul>{[...entry.hardBlockReasons, ...missing].map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}</ul>
                ) : <p>No missing evidence was reported; the score or freshness gate has not passed.</p>}
              </>
            )}
            <strong>Decision reasons</strong>
            {entry.reasonCodes.length ? (
              <ul>{entry.reasonCodes.map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}</ul>
            ) : <p>Current qualification gates passed without a warning.</p>}
            <strong>Source evidence</strong>
            {entry.evidenceRefs.length ? (
              <ul>{entry.evidenceRefs.map((reference) => <li key={reference}><code>{reference}</code></li>)}</ul>
            ) : <p>No source reference was attached.</p>}
          </div>
        </details>
      </td>
    </tr>
  );
}

const TABLE_HEAD = [
  "Token", "Age at decision", "Alert gate", "State", "Score", "Momentum", "Trade tape", "Risk",
  "Liquidity", "Sellable", "Sell impact (bps)", "Telegram", "Evidence"
];

function SummaryCard({ label, value, note, tone }: { label: string; value: string; note: string; tone?: "ok" | "warn" | "danger" }) {
  return (
    <div className="metric-card">
      <span className="metric-card__label">{label}</span>
      <strong className={tone ? `metric-card__value metric-card__value--${tone}` : "metric-card__value"}>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

export function UltraEarlyWorkspace({
  result,
  qualified
}: {
  result: ReadResult<ReadPage<EarlyRadarRecord>>;
  /** Candidates the backend currently passes through the Telegram alert gate. */
  qualified?: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  const [preset, setPreset] = useState<PresetKey>("ALL");
  const [sort, setSort] = useState<SortKey>("NEWEST");

  const heading = (
    <PageHeader
      eyebrow="Launch intelligence / read-only"
      note="Every tracked launch is listed; ALERT READY marks candidates the backend passes through the Telegram gate. Quotes are read-only probes, not order-size recommendations. Buying and selling are manual. Auto execution: LOCKED."
      title="Ultra-Early Detection"
    />
  );

  if (!result.ok) {
    return (
      <>
        {heading}
        <div className="read-state read-state--error" role="status">
          <strong>{readFailureMessage(result)}</strong>
          <p>No launch projection was substituted.</p>
          <Link href="/ultra-early">RETRY</Link>
        </div>
      </>
    );
  }

  const items = result.data.items;
  const qualifiedIds = qualified?.ok
    ? new Set(qualified.data.items.map((entry) => entry.candidateId))
    : null;
  const gates = new Map(items.map((entry) => [entry.candidateId, alertGate(entry, qualifiedIds)]));
  const countGate = (gate: AlertGate) => items.filter((entry) => gates.get(entry.candidateId) === gate).length;
  const activePreset = PRESETS.find((candidate) => candidate.key === preset) ?? PRESETS[0];
  const filtered = preset === "ALERT_READY"
    ? items.filter((entry) => gates.get(entry.candidateId) === "ALERT_READY")
    : items.filter(activePreset.match);
  const withTape = items.filter((entry) => (entry.tapeTradeCount ?? 0) > 0).length;

  return (
    <>
      {heading}

      <div className="metric-strip">
        <SummaryCard label="TRACKED" note={result.data.hasMore ? "First page; more exist" : "Launches in this view"} value={String(items.length)} />
        <SummaryCard
          label="ALERT READY"
          note={qualifiedIds === null ? "Gate status unavailable" : "Pass the Telegram gate now"}
          tone={qualifiedIds !== null && countGate("ALERT_READY") > 0 ? "ok" : undefined}
          value={qualifiedIds === null ? "UNKNOWN" : String(countGate("ALERT_READY"))}
        />
        <SummaryCard label="WAITING ON EVIDENCE" note="Not blocked, gate not passed" tone="warn" value={qualifiedIds === null ? "UNKNOWN" : String(countGate("WAITING"))} />
        <SummaryCard label="BLOCKED" note="Hard block or rejected" tone={countGate("BLOCKED") > 0 ? "danger" : undefined} value={String(countGate("BLOCKED"))} />
        <SummaryCard label="WITH TRADE TAPE" note="Decoded trades recorded" value={String(withTape)} />
      </div>

      <div aria-label="Ultra-early presets" className="preset-row" role="group">
        {PRESETS.map((candidate) => (
          <button
            aria-pressed={preset === candidate.key}
            className={preset === candidate.key ? "preset-chip preset-chip--active" : "preset-chip"}
            key={candidate.key}
            onClick={() => setPreset(candidate.key)}
            type="button"
          >
            {candidate.label}
          </button>
        ))}
      </div>

      <label className="control-row">
        <span className="card-label">SORT</span>
        <select aria-label="Sort launches" className="control-select" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
          {SORTS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </label>

      {filtered.length === 0 ? (
        <div className="read-state" role="status">
          <strong>{items.length === 0 ? "NO TRACKED LAUNCHES" : "NO MATCHING CANDIDATES"}</strong>
          <p>
            {items.length === 0
              ? "No launch has been recorded yet. This does not confirm that scanning is active."
              : preset === "ALERT_READY"
                ? "No tracked candidate currently passes the authority, liquidity, executable buy/sell quote and stream-integrity gates. Reference prices do not count as executable quotes."
                : `No launch projection matches the ${activePreset.label} preset.`}
          </p>
          {items.length === 0 && <Link href="/scan-monitor">OPEN SCAN MONITOR</Link>}
        </div>
      ) : (
        <div className="dt-wrap">
          <table aria-label="Ultra-early launch candidates" className="dt">
            <thead>
              <tr>{TABLE_HEAD.map((head) => <th key={head} scope="col">{head}</th>)}</tr>
            </thead>
            <tbody>
              {sortEntries(filtered, sort).map((entry) => (
                <UltraEarlyRow entry={entry} gate={gates.get(entry.candidateId) ?? "UNKNOWN"} key={entry.candidateId} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/** Compact read-only embed used inside the token workspace. */
export function UltraEarlyPanel({
  result
}: {
  result: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  if (!result.ok) {
    return (
      <section className="section-block" aria-labelledby="ultra-early-title">
        <div className="section-heading">
          <h3 id="ultra-early-title">Ultra-Early Detection</h3>
        </div>
        <div className="read-state read-state--error" role="status">
          <strong>{readFailureMessage(result)}</strong>
          <p>No launch projection was substituted.</p>
        </div>
      </section>
    );
  }

  const items = result.data.items;
  return (
    <section className="section-block" aria-labelledby="ultra-early-title">
      <div className="section-heading">
        <h3 id="ultra-early-title">Ultra-Early Detection</h3>
        <p className="section-note">Observed, derived and paper-only fields; UNKNOWN remains explicit.</p>
      </div>
      {items.length === 0 ? (
        <div className="read-state" role="status">
          <strong>NO ULTRA-EARLY CANDIDATES</strong>
          <p>No launch projection matched the current read boundary.</p>
        </div>
      ) : (
        <div className="dt-wrap">
          <table aria-label="Ultra-early launch candidates" className="dt">
            <thead>
              <tr>{TABLE_HEAD.map((head) => <th key={head} scope="col">{head}</th>)}</tr>
            </thead>
            <tbody>
              {items.map((entry) => <UltraEarlyRow entry={entry} gate={alertGate(entry, null)} key={entry.candidateId} />)}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
