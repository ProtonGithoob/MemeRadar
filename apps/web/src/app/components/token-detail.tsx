import React from "react";
import Link from "next/link";

import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./status-badges";
import {
  MetricCard,
  StatusPill,
  RiskChip,
  FreshnessIndicator,
  ScoreGauge,
  SectionHeader,
  EmptyState,
  ErrorState,
  Tooltip
} from "./ui-primitives";
import type {
  CandidateRecord,
  CreatorReputationRecord,
  EarlyRadarRecord,
  PositionRecord,
  ReadPage,
  ReadResult,
  TimelineRecord,
  TokenRecord
} from "../lib/read-api";

type MetricPoint = { at: string; value: number };

const MAX_CHART_POINTS = 24;
const METRIC_KEYS = {
  price: ["price"],
  liquidity: ["liquidity", "liquidity_usd"],
  buy: ["buy_volume", "buyVolume24h"],
  sell: ["sell_volume", "sellVolume24h"]
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteMetric(value: unknown): number | null {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && (value.length > 32 || value.trim() === "")) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1_000_000_000_000_000
    ? parsed
    : null;
}

function metricFromEntry(entry: TimelineRecord, keys: readonly string[]): number | null {
  const payload = entry.payload;
  const containers: Record<string, unknown>[] = [payload];
  for (const key of ["values", "metrics", "snapshot"]) {
    const nested = payload[key];
    if (isRecord(nested)) containers.push(nested);
  }
  for (const container of containers) {
    for (const key of keys) {
      const value = finiteMetric(container[key]);
      if (value !== null) return value;
    }
  }
  return null;
}

function pointsFor(entries: TimelineRecord[], keys: readonly string[]): MetricPoint[] {
  const points: MetricPoint[] = [];
  for (const entry of entries) {
    const value = metricFromEntry(entry, keys);
    if (value !== null) points.push({ at: entry.occurredAt, value });
  }
  return points.slice(-MAX_CHART_POINTS);
}

function netFlowPointsFor(entries: TimelineRecord[]): MetricPoint[] {
  const points: MetricPoint[] = [];
  for (const entry of entries) {
    const buy = metricFromEntry(entry, METRIC_KEYS.buy);
    const sell = metricFromEntry(entry, METRIC_KEYS.sell);
    if (buy !== null && sell !== null) {
      points.push({ at: entry.occurredAt, value: buy - sell });
    }
  }
  return points.slice(-MAX_CHART_POINTS);
}

function shortIdentity(value: string, visible = 9): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function displayDate(value: string): string {
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : "UNKNOWN TIME";
}

function displayNumber(value: number): string {
  if (Math.abs(value) >= 1_000_000) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function displayPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0 || value > 100) return "UNKNOWN";
  const normalized = value <= 1 ? value * 100 : value;
  return normalized > 100 ? "UNKNOWN" : `${normalized.toFixed(1)}%`;
}

function holderMetric(entries: TimelineRecord[], keys: readonly string[]): number | null {
  let value: number | null = null;
  for (const entry of entries) {
    if (!entry.kind.startsWith("holder.")) continue;
    const next = metricFromEntry(entry, keys);
    if (next !== null) value = next;
  }
  return value;
}

function failureMessage(
  result: ReadResult<unknown>,
  scope: "radar" | "detail" = "detail"
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
      return scope === "radar" ? "RADAR UNAVAILABLE" : "DETAIL UNAVAILABLE";
  }
}

export function MetricChart({ label, points }: { label: string; points: MetricPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="metric-chart metric-chart--empty" role="status">
        <span>{label.toUpperCase()}</span>
        <strong>NO DATA</strong>
      </div>
    );
  }

  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const coordinates = points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 92 - ((point.value - minimum) / span) * 76;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="metric-chart">
      <div className="metric-chart__heading">
        <span>{label.toUpperCase()}</span>
        <strong>{displayNumber(points[points.length - 1]?.value ?? 0)}</strong>
      </div>
      <svg
        className="metric-chart__svg"
        viewBox="0 0 100 100"
        role="img"
        aria-label={`${label} evidence chart`}
        preserveAspectRatio="none"
      >
        <title>{`${label} evidence chart, ${points.length} event-time points`}</title>
        <line x1="0" y1="92" x2="100" y2="92" className="metric-chart__axis" />
        <polyline points={coordinates} className="metric-chart__line" />
      </svg>
      <small>{points.length} event-time point{points.length === 1 ? "" : "s"}; API order preserved</small>
    </div>
  );
}

