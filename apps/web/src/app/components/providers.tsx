"use client";

import React from "react";
import Link from "next/link";

import { WorkstationTopBar, MetricCard, SectionHeader, StatusPill } from "./ui-primitives";
import { FreshnessBadge, SafetyBadge } from "./status-badges";
import type {
  ProviderHealthRecord,
  ProviderHealthState,
  ReadPage,
  ReadResult
} from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function quotaSummary(quota: Record<string, unknown>): string {
  const remaining = quota.remaining;
  const limit = quota.limit;
  if (
    typeof remaining === "number" && Number.isFinite(remaining) && remaining >= 0 &&
    typeof limit === "number" && Number.isFinite(limit) && limit >= 0
  ) {
    return `${remaining} remaining / ${limit} limit`;
  }
  return "QUOTA UNKNOWN";
}

function stateClass(state: ProviderHealthState): string {
  return state.toLowerCase();
}

function failureMessage(result: ReadResult<ReadPage<ProviderHealthRecord>>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED": return "PROVIDER HEALTH NOT CONFIGURED";
    case "UNAUTHORIZED": return "PROVIDER HEALTH AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID READ RESPONSE";
    case "UNAVAILABLE": return "PROVIDER HEALTH UNAVAILABLE";
  }
}

function ProviderRow({ record }: { record: ProviderHealthRecord }) {
  const isHealthy = record.state === "HEALTHY";
  const isDegraded = record.state === "DEGRADED";

  return (
    <article className={`provider-card provider-card--${stateClass(record.state)} bg-gray-900/80 border ${isHealthy ? 'border-emerald-900/40' : isDegraded ? 'border-amber-900/50' : 'border-rose-900/50'} rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 transition-all`}>
      <div className="provider-card__identity min-w-[200px]">
        <strong className="text-base font-bold text-gray-100 block">{record.provider}</strong>
        <span className="text-xs text-cyan-400 font-mono block">{record.capability}</span>
        <small className="text-[10px] text-gray-400 font-mono block mt-1">CHECKED {readableDate(record.checkedAt)}</small>
      </div>

      <div className="provider-card__state min-w-[140px]">
        <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">CURRENT STATE</span>
        <strong className={`text-sm font-bold block ${isHealthy ? 'text-emerald-400' : isDegraded ? 'text-amber-400' : 'text-rose-400'}`}>
          {record.state}
        </strong>
        <small className="text-[11px] text-gray-400 block">{record.consecutiveFailures} consecutive failure{record.consecutiveFailures === 1 ? "" : "s"}</small>
      </div>

      <div className="provider-card__metrics min-w-[180px]">
        <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">LATENCY</span>
        <strong className="text-sm font-mono text-gray-200 block">{record.latencyMs === null ? "UNKNOWN" : `${record.latencyMs.toFixed(0)} ms`}</strong>
        <span className="quota-copy text-xs text-gray-400 font-mono block mt-0.5">{quotaSummary(record.quota)}</span>
      </div>

      <div className="provider-card__quality min-w-[140px] text-right">
        {record.freshnessState === null ? (
          <SafetyBadge label="FRESHNESS" value="UNKNOWN" tone="disabled" />
        ) : <FreshnessBadge value={record.freshnessState} />}
        <small className="text-[11px] font-mono text-rose-300 block mt-1">{record.errorClass ? `ERROR ${record.errorClass}` : "NO ERROR CLASS"}</small>
      </div>
    </article>
  );
}

