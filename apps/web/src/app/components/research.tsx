"use client";

import React, { useState } from "react";
import Link from "next/link";
import { WorkstationTopBar, MetricCard, SectionHeader, StatusPill } from "./ui-primitives";

export interface ResearchGateQuestion {
  id: number;
  question: string;
  status: string;
  evidence_class: string;
  summary: string;
}

export interface ResearchGateData {
  gate_version: string;
  evaluated_at: string;
  verdict: string;
  operating_modes: {
    ANALYSIS_ONLY: boolean;
    PAPER_TRADING: boolean;
    MANUAL_EXECUTION: boolean;
    AUTO_EXECUTION: boolean;
  };
  questions: ResearchGateQuestion[];
}

export const DEFAULT_RESEARCH_GATE: ResearchGateData = {
  gate_version: "product-research-gate-v1",
  evaluated_at: "2026-09-04T12:00:00Z",
  verdict: "ULTRA_EARLY_DETECTION_READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING_AUTO_EXECUTION_LOCKED",
  operating_modes: {
    ANALYSIS_ONLY: true,
    PAPER_TRADING: true,
    MANUAL_EXECUTION: false,
    AUTO_EXECUTION: false
  },
  questions: [
    {
      id: 1,
      question: "Can future 20x/50x/100x winners be detected before major market-cap expansion?",
      status: "INSUFFICIENT_REAL_WORLD_SAMPLES",
      evidence_class: "SYNTHETIC_FIXTURE / INSUFFICIENT_SAMPLES",
      summary: "Synthetic replay demonstrates theoretical early detection at sub-$50k market caps; real-world live sample size remains insufficient."
    },
    {
      id: 2,
      question: "What decision-time micro-features provide the strongest out-of-sample lift for extreme winners?",
      status: "INSUFFICIENT_REAL_WORLD_SAMPLES",
      evidence_class: "SYNTHETIC_FIXTURE / INSUFFICIENT_SAMPLES",
      summary: "micro_flow_3m acceleration and creator_reputation_score show initial lift in synthetic ablation; empirical live ranking pending."
    },
    {
      id: 3,
      question: "Does creator outcome history and graph connectivity reliably separate winners from rugs?",
      status: "PROVEN_IN_SYNTHETIC_REPLAY",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "CreatorOutcomeGraph shortest path and reputation scoring fail closed on UNKNOWN and reduce rug false positives."
    },
    {
      id: 4,
      question: "Do thin-liquidity mark-price wicks create false positive 20x+ outcome labels?",
      status: "PROVEN_REJECTED",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "ExtremeWinnerOutcomeLabeler enforces $1,000 liquidity, sellability, and <=1,000bps impact, successfully failing closed on mark wicks."
    },
    {
      id: 5,
      question: "Can pre-mine and insider allocation suspicion identify hidden rug/dump risks early?",
      status: "PROVEN_IN_SYNTHETIC_REPLAY",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "InsiderAllocationAnalyzer correctly flags fresh wallet clusters, shared funding, and low native SOL balances before liquidity collapse."
    },
    {
      id: 6,
      question: "Does cross-venue wallet position continuity maintain accurate position tracking across DEX migrations?",
      status: "PROVEN",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "CrossVenuePositionTracker maintains canonical trade ID and wallet position state across Pump.fun -> Raydium graduation."
    },
    {
      id: 7,
      question: "What is the optimal convex exit policy for retaining asymmetric upside while bounding drawdown?",
      status: "BEST_SYNTHETIC_CANDIDATE",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "BEST_SYNTHETIC_CANDIDATE: balanced-convex-v1 (33% partial TP at 2.0x, 15% trailing stop, 25% max DD tolerance) achieves top expectancy in synthetic trade cohort replay; this is a synthetic candidate hypothesis, not a production optimality claim."
    },
    {
      id: 8,
      question: "Can asymmetric alpha candidate projections enhance decision confidence without emitting guaranteed predictions?",
      status: "PROVEN",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "AsymmetricAlphaProjection exposes early quality score, upside evidence, rug risk, and execution quality without fake multiple guarantees."
    },
    {
      id: 9,
      question: "Is out-of-sample strategy promotion strictly enforced against lookahead bias and sample inadequacy?",
      status: "PROVEN",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "StrategyPromotionGate enforces TRAIN/VAL/TEST split, sample adequacy, deterministic replay, out-of-sample lift, and human review."
    },
    {
      id: 10,
      question: "What is the current risk-adjusted paper PnL expectancy across evaluated replay cohorts?",
      status: "CALIBRATED_SYNTHETIC",
      evidence_class: "SYNTHETIC_FIXTURE",
      summary: "Positive net paper expectancy (+3.575x per trade under balanced-convex-v1) demonstrated in synthetic replay (tagged SYNTHETIC_FIXTURE); live paper trading expectancy remains INSUFFICIENT_REAL_WORLD_SAMPLES."
    },
    {
      id: 11,
      question: "Is the system ready for live read-only shadow trading under locked auto-execution?",
      status: "READY_FOR_LIVE_READ_ONLY_SHADOW_TRADING",
      evidence_class: "SYNTHETIC_FIXTURE / LIVE_READ_ONLY_READY",
      summary: "All 9 research extensions fully implemented and verified with 100% test pass rate under locked auto-execution."
    }
  ]
};

