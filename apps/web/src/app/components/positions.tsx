"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";

import { WorkstationTopBar, SectionHeader, MetricCard, StatusPill, ScoreGauge, RiskChip } from "./ui-primitives";
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
    <div className="position-panel position-panel--mark bg-gray-950/60 p-3.5 rounded-lg border border-gray-800/70 space-y-2">
      <div className="panel-heading flex items-center justify-between">
        <div>
          <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">OBSERVED MARK</span>
          <h4 className="text-base font-bold font-mono text-gray-100 m-0">{mark ? number(mark.price, 6) : "UNKNOWN"}</h4>
        </div>
        <FreshnessBadge value={mark?.qualityState ?? "UNKNOWN"} />
      </div>
      {mark ? (
        <dl className="position-meta grid grid-cols-2 gap-1.5 text-xs text-gray-300 pt-2 border-t border-gray-800/60 m-0">
          <div><dt className="text-[10px] text-gray-400 uppercase">PROVIDER</dt><dd className="font-semibold">{mark.provider}</dd></div>
          <div><dt className="text-[10px] text-gray-400 uppercase">SOURCE</dt><dd className="font-mono" title={mark.sourceId}>{shortIdentity(mark.sourceId, 14)}</dd></div>
          <div><dt className="text-[10px] text-gray-400 uppercase">OBSERVED</dt><dd className="font-mono text-[11px]">{readableDate(mark.observedAt)}</dd></div>
          <div><dt className="text-[10px] text-gray-400 uppercase">PARSER</dt><dd className="font-mono">{mark.parserVersion}</dd></div>
        </dl>
      ) : <p className="muted-copy text-xs text-gray-400 italic m-0 pt-1">No market mark was returned. Current value and unrealized PnL remain UNKNOWN.</p>}
    </div>
  );
}

function PositionPerformance({ position }: { position: PositionRecord }) {
  const performance = position.performance;
  return (
    <div className="position-panel bg-gray-950/60 p-3.5 rounded-lg border border-gray-800/70 space-y-2">
      <div className="panel-heading flex items-center justify-between">
        <div>
          <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block">DERIVED PERFORMANCE</span>
          <h4 className="text-base font-bold font-mono text-emerald-400 m-0">{signed(performance.totalPnl)} QUOTE PNL</h4>
        </div>
        <small className="text-[10px] font-mono text-gray-400">AS OF {readableDate(performance.asOf)}</small>
      </div>
      <div className="position-metric-grid grid grid-cols-2 gap-2 text-xs pt-2 border-t border-gray-800/60">
        <div><span className="text-[10px] text-gray-400 block uppercase">UNREALIZED</span><strong className="font-mono text-gray-200">{signed(performance.unrealizedPnl)}</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">REALIZED</span><strong className="font-mono text-gray-200">{signed(performance.realizedPnl)}</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">RETURN</span><strong className="font-mono text-gray-200">{performance.returnRatio === null ? "UNKNOWN" : `${signed(performance.returnRatio * 100)}%`}</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">MFE / MAE</span><strong className="font-mono text-gray-200">{signed(performance.mfe)} / {signed(performance.mae)}</strong></div>
      </div>
      <div className="pt-1 flex justify-end">
        <FreshnessBadge value={performance.qualityState} />
      </div>
    </div>
  );
}

function ExitRisk({ position }: { position: PositionRecord }) {
  const risk = position.exitRisk;
  if (risk === null) {
    return (
      <div className="position-panel bg-gray-950/60 p-3.5 rounded-lg border border-gray-800/70">
        <span className="card-label text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">EXIT RISK</span>
        <p className="muted-copy text-xs text-gray-400 italic m-0">No exit evaluation is available.</p>
      </div>
    );
  }
  return (
    <div className="position-panel position-panel--risk bg-gray-950/60 p-3.5 rounded-lg border border-amber-900/40 space-y-2">
      <div className="panel-heading flex items-center justify-between">
        <div>
          <span className="card-label text-[10px] font-bold text-amber-400 uppercase tracking-wider block">ADVISORY EXIT RISK</span>
          <h4 className="text-base font-bold font-mono text-amber-300 m-0">{risk.action} / {Math.round(risk.exitFraction * 100)}%</h4>
        </div>
        <FreshnessBadge value={risk.qualityState} />
      </div>
      <div className="position-metric-grid grid grid-cols-2 gap-2 text-xs pt-2 border-t border-gray-800/60">
        <div><span className="text-[10px] text-gray-400 block uppercase">RISK SCORE</span><strong className="font-mono text-amber-300">{number(risk.score)}</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">CONFIDENCE</span><strong className="font-mono text-gray-200">{Math.round(risk.confidence * 100)}%</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">EVALUATED</span><strong className="font-mono text-[11px] text-gray-300">{readableDate(risk.evaluatedAt)}</strong></div>
        <div><span className="text-[10px] text-gray-400 block uppercase">RULES</span><strong className="font-mono text-amber-300">{risk.triggeredRules.length ? risk.triggeredRules.join(", ") : "NONE"}</strong></div>
      </div>
      <p className="position-reasons text-xs text-gray-400 m-0 pt-1 border-t border-gray-800/40">
        <span className="font-semibold text-gray-300">REASONS</span> {risk.reasonCodes.length ? risk.reasonCodes.join(", ") : "UNKNOWN"}
      </p>
      <p className="position-reasons text-xs text-gray-400 m-0">
        <span className="font-semibold text-gray-300">EVIDENCE</span> {risk.evidenceRefs.length ? risk.evidenceRefs.join(", ") : "UNKNOWN"}
      </p>
    </div>
  );
}

