"use client";

import Link from "next/link";
import { useState } from "react";

import type { EarlyRadarRecord, ReadPage, ReadResult } from "../lib/read-api";
import {
  Pill,
  evidenceTone,
  formatAgeSeconds,
  formatCompactMap,
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
  return value === null ? "UNKNOWN" : value ? "YES" : "NO";
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
  const displayName = entry.symbol || entry.name || "UNNAMED";
  return (
    <tr>
      <td>
        <div className="dt-token">
          <Link href={`/tokens/${entry.tokenId}`}>{displayName}</Link>
          <code title={entry.mintAddress}>{shortIdentity(entry.mintAddress)}</code>
        </div>
      </td>
      <td className="num">{entry.launchAgeSeconds === null ? "UNKNOWN" : formatAgeSeconds(entry.launchAgeSeconds)}</td>
      <td><Pill label={entry.venue} tone={evidenceTone(entry.venue)} /></td>
      <td className="num">{formatUsd(entry.firstSeenMarketCap)}</td>
      <td className="num">{formatUsd(entry.currentMarketCap)}</td>
      <td className="num">{formatUsd(entry.liquidityUsd)}</td>
      <td className="dt-reasons" title={formatCompactMap(entry.uniqueBuyers, 6)}>{formatCompactMap(entry.uniqueBuyers)}</td>
      <td className="num">{displayMetric(entry.buyerAcceleration)}</td>
      <td className="num">{displayMetric(entry.volumeAcceleration)}</td>
      <td className="num">{displayMetric(entry.liquidityAcceleration)}</td>
      <td className="num">{displayMetric(entry.rawSmartWalletCount)}</td>
      <td className="num">{displayMetric(entry.independentSmartWalletCount)}</td>
      <td className="num">{entry.organicMomentum === null ? "UNKNOWN" : formatScore(entry.organicMomentum)}</td>
      <td className="num">{entry.earlyScore === null ? "UNKNOWN" : formatScore(entry.earlyScore)}</td>
      <td className="num">{formatConfidence(entry.earlyScoreConfidence)}</td>
      <td><Pill label={entry.earlyState} tone="info" /></td>
      <td><Pill label={entry.riskDisposition} tone={riskTone(entry.riskDisposition)} /></td>
      <td className="num">{entry.priceImpactBps === null ? "UNKNOWN" : `${displayMetric(entry.priceImpactBps)}`}</td>
      <td className="dt-reasons" title={formatCompactMap(entry.buyVelocity, 6)}>{formatCompactMap(entry.buyVelocity)}</td>
      <td><Pill label={entry.creatorRisk} tone={evidenceTone(entry.creatorRisk)} /></td>
      <td><Pill label={entry.bundleRisk} tone={evidenceTone(entry.bundleRisk)} /></td>
      <td><Pill label={entry.holderRisk} tone={evidenceTone(entry.holderRisk)} /></td>
      <td className="num">{entry.smartMoneyConfluence === null ? "UNKNOWN" : formatScore(entry.smartMoneyConfluence)}</td>
      <td><Pill label={entry.sellability} tone={evidenceTone(entry.sellability)} /></td>
      <td className="dt-reasons" title={formatCompactMap(entry.upsideEvidence, 6)}>
        {formatCompactMap(entry.upsideEvidence, 3)}
      </td>
      <td><Pill label={entry.marketIntegrityRisk} tone={evidenceTone(entry.marketIntegrityRisk)} /></td>
      <td><Pill label={entry.contractDeployerRisk} tone={evidenceTone(entry.contractDeployerRisk)} /></td>
      <td><Pill label={entry.liquidityExitRisk} tone={evidenceTone(entry.liquidityExitRisk)} /></td>
      <td className="num">{entry.executionQuality === null ? "UNKNOWN" : displayMetric(entry.executionQuality)}</td>
      <td className="num">{formatConfidence(entry.evidenceConfidence)}</td>
      <td><Pill label={entry.evidenceQualityState} tone={evidenceTone(entry.evidenceQualityState)} /></td>
      <td className="num">{entry.firstSeenLatencyMs === null ? "UNKNOWN" : `${displayMetric(entry.firstSeenLatencyMs)}ms`}</td>
      <td><Pill label={displayAlert(entry.alerted)} tone={entry.alerted === null ? "unknown" : entry.alerted ? "low" : "medium"} /></td>
      <td className="num">{entry.alertLatencyMs === null ? "UNKNOWN" : `${displayMetric(entry.alertLatencyMs)}ms`}</td>
      <td className="num">{entry.multipleSinceDiscovery === null ? "UNKNOWN" : `${displayMetric(entry.multipleSinceDiscovery)}x`}</td>
    </tr>
  );
}

const TABLE_HEAD = [
  "Token", "Age", "Venue", "First seen MC", "Current MC", "Liquidity", "Buyers",
  "Buyer accel", "Volume accel", "Liquidity accel", "Raw smart $", "Independent smart $",
  "Organic momentum", "Score", "Conf", "State", "Risk", "Impact bps", "Buy velocity",
  "Creator", "Bundle", "Holder", "Smart $", "Sellable", "Upside evidence", "Market integrity",
  "Contract / deployer", "Liquidity / exit", "Exec quality", "Evidence conf", "Evidence freshness",
  "1st-seen latency", "Alerted", "Alert latency", "Since discovery"
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
      note="Observed, derived and paper-only fields; UNKNOWN remains explicit. Auto execution: LOCKED."
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
              ? "No launch projection matched the current read boundary."
              : `No launch projection matches the ${activePreset.label} preset.`}
          </p>
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