export function ResearchDashboard({ data = DEFAULT_RESEARCH_GATE }: { data?: ResearchGateData }) {
  const [filterClass, setFilterClass] = useState<string>("ALL");

  const evidenceClasses = [
    { key: "SYNTHETIC_FIXTURE", label: "SYNTHETIC_FIXTURE", desc: "Synthetic Replay Fixture", color: "text-amber-400 border-amber-800 bg-amber-950/40" },
    { key: "HISTORICAL_REAL", label: "HISTORICAL_REAL", desc: "Historical Chain Data", color: "text-cyan-400 border-cyan-800 bg-cyan-950/40" },
    { key: "LIVE_SHADOW", label: "LIVE_SHADOW", desc: "Live Read-Only Shadow Window", color: "text-emerald-400 border-emerald-800 bg-emerald-950/40" },
    { key: "INSUFFICIENT_SAMPLES", label: "INSUFFICIENT_SAMPLES", desc: "Sample Size Insufficient", color: "text-rose-400 border-rose-800 bg-rose-950/40" },
    { key: "NOT_AVAILABLE", label: "NOT_AVAILABLE", desc: "Unconfigured / Unmeasured", color: "text-gray-400 border-gray-800 bg-gray-950/40" },
  ];

  const filteredQuestions = filterClass === "ALL"
    ? data.questions
    : data.questions.filter((q) => q.evidence_class.includes(filterClass));

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        {/* TOP STATUS & VERDICT BANNER */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800/80">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider bg-amber-950 px-2 py-0.5 rounded border border-amber-800/60">
                  RESEARCH & CALIBRATION DESK
                </span>
                <span className="text-[10px] text-gray-400 font-mono">VERSION {data.gate_version}</span>
              </div>
              <h1 className="text-2xl font-bold text-gray-100 m-0">Product Research Gate & Strategy Calibration</h1>
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

          {/* DOMINANT REAL-WORLD STATE WARNING */}
          <div className="bg-amber-950/40 border border-amber-800/80 rounded-lg p-4 flex items-start gap-4">
            <div className="text-amber-400 font-mono text-xl font-bold">⚠</div>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-3">
                <strong className="text-sm font-bold text-amber-300 font-mono">REAL_WORLD_ALPHA_NOT_YET_PROVEN</strong>
                <span className="text-[10px] bg-amber-900/60 text-amber-200 px-2 py-0.5 rounded font-mono uppercase">
                  SYNTHETIC HYPOTHESIS ONLY
                </span>
              </div>
              <p className="text-gray-300 text-[11px]">
                Synthetic replay expectancy (+3.575x under candidate policy <code className="text-amber-300">balanced-convex-v1</code>) is a calibrated synthetic hypothesis. Real-world live shadow collection is required before live alpha claims or production strategy promotion.
              </p>
            </div>
          </div>
        </div>

        {/* EVIDENCE TAXONOMY GRID */}
        <section className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4">
          <SectionHeader
            title="EVIDENCE CLASS TAXONOMY"
            subtitle="Strict distinction between synthetic replay and real-world live evidence"
          />

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-xs">
            {evidenceClasses.map((item) => (
              <div key={item.key} className={`p-3 rounded-lg border ${item.color} space-y-1`}>
                <strong className="font-mono text-xs block truncate">{item.label}</strong>
                <span className="text-[10px] text-gray-400 block">{item.desc}</span>
              </div>
            ))}
          </div>
        </section>

        {/* STRATEGY PROMOTION & EXIT POLICY COMPARISON */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4">
            <SectionHeader
              title="CANDIDATE STRATEGY EVALUATION"
              subtitle="Exit policy replay & out-of-sample validation"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="bg-gray-950 p-4 rounded-lg border border-gray-800 space-y-2">
                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">
                  CANDIDATE POLICY: balanced-convex-v1
                </span>
                <div className="space-y-1.5 text-gray-300">
                  <div className="flex justify-between"><span>Status:</span> <strong className="text-amber-300 font-mono">BEST_SYNTHETIC_CANDIDATE</strong></div>
                  <div className="flex justify-between"><span>Partial Take-Profit:</span> <strong className="font-mono text-gray-200">33% @ 2.0x</strong></div>
                  <div className="flex justify-between"><span>Trailing Stop:</span> <strong className="font-mono text-gray-200">15%</strong></div>
                  <div className="flex justify-between"><span>Max Drawdown Tolerance:</span> <strong className="font-mono text-gray-200">25%</strong></div>
                  <div className="flex justify-between"><span>Synthetic Expectancy:</span> <strong className="font-mono text-emerald-400">+3.575x / trade</strong></div>
                </div>
              </div>

              <div className="bg-gray-950 p-4 rounded-lg border border-gray-800 space-y-2">
                <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider block">
                  PROMOTION GATE CRITERIA (E10.6)
                </span>
                <ul className="space-y-1 text-gray-400 list-disc list-inside text-[11px]">
                  <li>TRAIN/VAL/TEST strict temporal data splits</li>
                  <li>Zero lookahead bias in micro-feature inputs</li>
                  <li>Min sample count: 100 historical outcomes</li>
                  <li>Out-of-sample expectancy lift &gt; 0</li>
                  <li>Human operator review approval required</li>
                </ul>
              </div>
            </div>
          </div>

          {/* SUMMARY METRICS */}
          <div className="lg:col-span-1 bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-gray-100 m-0">RESEARCH GATE SUMMARY</h3>
            <div className="space-y-3">
              <MetricCard label="TOTAL QUESTIONS AUDITED" value={data.questions.length} variant="info" />
              <MetricCard label="PROVEN IN SYNTHETIC REPLAY" value={data.questions.filter(q => q.status.includes("PROVEN")).length} variant="safe" />
              <MetricCard label="INSUFFICIENT LIVE SAMPLES" value={data.questions.filter(q => q.status.includes("INSUFFICIENT")).length} variant="warning" />
            </div>
          </div>
        </div>

        {/* 11 CORE RESEARCH QUESTIONS AUDIT TABLE */}
        <section className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 space-y-4" aria-label="Research gate questions audit">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-800">
            <div>
              <h3 className="text-base font-bold text-gray-100 m-0">11 Product Research Gate Questions</h3>
              <p className="text-xs text-gray-400 m-0 mt-0.5">Audited evidence class and empirical status for each core product requirement</p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">FILTER CLASS:</span>
              {["ALL", "SYNTHETIC_FIXTURE", "INSUFFICIENT_SAMPLES"].map((c) => (
                <button
                  key={c}
                  onClick={() => setFilterClass(c)}
                  className={`text-xs px-2.5 py-1 rounded font-medium transition-all ${
                    filterClass === c
                      ? "bg-amber-950 text-amber-300 border border-amber-700"
                      : "bg-gray-950 text-gray-400 border border-gray-800 hover:text-gray-200"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            {filteredQuestions.map((q) => (
              <article key={q.id} className="bg-gray-950/80 p-4 rounded-lg border border-gray-800/80 space-y-2 text-xs">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="font-bold text-gray-200 text-sm">
                    Q{q.id}. {q.question}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] bg-gray-900 text-amber-300 border border-amber-800 px-2 py-0.5 rounded font-semibold uppercase">
                      {q.status}
                    </span>
                    <span className="font-mono text-[10px] bg-gray-900 text-gray-400 border border-gray-800 px-2 py-0.5 rounded">
                      {q.evidence_class}
                    </span>
                  </div>
                </div>
                <p className="text-gray-300 text-xs m-0 leading-relaxed">{q.summary}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