function ClosedTrade({ position }: { position: PositionRecord }) {
  const trade = position.closedTrade;
  if (trade === null) return null;
  return (
    <div className="position-panel position-panel--closed bg-gray-950/80 p-3.5 rounded-lg border border-indigo-900/40 space-y-2" aria-label="Closed trade explanation">
      <div className="panel-heading flex items-center justify-between">
        <div>
          <span className="card-label text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">CLOSED TRADE EXPLANATION</span>
          <h4 className="text-sm font-bold font-mono text-gray-100 m-0">{trade.action} at {number(trade.averageExit, 6)}</h4>
        </div>
        <small className="text-[10px] font-mono text-gray-400">{readableDate(trade.closedAt)}</small>
      </div>
      <p className="position-reasons text-xs text-gray-300 m-0 pt-1 font-mono">
        <span className="font-semibold text-gray-400">REALIZED PNL</span> {signed(trade.realizedPnl)}
      </p>
      <p className="position-reasons text-xs text-gray-300 m-0">
        <span className="font-semibold text-gray-400">REASONS</span> {trade.reasonCodes.join(", ")}
      </p>
      <p className="position-reasons text-xs text-gray-300 m-0">
        <span className="font-semibold text-gray-400">BEFORE</span> {trade.beforeEvidenceRefs.length ? trade.beforeEvidenceRefs.join(", ") : "NONE"}
      </p>
      <p className="position-reasons text-xs text-gray-300 m-0">
        <span className="font-semibold text-gray-400">AFTER</span> {trade.afterEvidenceRefs.length ? trade.afterEvidenceRefs.join(", ") : trade.evidenceRefs.join(", ")}
      </p>
    </div>
  );
}

function PositionCard({ position }: { position: PositionRecord }) {
  const displayName = position.symbol || position.name || "UNNAMED POSITION";
  return (
    <article className={`position-card position-card--${position.state.toLowerCase()} bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4`}>
      <div className="position-card__heading flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-800">
        <div>
          <h4 className="text-lg font-bold text-gray-100 flex items-center gap-2 m-0">
            {displayName}
            {position.symbol && position.name ? <span className="text-xs font-normal text-gray-400">({position.name})</span> : null}
          </h4>
          <div className="flex items-center gap-2 mt-1">
            <code className="text-xs font-mono text-cyan-400" title={position.mintAddress}>{shortIdentity(position.mintAddress, 10)}</code>
            <Link href={`/tokens/${position.tokenId}`} className="text-xs text-indigo-400 hover:text-indigo-300 font-medium no-underline">
              Research Token →
            </Link>
          </div>
        </div>

        <div className="position-card__badges flex items-center gap-2">
          <SafetyBadge label="MODE" value={position.mode} tone="paper" />
          <SafetyBadge label="STATE" value={position.state} tone={position.state === "CLOSED" ? "advisory" : "safe"} />
        </div>
      </div>

      <div className="position-card__facts flex flex-wrap items-center gap-4 text-xs font-mono bg-gray-950/50 p-2.5 rounded-lg border border-gray-800/60">
        <span className="text-gray-400">QTY <strong className="text-gray-200">{number(position.quantity, 6)}</strong></span>
        <span className="text-gray-400">ENTRY <strong className="text-gray-200">${number(position.averageEntry, 6)}</strong></span>
        <span className="text-gray-400">OPENED <strong className="text-gray-200">{readableDate(position.openedAt)}</strong></span>
      </div>

      <div className="position-evidence-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <PositionMark position={position} />
        <PositionPerformance position={position} />
        <ExitRisk position={position} />
        <ClosedTrade position={position} />
      </div>
    </article>
  );
}

