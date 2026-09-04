"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";

import type {
  EarlyRadarRecord,
  ReadPage,
  ReadResult
} from "../lib/read-api";
import {
  SectionHeader,
  StatusPill,
  RiskChip,
  FreshnessIndicator,
  ScoreGauge
} from "./ui-primitives";

export type UltraEarlyPreset =
  | "ALL"
  | "FRESH_1M"
  | "FRESH_5M"
  | "HIGH_CONFLUENCE"
  | "ENTRY_READY"
  | "CREATOR_RISK"
  | "BUNDLE_RISK"
  | "UNKNOWN_CRITICAL";

function displayMetric(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "UNKNOWN";
  return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function displayMap(value: Record<string, unknown>): string {
  const entries = Object.entries(value).slice(0, 3);
  if (entries.length === 0) return "UNKNOWN";
  return entries.map(([key, item]) => `${key}=${String(item)}`).join(", ");
}

function errorMessage(result: ReadResult<unknown>): string {
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

function Entry({ entry }: { entry: EarlyRadarRecord }) {
  const displayName = entry.symbol || entry.name || "UNNAMED TOKEN";
  const scoreText = entry.earlyScore === null
    ? "UNKNOWN"
    : `${displayMetric(entry.earlyScore)} / 100`;

  return (
    <article className="early-radar-card bg-gray-900/80 border border-gray-800 rounded-xl p-4 space-y-3 transition-all hover:border-gray-700">
      <div className="early-radar-card__heading flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-gray-800/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="eyebrow text-[10px] font-bold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40 uppercase">
              {entry.earlyState}
            </span>
            <RiskChip disposition={entry.riskDisposition} />
            <FreshnessIndicator quality={entry.firstSeenQuality} />
          </div>
          <h4 className="text-base font-bold text-gray-100 flex items-center gap-2 m-0">
            {displayName}
            <code className="text-xs font-mono text-gray-400 font-normal">({entry.mintAddress.slice(0, 6)}…{entry.mintAddress.slice(-4)})</code>
          </h4>
          <Link href={`/tokens/${entry.tokenId}`} className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-block mt-1 no-underline">
            OPEN TOKEN DETAIL →
          </Link>
        </div>

        <div className="text-right">
          <strong className="text-sm font-bold font-mono text-emerald-400 block">
            EarlyScore {scoreText}
          </strong>
          <span className="text-[10px] text-gray-400 block font-mono">
            CONFIDENCE: {entry.earlyScoreConfidence === null ? "UNKNOWN" : `${Math.round(entry.earlyScoreConfidence * 100)}%`}
          </span>
        </div>
      </div>

      <div className="early-radar-card__grid grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">AGE</span>
          <strong className="text-gray-200 font-mono">{displayMetric(entry.launchAgeSeconds)}s</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">FIRST SEEN</span>
          <strong className="text-gray-200 font-mono truncate block" title={entry.firstSeenSource}>{entry.firstSeenSource}</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">LATENCY</span>
          <strong className="text-gray-200 font-mono">{displayMetric(entry.firstSeenLatencyMs)}ms</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">SMART MONEY</span>
          <strong className="text-amber-300 font-mono">{displayMetric(entry.smartMoneyConfluence)}</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">LIQUIDITY / IMPACT</span>
          <strong className="text-gray-200 font-mono">${displayMetric(entry.liquidityUsd)} / {displayMetric(entry.priceImpactBps)}bps</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">CREATOR / BUNDLE / HOLDER</span>
          <strong className="text-gray-200 font-mono">{entry.creatorRisk} / {entry.bundleRisk} / {entry.holderRisk}</strong>
        </div>

        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50 col-span-2 md:col-span-2">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">BUY VELOCITY & ACCELERATION</span>
          <strong className="text-cyan-300 font-mono text-[11px] block">{displayMap(entry.buyVelocity)} | ACC: {displayMap(entry.buyAcceleration)}</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50 col-span-2 md:col-span-2">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">UNIQUE BUYERS & INFLOW</span>
          <strong className="text-purple-300 font-mono text-[11px] block">{displayMap(entry.uniqueBuyers)} | INFLOW: {displayMap(entry.quoteInflow)}</strong>
        </div>
        <div className="bg-gray-950/50 p-2 rounded border border-gray-800/50 col-span-2 md:col-span-2">
          <span className="text-[10px] font-semibold text-gray-400 block uppercase">SELLABILITY</span>
          <strong className={`font-mono text-[11px] ${entry.sellability === 'PASS' ? 'text-emerald-400' : 'text-rose-400'}`}>{entry.sellability}</strong>
        </div>
      </div>

      <div className="early-radar-card__footer flex flex-wrap items-center justify-between text-xs pt-2 border-t border-gray-800/50 text-gray-400 font-mono">
        <span>Shadow entry: {entry.shadowEntryStatus}</span>
        <span>External lead: {displayMetric(entry.externalCallLeadTimeMs)}ms</span>
        <strong className="text-rose-400 font-bold">Auto execution: LOCKED</strong>
      </div>

      {entry.hardBlockReasons.length > 0 ? (
        <p className="early-radar-card__blocks text-xs font-mono text-rose-300 bg-rose-950/40 p-2 rounded border border-rose-900/50 m-0">
          Hard blocks: {entry.hardBlockReasons.join(", ")}
        </p>
      ) : null}
    </article>
  );
}

export function UltraEarlyPanel({
  result
}: {
  result: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  const [activePreset, setActivePreset] = useState<UltraEarlyPreset>("ALL");

  const items = result.ok ? result.data.items : [];

  const filteredItems = useMemo(() => {
    if (!items.length) return [];
    switch (activePreset) {
      case "FRESH_1M":
        return items.filter((item) => (item.launchAgeSeconds ?? 999) <= 60);
      case "FRESH_5M":
        return items.filter((item) => (item.launchAgeSeconds ?? 999) <= 300);
      case "HIGH_CONFLUENCE":
        return items.filter((item) => (item.smartMoneyConfluence ?? 0) >= 50);
      case "ENTRY_READY":
        return items.filter((item) => item.earlyState === "ENTRY_READY");
      case "CREATOR_RISK":
        return items.filter((item) => item.creatorRisk === "HIGH" || item.creatorRisk === "BLOCK");
      case "BUNDLE_RISK":
        return items.filter((item) => item.bundleRisk === "HIGH" || item.bundleRisk === "BLOCK");
      case "UNKNOWN_CRITICAL":
        return items.filter((item) => item.firstSeenQuality === "UNKNOWN" || item.holderRisk === "UNKNOWN");
      case "ALL":
      default:
        return items;
    }
  }, [items, activePreset]);

  if (!result.ok) {
    return (
      <section className="section-block ultra-early-section bg-gray-900/80 border border-gray-800 rounded-xl p-5" aria-labelledby="ultra-early-title">
        <div className="section-heading pb-3 border-b border-gray-800 mb-4">
          <p className="eyebrow text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">LAUNCH INTELLIGENCE / READ-ONLY</p>
          <h3 id="ultra-early-title" className="text-lg font-bold text-gray-100 m-0">Ultra-Early Detection</h3>
        </div>
        <div className="read-state read-state--error p-6 text-center bg-gray-950 border border-rose-900/50 rounded-lg" role="status">
          <strong className="text-rose-300 block mb-2">{errorMessage(result)}</strong>
          <p className="text-xs text-gray-400 mb-3">No launch projection was substituted.</p>
          <Link href="/" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">RETRY</Link>
        </div>
      </section>
    );
  }

  const presets: { key: UltraEarlyPreset; label: string }[] = [
    { key: "ALL", label: `All (${items.length})` },
    { key: "FRESH_1M", label: "Fresh < 1m" },
    { key: "FRESH_5M", label: "Fresh < 5m" },
    { key: "HIGH_CONFLUENCE", label: "High Confluence" },
    { key: "ENTRY_READY", label: "Entry Ready" },
    { key: "CREATOR_RISK", label: "Creator Risk" },
    { key: "BUNDLE_RISK", label: "Bundle Risk" },
    { key: "UNKNOWN_CRITICAL", label: "Unknown Data" }
  ];

  return (
    <section className="section-block ultra-early-section bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4" aria-labelledby="ultra-early-title">
      <div className="section-heading flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-800">
        <div>
          <p className="eyebrow text-[10px] font-bold text-cyan-400 uppercase tracking-wider m-0">LAUNCH INTELLIGENCE / READ-ONLY</p>
          <h3 id="ultra-early-title" className="text-lg font-bold text-gray-100 m-0">Ultra-Early Detection</h3>
          <p className="section-note text-xs text-gray-400 m-0 mt-0.5">Observed, derived and paper-only fields; UNKNOWN remains explicit.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400 bg-gray-950 px-2.5 py-1 rounded border border-gray-800">
            {filteredItems.length} Candidates
          </span>
        </div>
      </div>

      {/* OPERATOR PRESETS */}
      <div className="flex flex-wrap items-center gap-2 pb-2">
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mr-1">PRESETS:</span>
        {presets.map((preset) => (
          <button
            key={preset.key}
            onClick={() => setActivePreset(preset.key)}
            className={`text-xs px-2.5 py-1 rounded font-medium transition-all ${
              activePreset === preset.key
                ? "bg-cyan-950 text-cyan-300 border border-cyan-700 shadow-sm"
                : "bg-gray-950/80 text-gray-400 border border-gray-800 hover:text-gray-200 hover:border-gray-700"
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {filteredItems.length === 0 ? (
        <div className="read-state p-8 text-center bg-gray-950 border border-gray-800/80 rounded-xl" role="status">
          <strong className="text-gray-200 text-sm block mb-1">NO ULTRA-EARLY CANDIDATES</strong>
          <p className="text-xs text-gray-400">No launch projection matched the current read boundary or filter preset.</p>
        </div>
      ) : (
        <div className="early-radar-list space-y-4" aria-label="Ultra-early launch candidates">
          {filteredItems.map((entry) => <Entry entry={entry} key={entry.candidateId} />)}
        </div>
      )}
    </section>
  );
}