function Overview({ token, earlyRadar }: { token: TokenRecord; earlyRadar?: EarlyRadarRecord | null }) {
  const candidate = token.candidate;
  const risk = candidate?.riskDisposition ?? earlyRadar?.riskDisposition ?? "UNKNOWN";
  const freshness = candidate?.riskQualityState ?? earlyRadar?.firstSeenQuality ?? "UNKNOWN";
  const score = candidate?.score ?? earlyRadar?.earlyScore ?? null;
  const earlyState = earlyRadar?.earlyState ?? candidate?.state ?? "WATCH";

  return (
    <section className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 mb-6 space-y-4" aria-labelledby="token-overview-title">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-semibold text-emerald-400 tracking-wider uppercase">
              TOKEN RESEARCH WORKSTATION
            </span>
            <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded uppercase">
              {earlyState}
            </span>
          </div>
          <h1 id="token-overview-title" className="text-2xl font-bold text-gray-100 flex items-center gap-3">
            {token.symbol || "UNNAMED"}
            {token.name ? <span className="text-sm font-normal text-gray-400">({token.name})</span> : null}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <code className="text-xs font-mono text-cyan-400 bg-cyan-950/40 px-2 py-1 rounded border border-cyan-800/50" title={token.mintAddress}>
              {shortIdentity(token.mintAddress, 12)}
            </code>
            <Link
              href={`/wallet-graph?token=${token.mintAddress}`}
              className="text-xs text-indigo-400 hover:text-indigo-300 no-underline font-medium flex items-center gap-1"
            >
              <span>Explore Graph →</span>
            </Link>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="token-status-grid flex items-center gap-3">
            <ScoreBadge value={score} />
            <RiskBadge value={risk} />
            <FreshnessBadge value={freshness} />
          </div>
          <div className="badge-row flex items-center gap-2">
            <SafetyBadge label="ADVISORY OUTPUT" value="ONLY" tone="advisory" />
            <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
          </div>
        </div>
      </div>

      <div className="overview-grid grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <article className="detail-panel bg-gray-950/50 p-3 rounded-lg border border-gray-800/70">
          <span className="card-label block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">IDENTITY & SPEC</span>
          <dl className="detail-list grid grid-cols-2 gap-2 text-gray-300">
            <div><dt className="text-gray-400 text-[10px]">CHAIN</dt><dd className="font-semibold">{token.chain}</dd></div>
            <div><dt className="text-gray-400 text-[10px]">PROGRAM</dt><dd className="font-semibold">{token.tokenProgram}</dd></div>
            <div><dt className="text-gray-400 text-[10px]">STATUS</dt><dd className="font-semibold">{token.status}</dd></div>
            <div><dt className="text-gray-400 text-[10px]">DECIMALS</dt><dd className="font-semibold">{token.decimals ?? "UNKNOWN"}</dd></div>
          </dl>
        </article>

        <article className="detail-panel bg-gray-950/50 p-3 rounded-lg border border-gray-800/70">
          <span className="card-label block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">CREATOR WALLET</span>
          {token.creatorWallet ? (
            <div className="space-y-1">
              <code className="text-xs text-amber-400 font-mono block truncate" title={token.creatorWallet}>
                {shortIdentity(token.creatorWallet, 12)}
              </code>
              <Link href={`/wallets/${token.creatorWallet}`} className="text-[11px] text-gray-400 hover:text-gray-200">
                View Wallet Profile →
              </Link>
            </div>
          ) : <strong className="text-gray-500">UNKNOWN</strong>}
          <small className="muted-copy block text-[10px] text-gray-400 mt-2">Wallet identity is evidence, not execution authority.</small>
        </article>

        <article className="detail-panel detail-panel--wide bg-gray-950/50 p-3 rounded-lg border border-gray-800/70">
          <div className="panel-heading flex items-center justify-between mb-2">
            <span className="card-label text-[10px] font-semibold text-gray-400 uppercase tracking-wider">LIQUIDITY POOLS</span>
            <small className="text-[10px] text-gray-400">{token.pools.length} known</small>
          </div>
          {token.pools.length === 0 ? <strong className="text-gray-500">UNKNOWN</strong> : (
            <div className="pool-list space-y-1.5 max-h-24 overflow-y-auto pr-1">
              {token.pools.map((pool) => (
                <div className="pool-row flex items-center justify-between text-[11px] bg-gray-900/60 p-1.5 rounded border border-gray-800/50" key={pool.id}>
                  <strong className="text-gray-200">{pool.venue}</strong>
                  <code className="text-gray-400 font-mono text-[10px]" title={pool.poolAddress}>{shortIdentity(pool.poolAddress, 9)}</code>
                  <small className="text-gray-400 text-[10px]">QUOTE {shortIdentity(pool.quoteMint, 7)}</small>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}

function HolderBar({ label, value }: { label: string; value: number | null }) {
  const normalized = value === null ? null : value <= 1 ? value * 100 : value;
  const width = normalized === null || !Number.isFinite(normalized)
    ? 0
    : Math.min(100, Math.max(0, normalized));
  return (
    <div className="holder-metric mb-3">
      <div className="panel-heading flex justify-between text-xs mb-1">
        <span className="text-gray-300 font-medium">{label}</span>
        <strong className="text-gray-100">{displayPercent(value)}</strong>
      </div>
      <div className="holder-bar h-2 w-full bg-gray-800 rounded overflow-hidden" aria-hidden="true">
        <span className={`block h-full transition-all ${width > 50 ? 'bg-rose-500' : width > 30 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function ExplainabilityPanel({
  candidate,
  earlyRadar,
  reasonCodes
}: {
  candidate?: CandidateRecord | null;
  earlyRadar?: EarlyRadarRecord | null;
  reasonCodes: string[];
}) {
  const allReasons = Array.from(new Set([
    ...(candidate?.riskReasonCodes ?? []),
    ...(earlyRadar?.reasonCodes ?? []),
    ...(earlyRadar?.hardBlockReasons ?? []),
    ...reasonCodes
  ]));

  const hardBlocks = earlyRadar?.hardBlockReasons ?? [];
  const score = candidate?.score ?? earlyRadar?.earlyScore ?? null;
  const risk = candidate?.riskDisposition ?? earlyRadar?.riskDisposition ?? "UNKNOWN";

  return (
    <section className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 mb-6 space-y-4">
      <SectionHeader
        title="OPERATOR EXPLAINABILITY"
        subtitle="WHY INTERESTING / WHY RISKY / WHAT IS UNKNOWN"
        actionLabel="DETERMINISTIC EVIDENCE"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        {/* WHY INTERESTING */}
        <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-lg p-3 space-y-2">
          <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block">
            ✓ WHY INTERESTING (UPSIDE FACTORS)
          </span>
          <ul className="space-y-1.5 text-gray-300 list-disc list-inside">
            {score !== null && score >= 60 ? (
              <li>AlphaScore candidate rating: <strong className="text-emerald-300">{score}/100</strong></li>
            ) : null}
            {earlyRadar?.earlyState ? (
              <li>Signal funnel stage: <strong className="text-emerald-300">{earlyRadar.earlyState}</strong></li>
            ) : null}
            {earlyRadar?.smartMoneyConfluence !== null && earlyRadar?.smartMoneyConfluence !== undefined && earlyRadar.smartMoneyConfluence > 0 ? (
              <li>Smart wallet confluence detected: <strong className="text-emerald-300">+{earlyRadar.smartMoneyConfluence}%</strong></li>
            ) : null}
            {earlyRadar?.asymmetricAlpha?.upsideEvidenceScore ? (
              <li>Asymmetric upside evidence score: <strong className="text-emerald-300">{earlyRadar.asymmetricAlpha.upsideEvidenceScore}/100</strong></li>
            ) : null}
            {score === null && !earlyRadar ? (
              <li className="text-gray-400 italic">No positive score metrics recorded yet.</li>
            ) : null}
          </ul>
        </div>

        {/* WHY RISKY */}
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-lg p-3 space-y-2">
          <span className="text-[11px] font-bold text-rose-400 uppercase tracking-wider block">
            ⚠ WHY RISKY (HARD GATES & RISKS)
          </span>
          <ul className="space-y-1.5 text-gray-300 list-disc list-inside">
            {risk !== "PASS" ? (
              <li>Risk disposition: <strong className="text-rose-300">{risk}</strong></li>
            ) : null}
            {hardBlocks.map((b) => (
              <li key={b} className="text-rose-300 font-semibold">HARD BLOCK: {b}</li>
            ))}
            {earlyRadar?.creatorRisk && earlyRadar.creatorRisk !== "PASS" ? (
              <li>Creator risk flag: <strong className="text-rose-300">{earlyRadar.creatorRisk}</strong></li>
            ) : null}
            {earlyRadar?.holderRisk && earlyRadar.holderRisk !== "PASS" ? (
              <li>Holder concentration flag: <strong className="text-rose-300">{earlyRadar.holderRisk}</strong></li>
            ) : null}
            {hardBlocks.length === 0 && risk === "PASS" ? (
              <li className="text-emerald-400 font-medium">No hard risk blocks triggered.</li>
            ) : null}
          </ul>
        </div>

        {/* WHAT IS UNKNOWN */}
        <div className="bg-gray-950/50 border border-gray-800/70 rounded-lg p-3 space-y-2">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
            ? WHAT IS UNKNOWN / UNMEASURED
          </span>
          <ul className="space-y-1.5 text-gray-400 list-disc list-inside">
            {earlyRadar?.externalCallLeadTimeMs === null ? (
              <li>External caller lead time: UNKNOWN</li>
            ) : null}
            <li>Social / KOL corroboration: ADVISORY ONLY</li>
            <li>LP Token Lock / Authority status: UNVERIFIED</li>
            <li>Real-world live trading PnL: UNPROVEN (PAPER ONLY)</li>
          </ul>
        </div>
      </div>

      {/* REASON CODES BAR */}
      {allReasons.length > 0 ? (
        <div className="pt-2 border-t border-gray-800/60">
          <span className="text-[10px] font-semibold text-gray-400 uppercase block mb-1.5">REASON CODES</span>
          <div className="flex flex-wrap gap-1.5">
            {allReasons.map((code) => (
              <span key={code} className="text-[10px] font-mono bg-gray-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700">
                {code}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function EntryReadinessChecklist({ earlyRadar }: { earlyRadar?: EarlyRadarRecord | null }) {
  const checks = [
    { label: "AlphaScore / EarlyScore Threshold", pass: (earlyRadar?.earlyScore ?? 0) >= 65, detail: earlyRadar?.earlyScore != null ? `${earlyRadar.earlyScore}/100` : "UNAVAILABLE" },
    { label: "Hard Risk Gate", pass: earlyRadar?.riskDisposition === "PASS", detail: earlyRadar?.riskDisposition ?? "UNKNOWN" },
    { label: "Quote / Stream Freshness", pass: earlyRadar?.firstSeenQuality === "FRESH", detail: earlyRadar?.firstSeenQuality ?? "UNKNOWN" },
    { label: "Token Sellability", pass: earlyRadar?.sellability === "PASS", detail: earlyRadar?.sellability ?? "UNKNOWN" },
    { label: "Liquidity Depth (>= $5,000)", pass: (earlyRadar?.liquidityUsd ?? 0) >= 5000, detail: earlyRadar?.liquidityUsd != null ? `$${earlyRadar.liquidityUsd.toLocaleString()}` : "UNKNOWN" },
    { label: "Max Price Impact (<= 300 bps)", pass: earlyRadar?.priceImpactBps != null && earlyRadar.priceImpactBps <= 300, detail: earlyRadar?.priceImpactBps != null ? `${earlyRadar.priceImpactBps} bps` : "UNKNOWN" },
    { label: "Operating Modes Locked", pass: true, detail: "ANALYSIS_ONLY=true, PAPER=true" },
  ];

  const allPass = checks.every(c => c.pass);

  return (
    <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">ENTRY READINESS CHECKLIST</h4>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${allPass ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-gray-800 text-gray-400'}`}>
          {allPass ? "ENTRY READY" : "HARD GATED"}
        </span>
      </div>

      <div className="space-y-2 text-xs">
        {checks.map((c, i) => (
          <div key={i} className="flex items-center justify-between py-1 border-b border-gray-800/40 last:border-0">
            <span className="text-gray-300 flex items-center gap-2">
              <span className={`text-xs ${c.pass ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}`}>
                {c.pass ? '✓' : '✗'}
              </span>
              {c.label}
            </span>
            <span className="font-mono text-[11px] text-gray-400">{c.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidencePanels({ entries }: { entries: TimelineRecord[] }) {
  const top10 = holderMetric(entries, ["top10_hold_percent", "holder_supply_pct", "top10_concentration_pct"]);
  const clustered = holderMetric(entries, ["clustered_supply_pct", "clustered_supply_percent", "holder_cluster_pct"]);
  return (
    <section className="evidence-grid grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6" aria-label="Explainable evidence panels">
      <article className="detail-panel chart-panel lg:col-span-2 bg-gray-900/80 border border-gray-800 rounded-xl p-4">
        <div className="panel-heading flex items-center justify-between mb-4 pb-2 border-b border-gray-800/60">
          <div>
            <p className="eyebrow text-[10px] font-semibold text-emerald-400 tracking-wider">MARKET EVIDENCE</p>
            <h3 className="text-sm font-bold text-gray-100">Event-time metrics</h3>
          </div>
          <small className="text-[10px] text-gray-400 font-mono bg-gray-800 px-2 py-0.5 rounded">ALLOW-LISTED ONLY</small>
        </div>
        <div className="charts-grid grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricChart label="Price" points={pointsFor(entries, METRIC_KEYS.price)} />
          <MetricChart label="Liquidity" points={pointsFor(entries, METRIC_KEYS.liquidity)} />
          <MetricChart label="Net flow" points={netFlowPointsFor(entries)} />
        </div>
      </article>

      <article className="detail-panel holder-panel bg-gray-900/80 border border-gray-800 rounded-xl p-4">
        <p className="eyebrow text-[10px] font-semibold text-amber-400 tracking-wider">HOLDER EVIDENCE</p>
        <h3 className="text-sm font-bold text-gray-100 mb-1">HOLDER CONCENTRATION / CLUSTERS</h3>
        <p className="muted-copy text-[11px] text-gray-400 mb-4">Normalized holder snapshots remain contextual evidence.</p>
        <HolderBar label="TOP 10 SUPPLY" value={top10} />
        <HolderBar label="CLUSTERED SUPPLY" value={clustered} />
      </article>
    </section>
  );
}

function TokenTimeline({ entries }: { entries: TimelineRecord[] }) {
  if (entries.length === 0) {
    return <div className="read-state" role="status"><strong>NO EVIDENCE YET</strong><p>No normalized timeline entries were returned.</p></div>;
  }
  return (
    <div className="timeline-list space-y-3" aria-label="Event-time evidence timeline">
      {entries.map((entry) => (
        <article className="timeline-entry bg-gray-950/60 p-3 rounded-lg border border-gray-800/60 flex flex-col md:flex-row gap-3" key={entry.id}>
          <div className="timeline-entry__time text-xs md:w-48 shrink-0">
            <strong className="text-gray-200 block font-mono">{displayDate(entry.occurredAt)}</strong>
            <small className="text-[10px] text-gray-400 block mt-0.5">OBSERVED {displayDate(entry.observedAt)}</small>
          </div>
          <div className="timeline-entry__body flex-1 space-y-1 text-xs">
            <div className="timeline-entry__heading flex items-center justify-between">
              <strong className="text-cyan-300 font-semibold">{entry.kind}</strong>
              <FreshnessBadge value={entry.qualityState} />
            </div>
            <span className="text-[11px] text-gray-400 block font-mono">SOURCE {entry.sourceId}</span>
            <small className="text-[11px] text-gray-400 block">
              {entry.reasonCodes.length > 0 ? `REASONS ${entry.reasonCodes.join(", ")}` : "NO REASON CODES"}
            </small>
            {entry.provenance.length > 0 ? (
              <div className="provenance-list text-[10px] text-gray-400 font-mono pt-1">
                {entry.provenance.map((provenance, index) => (
                  <small key={`${provenance.sourceId}-${index}`} className="block">
                    PROVIDER {provenance.provider} / SOURCE {provenance.sourceId} / PARSER {provenance.parserVersion}
                  </small>
                ))}
              </div>
            ) : <small className="text-[10px] text-gray-400 font-mono block pt-1">PROVENANCE UNKNOWN</small>}
          </div>
        </article>
      ))}
    </div>
  );
}

function SocialNarrative({ entries }: { entries: TimelineRecord[] }) {
  const selected = entries.filter((entry) => entry.kind.startsWith("social.") || entry.kind.startsWith("narrative."));
  return (
    <section className="detail-panel social-panel bg-gray-900/80 border border-gray-800 rounded-xl p-4 mb-6" aria-labelledby="social-title">
      <div className="panel-heading flex items-center justify-between mb-3">
        <div>
          <p className="eyebrow text-[10px] font-semibold text-purple-400 tracking-wider">CORRELATED CONTEXT</p>
          <h3 id="social-title" className="text-sm font-bold text-gray-100">SOCIAL / NARRATIVE EVIDENCE</h3>
        </div>
        <small className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded uppercase font-semibold">ADVISORY</small>
      </div>
      {selected.length === 0 ? <strong className="text-gray-500 text-xs">UNKNOWN</strong> : (
        <div className="social-list space-y-2">
          {selected.map((entry) => (
            <article className="social-row bg-gray-950/60 p-2.5 rounded border border-gray-800/60 flex items-center justify-between text-xs" key={entry.id}>
              <div>
                <strong className="text-purple-300 block">{entry.kind}</strong>
                <span className="text-gray-300 font-mono text-[11px]">{entry.sourceId}</span>
              </div>
              <div className="text-right text-[10px] text-gray-400">
                <small className="block">PROVIDER {entry.provenance[0]?.provider ?? "UNKNOWN"}</small>
                <small className="block">OBSERVED {displayDate(entry.observedAt)}</small>
                {entry.reasonCodes.length > 0 ? <small className="text-purple-400 font-mono block">REASONS {entry.reasonCodes.join(", ")}</small> : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function TokenDetailView({
  tokenResult,
  timelineResult,
  earlyRadarRecord,
  positionRecord,
  creatorReputationRecord
}: {
  tokenResult: ReadResult<TokenRecord>;
  timelineResult: ReadResult<ReadPage<TimelineRecord>>;
  earlyRadarRecord?: EarlyRadarRecord | null;
  positionRecord?: PositionRecord | null;
  creatorReputationRecord?: CreatorReputationRecord | null;
}) {
  if (!tokenResult.ok) {
    return (
      <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
        <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">TOKEN READ</span>
        <strong className="text-lg text-rose-200 block mb-2">{failureMessage(tokenResult)}</strong>
        <p className="text-sm text-gray-400 mb-4">The token projection could not be safely loaded.</p>
        <Link href="/" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">BACK TO RADAR</Link>
      </div>
    );
  }

  const token = tokenResult.data;
  if (!token) {
    return (
      <div className="read-state p-8 text-center bg-gray-900 border border-gray-800 rounded-xl" role="status">
        <strong className="text-lg text-gray-200 block mb-3">TOKEN NOT FOUND</strong>
        <Link href="/" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">BACK TO RADAR</Link>
      </div>
    );
  }

  if (!timelineResult.ok) {
    return (
      <>
        <Overview token={token} earlyRadar={earlyRadarRecord} />
        <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
          <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">EVIDENCE TIMELINE</span>
          <strong className="text-lg text-rose-200 block mb-2">{failureMessage(timelineResult)}</strong>
          <p className="text-sm text-gray-400">Token metadata is available; evidence remains unavailable.</p>
        </div>
      </>
    );
  }

  const entries = timelineResult.data.items;

  return (
    <div className="space-y-6">
      <Overview token={token} earlyRadar={earlyRadarRecord} />

      <ExplainabilityPanel
        candidate={token.candidate}
        earlyRadar={earlyRadarRecord}
        reasonCodes={token.candidate?.riskReasonCodes ?? []}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <EvidencePanels entries={entries} />

          <section className="detail-panel timeline-panel bg-gray-900/80 border border-gray-800 rounded-xl p-5" aria-labelledby="timeline-title">
            <div className="panel-heading flex items-center justify-between mb-4 pb-2 border-b border-gray-800/60">
              <div>
                <p className="eyebrow text-[10px] font-semibold text-cyan-400 tracking-wider uppercase">NO-LOOKAHEAD EVIDENCE</p>
                <h3 id="timeline-title" className="text-sm font-bold text-gray-100">Evidence timeline</h3>
              </div>
              <small className="text-[10px] font-mono text-gray-400">OCCURRED → OBSERVED → INGESTED</small>
            </div>
            <TokenTimeline entries={entries} />
          </section>

          <SocialNarrative entries={entries} />
        </div>

        <div className="lg:col-span-1 space-y-6">
          <EntryReadinessChecklist earlyRadar={earlyRadarRecord} />

          {/* CREATOR REPUTATION CARD */}
          {creatorReputationRecord ? (
            <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">CREATOR REPUTATION</h4>
                <span className="text-[10px] font-mono text-amber-400">{creatorReputationRecord.reputationClass}</span>
              </div>
              <div className="space-y-2 text-xs text-gray-300">
                <div className="flex justify-between"><span>Launches Total:</span> <strong className="text-gray-100">{creatorReputationRecord.launchesTotal}</strong></div>
                <div className="flex justify-between"><span>Winner Rate:</span> <strong className="text-emerald-400">{(creatorReputationRecord.winnerRate * 100).toFixed(1)}%</strong></div>
                <div className="flex justify-between"><span>Rug Rate:</span> <strong className="text-rose-400">{(creatorReputationRecord.rugRate * 100).toFixed(1)}%</strong></div>
                <div className="flex justify-between"><span>Reputation Score:</span> <strong className="text-amber-300">{creatorReputationRecord.score}/100</strong></div>
              </div>
            </div>
          ) : null}

          {/* PAPER POSITION STATUS */}
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">PAPER POSITION STATUS</h4>
              <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-2 py-0.5 rounded font-mono uppercase">
                {positionRecord ? positionRecord.state : "NO POSITION"}
              </span>
            </div>
            {positionRecord ? (
              <div className="space-y-1.5 text-xs text-gray-300 pt-2 border-t border-gray-800/60">
                <div className="flex justify-between"><span>Entry Price:</span><span className="font-mono">${positionRecord.averageEntry.toFixed(6)}</span></div>
                <div className="flex justify-between"><span>Current Mark:</span><span className="font-mono">${positionRecord.currentMark?.price ? positionRecord.currentMark.price.toFixed(6) : "UNKNOWN"}</span></div>
                <div className="flex justify-between"><span>Realized PnL:</span><span className="font-mono font-semibold text-emerald-400">${positionRecord.realizedPnl.toFixed(2)}</span></div>
                <div className="flex justify-between"><span>Exit Risk Score:</span><span className="font-mono font-semibold text-amber-300">{positionRecord.exitRisk?.score ?? 0}/100</span></div>
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No active paper position currently open for this token.</p>
            )}
          </div>

          {/* RESEARCH ONLY NOTICE */}
          <div className="bg-gray-950/60 border border-gray-800/80 rounded-xl p-4 text-xs">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block mb-1">
              RESEARCH / REPLAY LABELS
            </span>
            <p className="text-gray-400 text-[11px]">
              Future 20x/50x/100x outcome labels are deterministic historical backtest markers only. They are NEVER live predictions or execution guarantees.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
