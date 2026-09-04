import React from "react";
import Link from "next/link";

import { WorkstationTopBar } from "../components/ui-primitives";
import { UltraEarlyPanel } from "../components/ultra-early";
import { fetchEarlyRadar } from "../lib/read-api";

export default async function UltraEarlyPage() {
  const result = await fetchEarlyRadar();

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-gray-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800/60">
                ULTRA-EARLY WORKSTATION
              </span>
              <span className="text-[10px] text-gray-400 bg-gray-900 px-2 py-0.5 rounded">
                SUB-SECOND TO 5-MINUTE LAUNCHES
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-100 m-0">Ultra-Early Launch Intelligence</h1>
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

        <UltraEarlyPanel result={result} />

        <section className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex items-center justify-between" aria-label="Execution boundary">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center font-mono font-bold text-sm" aria-hidden="true">
              ◎
            </div>
            <div>
              <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">OPERATOR BOUNDARY / ADVISORY</p>
              <h3 className="text-xs font-bold text-gray-200">No execution authority in this view</h3>
              <p className="text-[11px] text-gray-400">Launch metrics and flow acceleration remain advisory context for paper trading.</p>
            </div>
          </div>
          <span className="text-xs font-mono font-bold text-gray-500 bg-gray-950 border border-gray-800 px-3 py-1 rounded">
            NO LIVE ORDERS
          </span>
        </section>
      </div>
    </main>
  );
}
