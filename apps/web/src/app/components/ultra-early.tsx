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

type PresetKey =
  | "ALL"
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
  { key: "ALL", label: "All", match: () => true },
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

function UltraEarlyRow({ entry }: { entry: EarlyRadarRecord }) {
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
      <td><Pill label={entry.earlyState} tone="info" /></td>
      <td className="num">{entry.earlyScore === null ? "UNKNOWN" : formatScore(entry.earlyScore)}</td>
      <td className="num">{formatConfidence(entry.earlyScoreConfidence)}</td>
      <td><Pill label={entry.riskDisposition} tone={riskTone(entry.riskDisposition)} /></td>
      <td className="num">{formatUsd(entry.liquidityUsd)}</td>
      <td className="num">{formatUsd(entry.currentMarketCap)}</td>
      <td><Pill label={entry.sellability} tone={evidenceTone(entry.sellability)} /></td>
      <td className="num">{entry.priceImpactBps === null ? "UNKNOWN" : displayMetric(entry.priceImpactBps)}</td>
      <td><Pill label={displayAlert(entry.alerted)} tone={entry.alerted ? "low" : "unknown"} /></td>
      <td>
        <details className="early-evidence">
          <summary>Inspect</summary>
          <div className="early-evidence__panel">
            <dl>
              <div><dt>Protocol source</dt><dd>{entry.firstSeenSource}</dd></div>
              <div><dt>Venue</dt><dd>{entry.venue}</dd></div>
              <div><dt>Protocol identity</dt><dd>{displayGate(entry.protocolIdentityVerified, "VERIFIED", "UNVERIFIED")}</dd></div>
              <div><dt>Mint authority</dt><dd>{displayGate(entry.mintAuthoritySafe, "SAFE", "ACTIVE")}</dd></div>
              <div><dt>Freeze authority</dt><dd>{displayGate(entry.freezeAuthoritySafe, "SAFE", "ACTIVE")}</dd></div>
              <div><dt>Quote semantics</dt><dd>{entry.quoteSemantics ?? "UNKNOWN"}</dd></div>
              <div><dt>Input quote impact</dt><dd>{entry.buyImpactBps == null ? "UNKNOWN" : `${displayMetric(entry.buyImpactBps)} bps`}</dd></div>
              <div><dt>Exit quote impact</dt><dd>{entry.priceImpactBps == null ? "UNKNOWN" : `${displayMetric(entry.priceImpactBps)} bps`}</dd></div>
              <div><dt>Evidence quality</dt><dd>{entry.firstSeenQuality}</dd></div>
            </dl>
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
  "Token", "Age at decision", "State", "Score", "Confidence", "Risk", "Liquidity",
  "Decision MC", "Sellable", "Sell impact @ 0.01 SOL", "Telegram", "Evidence"
];

export function UltraEarlyWorkspace({
  result
}: {
  result: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  const [preset, setPreset] = useState<PresetKey>("ALL");
  const [sort, setSort] = useState<SortKey>("NEWEST");

  const heading = (
    <PageHeader
      eyebrow="Launch intelligence / read-only"
      note="Only fresh candidates passing the Telegram gate are shown. When an executable quote provider is configured, buy and sell routes use a read-only 0.01 SOL probe; this is not an order-size recommendation. Auto execution: LOCKED."
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
  const activePreset = PRESETS.find((candidate) => candidate.key === preset) ?? PRESETS[0];
  const filtered = items.filter(activePreset.match);

  return (
    <>
      {heading}

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

      <label>
        <span>Sort launches</span>
        <select aria-label="Sort launches" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
          {SORTS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </label>

      {filtered.length === 0 ? (
        <div className="read-state" role="status">
          <strong>NO ULTRA-EARLY CANDIDATES</strong>
          <p>
            {items.length === 0
              ? "No fresh candidate currently passes the authority, liquidity, executable buy/sell quote and stream-integrity gates. Reference prices do not count as executable quotes."
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
              {sortEntries(filtered, sort).map((entry) => <UltraEarlyRow entry={entry} key={entry.candidateId} />)}
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
              {items.map((entry) => <UltraEarlyRow entry={entry} key={entry.candidateId} />)}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
