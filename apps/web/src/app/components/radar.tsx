"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  PageShell,
  MetricCard,
  StatusPill,
  RiskChip,
  FreshnessIndicator,
  ScoreGauge,
  SectionHeader,
  DataTable,
  EmptyState,
} from "./ui-primitives";
import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge,
} from "./status-badges";
import { UltraEarlyPanel } from "./ultra-early";

import type {
  CandidateRecord,
  EarlyRadarRecord,
  OperationsRecord,
  PositionRecord,
  ProviderHealthRecord,
  RadarFilters,
  ReadPage,
  ReadResult,
} from "../lib/read-api";

const operatingModes = [
  {
    label: "ANALYSIS ONLY",
    value: "Enabled",
    detail: "Evidence collection remains on.",
    tone: "safe",
  },
  {
    label: "PAPER TRADING",
    value: "Enabled",
    detail: "Simulated outcomes only.",
    tone: "paper",
  },
  {
    label: "MANUAL EXECUTION",
    value: "Disabled",
    detail: "Operator approval path is locked.",
    tone: "disabled",
  },
  {
    label: "AUTO EXECUTION",
    value: "Disabled",
    detail: "No autonomous orders are possible.",
    tone: "disabled",
  },
] as const;

export function ProtectedShell() {
  return (
    <>
      <section className="hero hidden" aria-labelledby="hero-title">
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

      <section className="section-block hidden" aria-labelledby="modes-title">
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
  "CLOSED",
] as const;

const riskStates = ["PASS", "WARN", "BLOCK", "UNKNOWN"] as const;

function shortIdentity(value: string, visible = 6): string {
  if (!value || value.length <= visible * 2 + 1) return value || "";
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function readableDate(value: string): string {
  if (!value) return "UNKNOWN";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString() : "UNKNOWN";
}

function formatAge(discoveredAt: string): string {
  if (!discoveredAt) return "UNKNOWN";
  const diff = Date.now() - new Date(discoveredAt).getTime();
  if (isNaN(diff) || diff < 0) return "Just now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
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

function Filters({ filters }: { filters: RadarFilters }) {
  return (
    <form className="radar-filters border border-gray-800 rounded-xl bg-gray-900/60 p-4 mb-4" method="get" action="/" aria-label="Radar filters">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-mono text-[10px] text-gray-400 font-bold uppercase">State</span>
          <select
            name="state"
            defaultValue={filters.state ?? ""}
            aria-label="State"
            className="bg-gray-950 border border-gray-700 rounded p-2 font-mono text-gray-200 text-xs"
          >
            <option value="">All states</option>
            {candidateStates.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-mono text-[10px] text-gray-400 font-bold uppercase">Risk</span>
          <select
            name="risk_disposition"
            defaultValue={filters.riskDisposition ?? ""}
            aria-label="Risk"
            className="bg-gray-950 border border-gray-700 rounded p-2 font-mono text-gray-200 text-xs"
          >
            <option value="">All risk states</option>
            {riskStates.map((risk) => (
              <option key={risk} value={risk}>
                {risk}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-mono text-[10px] text-gray-400 font-bold uppercase">Minimum score</span>
          <input
            name="min_score"
            type="number"
            min="0"
            max="100"
            step="1"
            inputMode="numeric"
            defaultValue={filters.minScore ?? ""}
            aria-label="Minimum score"
            className="bg-gray-950 border border-gray-700 rounded p-2 font-mono text-gray-200 text-xs"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            className="filter-submit flex-1 px-3 py-2 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-400 font-mono text-xs font-bold hover:bg-emerald-900 transition-colors"
            type="submit"
          >
            APPLY FILTERS
          </button>
          <Link
            className="filter-reset px-3 py-2 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-xs font-bold no-underline text-center"
            href="/"
          >
            RESET
          </Link>
        </div>
      </div>
    </form>
  );
}

export function RadarDashboard({
  filters,
  result,
  earlyResult,
  opsResult,
  providerHealthResult,
  positionsResult,
}: {
  filters: RadarFilters;
  result: ReadResult<ReadPage<CandidateRecord>>;
  earlyResult?: ReadResult<ReadPage<EarlyRadarRecord>>;
  opsResult?: ReadResult<OperationsRecord>;
  providerHealthResult?: ReadResult<ReadPage<ProviderHealthRecord>>;
  positionsResult?: ReadResult<ReadPage<PositionRecord>>;
}) {
  const [searchQuery, setSearchQuery] = useState<string>("");

  const candidates = result.ok ? result.data.items : [];
  const earlyRadarItems = earlyResult?.ok ? earlyResult.data.items : [];
  const providerHealth = providerHealthResult?.ok ? providerHealthResult.data.items : [];
  const opsData = opsResult?.ok ? opsResult.data : null;

  const paperPositionMints = useMemo(() => {
    const items = positionsResult?.ok ? positionsResult.data.items : [];
    const set = new Set<string>();
    items.forEach((p) => {
      if (p.mintAddress) set.add(p.mintAddress);
    });
    return set;
  }, [positionsResult]);

  const funnelCounts = useMemo(() => {
    const counts = {
      WATCH: 0,
      EARLY_WATCH: 0,
      STRONG_SETUP: 0,
      HIGH_CONFLUENCE: 0,
      ENTRY_READY: 0,
    };
    if (earlyResult?.ok) {
      earlyResult.data.items.forEach((item) => {
        const st = item.earlyState;
        if (st in counts) {
          counts[st as keyof typeof counts]++;
        }
      });
    }
    return counts;
  }, [earlyResult]);

  const heliusHealth = providerHealth.find((p) => p.provider.toLowerCase().includes("helius"));
  const birdeyeHealth = providerHealth.find((p) => p.provider.toLowerCase().includes("birdeye"));

  const filteredCandidates = useMemo(() => {
    const rawList = result.ok ? result.data.items : [];
    let list = [...rawList];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (c) =>
          c.symbol?.toLowerCase().includes(q) ||
          c.name?.toLowerCase().includes(q) ||
          c.mintAddress.toLowerCase().includes(q)
      );
    }
    return list;
  }, [result, searchQuery]);

  return (
    <PageShell>
      {/* Product Identity & Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-gray-900/60 p-4 rounded-xl border border-gray-800">
        <div>
          <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-emerald-400 m-0">
            EVIDENCE BEFORE EXECUTION &bull; COMMAND CENTER
          </p>
          <h1 className="text-2xl font-black tracking-tight text-gray-100 m-0">MemeRadar</h1>
          <p className="text-xs text-gray-400 mt-1 m-0">
            Real-time Solana memecoin alpha discovery, risk filtering, and paper trade intelligence.
          </p>
        </div>

        {/* Operating Invariants & Safety Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill label="Operating Mode" value="ANALYSIS ONLY" variant="safe" />
          <StatusPill label="Execution Desk" value="PAPER TRADING" variant="paper" />
          <StatusPill label="Manual Exec" value="Disabled" variant="muted" />
          <StatusPill label="Auto Exec" value="Disabled" variant="muted" />
          <div className="badge-row flex items-center gap-2">
            <SafetyBadge label="LIVE DATA" value="READ ONLY" tone="disabled" />
            <SafetyBadge label="ADVISORY OUTPUT" value="ONLY" tone="advisory" />
          </div>
        </div>
      </div>

      {/* Market & Operational Readiness Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard
          label="Stack Status"
          value={opsData?.overallState === "HEALTHY" ? "STACK_READY" : "STACK_OFFLINE"}
          subtext="Postgres & Redis Stack"
          variant={opsData?.overallState === "HEALTHY" ? "safe" : "warning"}
        />
        <MetricCard
          label="Provider Readiness"
          value={
            heliusHealth?.state === "HEALTHY" && birdeyeHealth?.state === "HEALTHY"
              ? "PROVIDERS_READY"
              : "BLOCKED_EXTERNAL"
          }
          subtext="Helius & Birdeye Adapters"
          variant={
            heliusHealth?.state === "HEALTHY" && birdeyeHealth?.state === "HEALTHY"
              ? "safe"
              : "danger"
          }
        />
        <MetricCard
          label="Shadow Stream"
          value={
            heliusHealth?.state === "HEALTHY"
              ? "LIVE_SHADOW_COLLECTION_ACTIVE"
              : "NOT_ACTIVE"
          }
          subtext="Real-time Solana Events"
          variant={heliusHealth?.state === "HEALTHY" ? "safe" : "warning"}
        />
        <MetricCard
          label="Helius RPC Stream"
          value={heliusHealth?.state || "UNKNOWN"}
          subtext={
            heliusHealth?.latencyMs !== null && heliusHealth?.latencyMs !== undefined
              ? `${heliusHealth.latencyMs}ms latency`
              : "STREAM DISABLED"
          }
          variant={heliusHealth?.state === "HEALTHY" ? "safe" : "warning"}
        />
        <MetricCard
          label="Birdeye REST"
          value={birdeyeHealth?.state || "UNKNOWN"}
          subtext={
            birdeyeHealth?.latencyMs !== null && birdeyeHealth?.latencyMs !== undefined
              ? `${birdeyeHealth.latencyMs}ms latency`
              : "STREAM DISABLED"
          }
          variant={birdeyeHealth?.state === "HEALTHY" ? "safe" : "warning"}
        />
        <MetricCard
          label="Active Candidates"
          value={candidates.length}
          subtext={`${paperPositionMints.size} paper positions`}
          variant="info"
        />
      </div>

      {/* Early Alpha Funnel Bar */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-gray-400">
            Early Signal Funnel
          </span>
          <span className="text-[11px] text-gray-500 font-mono">
            {earlyRadarItems.length} ultra-early observations active
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <div className="bg-gray-950/80 border border-gray-800 rounded-lg p-2.5 text-center">
            <span className="text-[10px] font-mono text-gray-400 block uppercase">WATCH</span>
            <strong className="text-base font-mono text-gray-200">{funnelCounts.WATCH}</strong>
          </div>
          <div className="bg-gray-950/80 border border-gray-800 rounded-lg p-2.5 text-center">
            <span className="text-[10px] font-mono text-cyan-400 block uppercase">EARLY WATCH</span>
            <strong className="text-base font-mono text-cyan-300">{funnelCounts.EARLY_WATCH}</strong>
          </div>
          <div className="bg-gray-950/80 border border-gray-800 rounded-lg p-2.5 text-center">
            <span className="text-[10px] font-mono text-blue-400 block uppercase">STRONG SETUP</span>
            <strong className="text-base font-mono text-blue-300">{funnelCounts.STRONG_SETUP}</strong>
          </div>
          <div className="bg-gray-950/80 border border-gray-800 rounded-lg p-2.5 text-center">
            <span className="text-[10px] font-mono text-purple-400 block uppercase">HIGH CONFLUENCE</span>
            <strong className="text-base font-mono text-purple-300">{funnelCounts.HIGH_CONFLUENCE}</strong>
          </div>
          <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-lg p-2.5 text-center">
            <span className="text-[10px] font-mono text-emerald-400 block uppercase font-bold">ENTRY READY</span>
            <strong className="text-base font-mono text-emerald-300">{funnelCounts.ENTRY_READY}</strong>
          </div>
        </div>
      </div>

      {/* Radar Candidates Section */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-800 pb-3">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-gray-400 m-0">
              RANKED OBSERVATIONS / READ-ONLY
            </p>
            <h2 id="radar-title" className="text-xl font-bold text-gray-100 m-0">Radar</h2>
          </div>
          <Link
            href="/ultra-early"
            className="px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-xs font-mono font-semibold text-emerald-400 hover:bg-emerald-900/80 transition-colors no-underline"
          >
            Ultra Early &rarr;
          </Link>
        </div>

        <Filters filters={filters} />

        {!result.ok ? (
          <div className="read-state read-state--error p-6 rounded-xl border border-rose-900/50 bg-rose-950/20 text-rose-300 text-center" role="status">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-rose-400 block mb-1">
              READ-ONLY BOUNDARY
            </span>
            <strong className="text-lg block mb-2">{resultMessage(result)}</strong>
            <p className="text-xs text-rose-400/80 mb-4">
              No candidate data was substituted. Retry after the read dependency is available.
            </p>
            <Link href="/" className="px-4 py-2 rounded bg-rose-900/60 hover:bg-rose-800 text-xs font-mono font-bold text-rose-100 no-underline inline-block">
              RETRY
            </Link>
          </div>
        ) : filteredCandidates.length === 0 ? (
          <div className="read-state p-8 rounded-xl border border-dashed border-gray-800 bg-gray-950/40 text-center" role="status">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-gray-500 block mb-1">
              RADAR QUEUE
            </span>
            <strong className="text-base text-gray-300 block mb-2">NO CANDIDATES MATCH FILTERS</strong>
            <p className="text-xs text-gray-500 m-0">The read API returned an empty ranked page. No sample candidate is shown.</p>
          </div>
        ) : (
          <div className="hidden md:block">
            <DataTable
              data={filteredCandidates}
              keyExtractor={(item) => item.id}
              columns={[
                {
                  key: "token",
                  header: "Token Identity",
                  render: (c) => (
                    <div className="flex flex-col">
                      <Link
                        href={`/tokens/${c.tokenId}`}
                        className="font-bold text-emerald-400 hover:underline font-mono text-xs"
                      >
                        {c.symbol || c.name || shortIdentity(c.mintAddress)}
                      </Link>
                      <span className="text-[10px] text-gray-500 font-mono">
                        {shortIdentity(c.mintAddress, 8)}
                      </span>
                    </div>
                  ),
                },
                {
                  key: "age",
                  header: "Age / Discovered",
                  render: (c) => (
                    <div className="flex flex-col">
                      <span className="font-mono text-xs text-gray-200">{formatAge(c.discoveredAt)}</span>
                      <span className="text-[10px] text-gray-500 font-mono">{readableDate(c.discoveredAt)}</span>
                    </div>
                  ),
                },
                {
                  key: "state",
                  header: "Decision State",
                  render: (c) => (
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-gray-800 text-gray-200 border border-gray-700">
                        {c.state}
                      </span>
                      {paperPositionMints.has(c.mintAddress) && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-950 text-amber-400 border border-amber-500/30">
                          PAPER
                        </span>
                      )}
                    </div>
                  ),
                },
                {
                  key: "score",
                  header: "Alpha Score",
                  render: (c) => <ScoreBadge value={c.score} />,
                },
                {
                  key: "risk",
                  header: "Risk & Quality",
                  render: (c) => (
                    <div className="flex items-center gap-2">
                      <RiskBadge value={c.riskDisposition} />
                      <FreshnessBadge value={c.riskQualityState} />
                    </div>
                  ),
                },
                {
                  key: "reasons",
                  header: "Top Reason Codes",
                  render: (c) => (
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {c.riskReasonCodes.slice(0, 2).map((code) => (
                        <span
                          key={code}
                          className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-gray-950 text-gray-400 border border-gray-800"
                        >
                          {code}
                        </span>
                      ))}
                      {c.riskReasonCodes.length > 2 && (
                        <span className="text-[9px] font-mono text-gray-500">
                          +{c.riskReasonCodes.length - 2} more
                        </span>
                      )}
                    </div>
                  ),
                },
                {
                  key: "action",
                  header: "Inspect",
                  render: (c) => (
                    <Link
                      href={`/tokens/${c.tokenId}`}
                      className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 font-mono text-[11px] no-underline transition-colors"
                    >
                      Inspect &rarr;
                    </Link>
                  ),
                },
              ]}
            />
          </div>
        )}
      </div>

      {/* Ultra Early Workspace Component */}
      {earlyResult && <UltraEarlyPanel result={earlyResult} />}

      {/* Queue Card Operator Boundary Footer */}
      <section className="queue-card rounded-xl border border-gray-800 bg-gray-900/40 p-4 flex flex-wrap items-center justify-between gap-4" aria-labelledby="queue-title">
        <div className="flex items-center gap-3">
          <div className="queue-card__icon w-8 h-8 rounded-full bg-emerald-950 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-sm" aria-hidden="true">
            ◎
          </div>
          <div>
            <p className="eyebrow text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-400 m-0">
              OPERATOR BOUNDARY / ADVISORY
            </p>
            <h3 id="queue-title" className="text-sm font-bold text-gray-200 m-0">
              No browser-side execution controls
            </h3>
            <p className="text-xs text-gray-400 m-0">
              Read data, provider labels and narratives cannot authorize an order.
            </p>
          </div>
        </div>
        <span className="queue-card__state px-3 py-1 rounded-full text-[10px] font-mono font-bold border border-emerald-500/40 text-emerald-400 bg-emerald-950/40">
          NO LIVE ORDERS
        </span>
      </section>
    </PageShell>
  );
}
