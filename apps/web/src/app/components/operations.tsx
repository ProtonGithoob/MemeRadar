"use client";

import React from "react";
import Link from "next/link";

import { WorkstationTopBar, MetricCard, SectionHeader } from "./ui-primitives";
import { SafetyBadge } from "./status-badges";
import type {
  OperationalProviderRecord,
  OperationsRecord,
  ReadResult
} from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function stateTone(state: OperationsRecord["overallState"]): "safe" | "paper" | "disabled" | "advisory" {
  if (state === "HEALTHY") return "safe";
  if (state === "DEGRADED") return "advisory";
  return "disabled";
}

function quotaSummary(provider: OperationalProviderRecord): string {
  if (provider.quotaRemaining !== null && provider.quotaLimit !== null) {
    return `${provider.quotaRemaining} remaining / ${provider.quotaLimit} limit`;
  }
  return "QUOTA UNKNOWN";
}

function costSummary(provider: OperationalProviderRecord): string {
  if (provider.costTodayUsd !== null && provider.costBudgetUsd !== null) {
    return `$${provider.costTodayUsd.toFixed(2)} / $${provider.costBudgetUsd.toFixed(2)} budget`;
  }
  return "COST UNKNOWN";
}

function counterValue(metrics: Record<string, unknown>, name: string): number {
  const counters = metrics.counters;
  if (typeof counters !== "object" || counters === null || Array.isArray(counters)) return 0;
  const value = (counters as Record<string, unknown>)[name];
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

function nestedRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function earlyCounterValue(metrics: Record<string, unknown>, name: string): number {
  const counters = nestedRecord(metrics.counters);
  const value = counters?.[name];
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : 0;
}

function earlyLatencySummary(metrics: Record<string, unknown>): string {
  const latencies = nestedRecord(metrics.latencies);
  const decisionLatency = nestedRecord(latencies?.first_seen_to_decision_ms);
  if (decisionLatency === null) return "UNVERIFIED LATENCY";
  const evidenceClass = typeof metrics.evidence_class === "string" ? metrics.evidence_class : "UNVERIFIED";
  const summary = nestedRecord(decisionLatency[evidenceClass]) ??
    Object.values(decisionLatency).map(nestedRecord).find((item) => item !== null) ?? null;
  if (summary === null) return "UNVERIFIED LATENCY";
  const p50 = summary.p50_ms;
  const p95 = summary.p95_ms;
  if (typeof p50 !== "number" || typeof p95 !== "number") return "UNVERIFIED LATENCY";
  return `${p50} ms p50 / ${p95} ms p95`;
}

function earlyEvidenceSummary(metrics: Record<string, unknown>): string {
  const evidence = typeof metrics.evidence_class === "string" ? metrics.evidence_class : "UNVERIFIED";
  const method = typeof metrics.measurement_method === "string" ? metrics.measurement_method : "unknown";
  return `${evidence} / ${method}`;
}

function failureMessage(result: ReadResult<OperationsRecord>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED": return "OPERATIONS OBSERVABILITY NOT CONFIGURED";
    case "UNAUTHORIZED": return "OPERATIONS OBSERVABILITY AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID OPERATIONS READ RESPONSE";
    case "UNAVAILABLE": return "OPERATIONS OBSERVABILITY UNAVAILABLE";
  }
}

function ProviderOperationRow({ provider }: { provider: OperationalProviderRecord }) {
  const isHealthy = provider.state === "HEALTHY";
  const isDegraded = provider.state === "DEGRADED";

  return (
    <article className={`operations-provider operations-provider--${provider.state.toLowerCase()} bg-gray-950/60 p-4 rounded-xl border ${isHealthy ? 'border-gray-800' : 'border-amber-900/50'} flex flex-wrap items-center justify-between gap-4`}>
      <div className="min-w-[180px]">
        <strong className="text-base font-bold text-gray-100 block">{provider.provider}</strong>
        <span className="text-xs font-mono text-cyan-400 block">{provider.capability}</span>
        <small className="text-[10px] text-gray-400 font-mono block mt-1">CHECKED {readableDate(provider.checkedAt)}</small>
      </div>

      <div className="min-w-[150px]">
        <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">STATE / SLO</span>
        <strong className={`text-sm font-bold block ${isHealthy ? 'text-emerald-400' : 'text-amber-400'}`}>
          {provider.state} / {provider.sloState}
        </strong>
        <small className="text-[11px] font-mono text-amber-300 block mt-0.5">{provider.reasonCodes.length > 0 ? provider.reasonCodes.join(", ") : "NO DEGRADATION REASON"}</small>
      </div>

      <div className="min-w-[200px]">
        <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">QUOTA</span>
        <strong className="text-xs font-mono text-gray-200 block">{quotaSummary(provider)}</strong>
        <small className="text-[11px] text-gray-400 block font-mono mt-0.5">{provider.latencyMs === null ? "LATENCY UNKNOWN" : `${provider.latencyMs.toFixed(0)} ms latest`}</small>
        <small className="text-[11px] text-amber-400 font-mono block">{costSummary(provider)}</small>
      </div>
    </article>
  );
}