function PositionsContent({ result }: { result: ReadResult<ReadPage<PositionRecord>> }) {
  const [filterState, setFilterState] = useState<string>("ALL");

  if (!result.ok) {
    return (
      <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
        <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">POSITION EVIDENCE / READ-ONLY</span>
        <strong className="text-lg text-rose-200 block mb-2">{failureMessage(result.reason)}</strong>
        <p className="text-sm text-gray-400 mb-4">No position or market data was substituted. Retry after the read dependency is available.</p>
        <Link href="/positions" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">RETRY</Link>
      </div>
    );
  }

  const items = result.data.items;

  if (items.length === 0) {
    return (
      <div className="read-state p-8 text-center bg-gray-900 border border-gray-800 rounded-xl" role="status">
        <span className="eyebrow text-xs text-amber-400 font-bold tracking-wider uppercase block mb-1">PAPER PORTFOLIO</span>
        <strong className="text-lg text-gray-200 block mb-2">NO POSITIONS AVAILABLE</strong>
        <p className="text-xs text-gray-400">The bounded read API returned no position records. Empty is not a performance signal.</p>
      </div>
    );
  }

  const filteredItems = filterState === "ALL" ? items : items.filter((p) => p.state === filterState);

  return (
    <div className="space-y-4">
      {/* FILTER TABS */}
      <div className="flex items-center gap-2 pb-2">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mr-1">FILTER POSITIONS:</span>
        {["ALL", "OPEN", "EXIT_SIGNALLED", "CLOSED"].map((st) => (
          <button
            key={st}
            onClick={() => setFilterState(st)}
            className={`text-xs px-2.5 py-1 rounded font-medium transition-all ${
              filterState === st
                ? "bg-emerald-950 text-emerald-300 border border-emerald-700 shadow-sm"
                : "bg-gray-950 text-gray-400 border border-gray-800 hover:text-gray-200"
            }`}
          >
            {st} ({st === "ALL" ? items.length : items.filter((p) => p.state === st).length})
          </button>
        ))}
      </div>

      <div className="position-list space-y-4" aria-label="Paper positions">
        {filteredItems.map((position) => <PositionCard key={position.id} position={position} />)}
      </div>
    </div>
  );
}

export function PositionsDashboard({ result }: { result: ReadResult<ReadPage<PositionRecord>> }) {
  const items = result.ok ? result.data.items : [];
  const openCount = items.filter((p) => p.state === "OPEN" || p.state === "EXIT_SIGNALLED").length;
  const closedCount = items.filter((p) => p.state === "CLOSED").length;
  const totalRealizedPnl = items.reduce((acc, p) => acc + (p.realizedPnl ?? 0), 0);
  const totalUnrealizedPnl = items.reduce((acc, p) => acc + (p.performance?.unrealizedPnl ?? 0), 0);

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        <section className="section-block intelligence-section space-y-6" aria-labelledby="positions-title">
          <div className="section-heading flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800/80">
            <div>
              <p className="eyebrow text-[10px] font-bold text-emerald-400 uppercase tracking-wider m-0">PAPER PORTFOLIO / OBSERVED + DERIVED EVIDENCE</p>
              <h3 id="positions-title" className="text-2xl font-bold text-gray-100 m-0">Positions</h3>
              <p className="section-note text-xs text-gray-400 m-0 mt-1">Marks and PnL are read-only projections; unknown data stays visible.</p>
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

          {/* TOP METRIC STRIP */}
          {result.ok && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="OPEN POSITIONS" value={openCount} variant={openCount > 0 ? "info" : "muted"} />
              <MetricCard label="CLOSED POSITIONS" value={closedCount} variant="muted" />
              <MetricCard label="TOTAL REALIZED PNL" value={`$${totalRealizedPnl.toFixed(2)}`} variant={totalRealizedPnl >= 0 ? "safe" : "danger"} />
              <MetricCard label="TOTAL UNREALIZED PNL" value={`$${totalUnrealizedPnl.toFixed(2)}`} variant={totalUnrealizedPnl >= 0 ? "safe" : "danger"} />
            </div>
          )}

          <PositionsContent result={result} />
        </section>

        <section className="queue-card bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex items-center justify-between" aria-labelledby="position-boundary-title">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center font-mono font-bold text-sm" aria-hidden="true">
              ◌
            </div>
            <div>
              <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider m-0">PAPER / ADVISORY ONLY</p>
              <h3 id="position-boundary-title" className="text-xs font-bold text-gray-200 m-0">No execution controls in this view</h3>
              <p className="text-[11px] text-gray-400 m-0">Exit risk and closed-trade explanations preserve evidence without authorizing orders.</p>
            </div>
          </div>
          <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
        </section>
      </div>
    </main>
  );
}
