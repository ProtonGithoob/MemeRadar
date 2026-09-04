import { Metadata } from "next";
import Link from "next/link";
import { WorkstationTopBar } from "../components/ui-primitives";
import { WalletGraphExplorer } from "../components/wallet-graph";

export const metadata: Metadata = {
  title: "Wallet & Creator Outcome Graph — MemeRadar",
  description: "Read-only wallet, funder, deployer and token outcome graph explorer.",
};

export default function WalletGraphPage() {
  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-gray-800/80 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider bg-indigo-950 px-2 py-0.5 rounded border border-indigo-800/60">
                READ-ONLY OUTCOME GRAPH / E8.6
              </span>
              <span className="text-[10px] text-gray-400 bg-gray-900 px-2 py-0.5 rounded">
                ACTOR CLUSTER & CREATOR REPUTATION
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-100 m-0">Wallet & Creator Outcome Graph</h1>
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

        {/* GRAPH LEGEND & UX INSTRUCTIONS */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-gray-400 font-bold font-sans">LEGEND:</span>
            <span className="flex items-center gap-1 text-emerald-400"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Winner Token</span>
            <span className="flex items-center gap-1 text-rose-400"><span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Rug / Severe Dump</span>
            <span className="flex items-center gap-1 text-cyan-400"><span className="w-2.5 h-2.5 rounded-full bg-cyan-500" /> Wallet</span>
            <span className="flex items-center gap-1 text-purple-400"><span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> Actor Cluster / Pool</span>
            <span className="flex items-center gap-1 text-amber-300"><span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Shortest Path</span>
          </div>
          <span className="text-gray-400 text-[11px]">Click any node to inspect properties & creator reputation. Drag canvas to pan.</span>
        </div>

        <WalletGraphExplorer />
      </div>
    </main>
  );
}