function OperationsContent({ result }: { result: ReadResult<OperationsRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
        <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">OPERATIONS / READ-ONLY</span>
        <strong className="text-lg text-rose-200 block mb-2">{failureMessage(result)}</strong>
        <p className="text-sm text-gray-400 mb-4">No operational health was inferred from the failed read.</p>
        <Link href="/operations" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">RETRY</Link>
      </div>
    );
  }

  const { data } = result;
  return (
    <div className="space-y-6">
      <div className="operations-summary grid grid-cols-1 md:grid-cols-3 gap-4" aria-label="Operations summary">
        <div className="detail-panel bg-gray-900/80 p-4 rounded-xl border border-gray-800 space-y-2">
          <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">OVERALL STATE</span>
          <SafetyBadge label="OPERATIONS" value={data.overallState} tone={stateTone(data.overallState)} />
          <small className="text-[10px] text-gray-400 font-mono block">AS OF {readableDate(data.asOf)}</small>
        </div>

        <div className="detail-panel bg-gray-900/80 p-4 rounded-xl border border-gray-800 space-y-2">
          <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">PROVIDER SLO EVIDENCE</span>
          <SafetyBadge
            label="SLO"
            value={data.sloState}
            tone={data.sloState === "MEASURED" ? "paper" : "disabled"}
          />
          <small className="text-[10px] text-gray-400 font-mono block">{data.measurementMethod} / {data.policyVersion}</small>
        </div>

        <div className="detail-panel bg-gray-900/80 p-4 rounded-xl border border-gray-800 space-y-2">
          <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">ACTIVE ALERTS</span>
          <strong className="operations-big-value text-2xl font-bold font-mono text-amber-400 block">{data.alerts.length}</strong>
          <small className="text-[10px] text-gray-400 block">Operational alerts are evidence quality, never trade signals.</small>
        </div>
      </div>

      <section className="section-block bg-gray-900/80 p-5 rounded-xl border border-gray-800 space-y-4" aria-labelledby="operations-providers-title">
        <div className="section-heading pb-2 border-b border-gray-800">
          <p className="eyebrow text-[10px] font-bold text-cyan-400 uppercase tracking-wider m-0">PROVIDER / QUOTA / LATENCY</p>
          <h3 id="operations-providers-title" className="text-base font-bold text-gray-100 m-0">Provider operations</h3>
          <p className="section-note text-xs text-gray-400 m-0 mt-0.5">Synthetic or missing measurements remain unverified.</p>
        </div>

        {data.providers.length === 0 ? (
          <div className="read-state p-6 text-center bg-gray-950 border border-gray-800 rounded-lg" role="status">
            <strong className="text-gray-200 text-sm block mb-1">NO OPERATIONAL PROVIDER EVIDENCE</strong>
            <p className="text-xs text-gray-400">Empty is not healthy; configure a read-only provider health projection.</p>
          </div>
        ) : (
          <div className="operations-provider-list space-y-3">
            {data.providers.map((provider) => (
              <ProviderOperationRow key={`${provider.provider}:${provider.capability}`} provider={provider} />
            ))}
          </div>
        )}
      </section>

      <section className="section-block bg-gray-900/80 p-5 rounded-xl border border-gray-800 space-y-4" aria-labelledby="operations-alerts-title">
        <div className="section-heading pb-2 border-b border-gray-800">
          <p className="eyebrow text-[10px] font-bold text-amber-400 uppercase tracking-wider m-0">DEGRADATION / BACKPRESSURE / RECOVERY</p>
          <h3 id="operations-alerts-title" className="text-base font-bold text-gray-100 m-0">Active operational alerts</h3>
        </div>

        {data.alerts.length === 0 ? (
          <div className="read-state p-6 text-center bg-gray-950 border border-gray-800 rounded-lg" role="status">
            <strong className="text-emerald-400 text-sm block mb-1">NO ACTIVE OPERATIONAL ALERTS</strong>
            <p className="text-xs text-gray-400">Healthy telemetry is neutral and does not increase AlphaScore.</p>
          </div>
        ) : (
          <div className="operations-alert-list space-y-3">
            {data.alerts.map((alert) => (
              <article className={`operations-alert operations-alert--${alert.severity.toLowerCase()} bg-gray-950 p-3.5 rounded-lg border border-amber-900/50 flex items-start justify-between text-xs`} key={alert.dedupeKey}>
                <div className="space-y-1">
                  <strong className="text-amber-300 font-mono block">{alert.code}</strong>
                  <span className="text-gray-400 font-mono block">{alert.provider ?? "SYSTEM"}{alert.capability ? ` / ${alert.capability}` : ""}</span>
                </div>
                <div className="text-right space-y-1">
                  <span className="card-label text-[10px] font-bold text-amber-400 uppercase tracking-wider block">{alert.severity}</span>
                  <p className="text-gray-200 m-0">{alert.message}</p>
                  <small className="text-[10px] font-mono text-gray-400 block">{alert.reasonCodes.join(", ") || "NO REASON CODE"}</small>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="section-block bg-gray-900/80 p-5 rounded-xl border border-gray-800 space-y-4" aria-labelledby="operations-early-title">
        <div className="section-heading pb-2 border-b border-gray-800">
          <p className="eyebrow text-[10px] font-bold text-cyan-400 uppercase tracking-wider m-0">ULTRA-EARLY / SHADOW OBSERVABILITY</p>
          <h3 id="operations-early-title" className="text-base font-bold text-gray-100 m-0">Ultra-early detection</h3>
          <p className="section-note text-xs text-gray-400 m-0 mt-0.5">Local fixture latency is evidence, not a production SLO.</p>
        </div>

        <div className="operations-counter-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="detail-panel bg-gray-950 p-3.5 rounded-lg border border-gray-800">
            <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">EVIDENCE CLASS / METHOD</span>
            <strong className="text-sm font-mono text-gray-200 block mt-1">{earlyEvidenceSummary(data.earlyDetection)}</strong>
            <small className="text-[10px] font-mono text-cyan-400 block mt-1">{earlyLatencySummary(data.earlyDetection)}</small>
          </div>

          <div className="detail-panel bg-gray-950 p-3.5 rounded-lg border border-gray-800">
            <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">CANDIDATES / ENTRY READY</span>
            <strong className="operations-big-value text-xl font-mono text-emerald-400 block mt-1">
              {earlyCounterValue(data.earlyDetection, "candidates_detected")} / {earlyCounterValue(data.earlyDetection, "entry_ready")}
            </strong>
            <small className="text-[10px] text-gray-400 block mt-1">ENTRY_READY RATE IS OBSERVATIONAL ONLY</small>
          </div>

          <div className="detail-panel bg-gray-950 p-3.5 rounded-lg border border-gray-800">
            <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">SHADOW FILLS</span>
            <strong className="operations-big-value text-xl font-mono text-cyan-400 block mt-1">
              {earlyCounterValue(data.earlyDetection, "shadow_fills")}
            </strong>
            <small className="text-[10px] text-gray-400 block mt-1">PAPER PATH ONLY</small>
          </div>

          <div className="detail-panel bg-gray-950 p-3.5 rounded-lg border border-gray-800">
            <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">EXECUTION BOUNDARY</span>
            <strong className="text-xs font-mono text-rose-400 block mt-1">AUTO EXECUTION: LOCKED</strong>
            <small className="text-[10px] text-gray-400 block mt-1">NO SIGNER OR LIVE SUBMISSION PATH</small>
          </div>
        </div>
      </section>

      <section className="section-block bg-gray-900/80 p-5 rounded-xl border border-gray-800 space-y-4" aria-labelledby="operations-metrics-title">
        <div className="section-heading pb-2 border-b border-gray-800">
          <p className="eyebrow text-[10px] font-bold text-purple-400 uppercase tracking-wider m-0">BOUNDED TELEMETRY</p>
          <h3 id="operations-metrics-title" className="text-base font-bold text-gray-100 m-0">Reliability counters</h3>
        </div>

        <div className="operations-counter-grid grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            ["QUEUE SATURATION", "queue_saturations"],
            ["OUTBOX DEAD LETTERS", "outbox_dead_letters"],
            ["RECOVERY FAILURES", "recovery_failures"],
            ["STREAM RECONNECTS", "stream_reconnects"]
          ].map(([label, name]) => (
            <div className="detail-panel bg-gray-950 p-3.5 rounded-lg border border-gray-800" key={name}>
              <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">{label}</span>
              <strong className="operations-big-value text-xl font-mono text-gray-200 block mt-1">{counterValue(data.metrics, name)}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function OperationsDashboard({ result }: { result: ReadResult<OperationsRecord> }) {
  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        <section className="section-block intelligence-section space-y-6" aria-labelledby="operations-title">
          <div className="section-heading flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800/80">
            <div>
              <p className="eyebrow text-[10px] font-bold text-cyan-400 uppercase tracking-wider m-0">OBSERVABILITY / OPERATIONS / READ-ONLY</p>
              <h3 id="operations-title" className="text-2xl font-bold text-gray-100 m-0">Operations</h3>
              <p className="section-note text-xs text-gray-400 m-0 mt-1">Operational health is evidence quality, never a positive trade signal.</p>
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

          <OperationsContent result={result} />
        </section>

        <section className="queue-card bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex items-center justify-between" aria-labelledby="operations-boundary-title">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center font-mono font-bold text-sm" aria-hidden="true">
              ⌁
            </div>
            <div>
              <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider m-0">PROTECTED MODES</p>
              <h3 id="operations-boundary-title" className="text-xs font-bold text-gray-200 m-0">Analysis-only operations</h3>
              <p className="text-[11px] text-gray-400 m-0">Provider degradation, queue pressure and alert failures stay visible without changing score or execution state.</p>
            </div>
          </div>
          <SafetyBadge label="MODE" value="ANALYSIS ONLY" tone="safe" />
        </section>
      </div>
    </main>
  );
}