function ProvidersContent({ result }: { result: ReadResult<ReadPage<ProviderHealthRecord>> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
        <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">PROVIDER OBSERVABILITY / READ-ONLY</span>
        <strong className="text-lg text-rose-200 block mb-2">{failureMessage(result)}</strong>
        <p className="text-sm text-gray-400 mb-4">No provider health was inferred from the failed read.</p>
        <Link href="/providers" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">RETRY</Link>
      </div>
    );
  }

  if (result.data.items.length === 0) {
    return (
      <div className="read-state p-8 text-center bg-gray-900 border border-gray-800 rounded-xl" role="status">
        <span className="eyebrow text-xs text-amber-400 font-bold tracking-wider uppercase block mb-1">PROVIDER OBSERVABILITY</span>
        <strong className="text-lg text-gray-200 block mb-2">NO PROVIDER HEALTH EVIDENCE</strong>
        <p className="text-xs text-gray-400">The catalog is empty or not persisted. Empty is not healthy.</p>
      </div>
    );
  }

  return (
    <div className="provider-list space-y-3" aria-label="Provider health records">
      {result.data.items.map((record) => (
        <ProviderRow key={`${record.provider}:${record.capability}`} record={record} />
      ))}
    </div>
  );
}

export function ProvidersDashboard({ result }: { result: ReadResult<ReadPage<ProviderHealthRecord>> }) {
  const items = result.ok ? result.data.items : [];
  const healthyCount = items.filter((p) => p.state === "HEALTHY").length;
  const degradedCount = items.filter((p) => p.state === "DEGRADED").length;
  const downCount = items.filter((p) => p.state === "DOWN" || p.state === "UNKNOWN").length;

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        {/* OPERATIONAL TRUTH HIERARCHY STRIP */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-gray-400 font-bold">OPERATIONAL TRUTH:</span>
            <span className="text-emerald-400">STACK</span>
            <span className="text-gray-600">→</span>
            <span className="text-cyan-400">PRIMARY PROVIDERS</span>
            <span className="text-gray-600">→</span>
            <span className="text-amber-400">LIVE OBSERVATIONS</span>
            <span className="text-gray-600">→</span>
            <span className="text-indigo-400">SHADOW RUN</span>
            <span className="text-gray-600">→</span>
            <span className="text-purple-400">ALPHA EVIDENCE</span>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/operations" className="text-xs text-indigo-400 hover:text-indigo-300 font-sans font-semibold no-underline">
              System Operations →
            </Link>
          </div>
        </div>

        <section className="section-block intelligence-section space-y-6" aria-labelledby="providers-title">
          <div className="section-heading flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800/80">
            <div>
              <p className="eyebrow text-[10px] font-bold text-cyan-400 uppercase tracking-wider m-0">TRANSPORT / QUOTA / FRESHNESS</p>
              <h3 id="providers-title" className="text-2xl font-bold text-gray-100 m-0">Provider health</h3>
              <p className="section-note text-xs text-gray-400 m-0 mt-1">Health is evidence quality, never a positive trade signal.</p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 px-2.5 py-1 rounded">
                ANALYSIS_ONLY=true
              </span>
              <span className="text-xs font-mono bg-cyan-950 text-cyan-300 border border-cyan-800 px-2.5 py-1 rounded">
                PAPER_TRADING=true
              </span>
            </div>
          </div>

          {result.ok && items.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard label="HEALTHY PROVIDERS" value={healthyCount} variant="safe" />
              <MetricCard label="DEGRADED PROVIDERS" value={degradedCount} variant={degradedCount > 0 ? "warning" : "muted"} />
              <MetricCard label="DOWN / UNKNOWN PROVIDERS" value={downCount} variant={downCount > 0 ? "danger" : "muted"} />
            </div>
          )}

          <ProvidersContent result={result} />
        </section>

        <section className="queue-card bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex items-center justify-between" aria-labelledby="provider-boundary-title">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center font-mono font-bold text-sm" aria-hidden="true">
              ⌁
            </div>
            <div>
              <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider m-0">FAIL-CLOSED OBSERVABILITY</p>
              <h3 id="provider-boundary-title" className="text-xs font-bold text-gray-200 m-0">Degradation remains visible</h3>
              <p className="text-[11px] text-gray-400 m-0">Unknown, stale, down or conflicted providers reduce confidence; they never become safe.</p>
            </div>
          </div>
          <SafetyBadge label="DATA" value="ADVISORY" tone="advisory" />
        </section>
      </div>
    </main>
  );
}
