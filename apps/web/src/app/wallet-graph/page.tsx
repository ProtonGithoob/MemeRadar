import { Metadata } from "next";
import Link from "next/link";
import { OperatorHeader } from "../components/operator-header";
import { fetchControlState } from "../lib/read-api";

export const metadata: Metadata = {
  title: "Wallet & Creator Outcome Graph — MemeRadar",
  description: "Read-only wallet, funder, deployer and token outcome graph explorer.",
};

export default async function WalletGraphPage() {
  const controlResult = await fetchControlState();
  const control = controlResult.ok ? controlResult.data : null;

  return (
    <div className="app-shell min-h-screen bg-slate-950 text-slate-100 font-sans">
      <OperatorHeader />
      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Wallet & Creator Outcome Graph</h1>
            <p className="text-sm text-slate-400 mt-1">
              Read-only projection of relationships between creators, deployers, funders, side-wallets, and historical token outcomes.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">
              READ_ONLY / E8.6
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
            <h2 className="text-lg font-semibold text-slate-200">Graph Explorer</h2>
            <div className="h-64 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-center p-6 text-center text-slate-400">
              <div>
                <p className="text-sm">Enter a Solana wallet address or token mint on detail pages to view graph projections.</p>
                <p className="text-xs text-slate-500 mt-2">
                  Relationships include: FUNDER &rarr; CREATOR &rarr; TOKEN &rarr; SIDE WALLET &rarr; OUTCOME
                </p>
              </div>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-4">
            <h2 className="text-lg font-semibold text-slate-200">Reputation Taxonomy</h2>
            <ul className="space-y-2 text-xs text-slate-300">
              <li className="flex items-center justify-between">
                <span>PROVEN_POSITIVE</span>
                <span className="text-emerald-400 font-mono">Score &gt; 75 / 3+ Samples</span>
              </li>
              <li className="flex items-center justify-between">
                <span>POSITIVE</span>
                <span className="text-emerald-300 font-mono">Score &gt; 60</span>
              </li>
              <li className="flex items-center justify-between">
                <span>NEUTRAL</span>
                <span className="text-slate-400 font-mono">Score 40–60</span>
              </li>
              <li className="flex items-center justify-between">
                <span>UNPROVEN</span>
                <span className="text-amber-400 font-mono">&lt; 3 Samples</span>
              </li>
              <li className="flex items-center justify-between">
                <span>HIGH_RISK</span>
                <span className="text-rose-400 font-mono">Severe Failures &gt; 50%</span>
              </li>
              <li className="flex items-center justify-between">
                <span>REPEATED_SEVERE_FAILURE</span>
                <span className="text-rose-500 font-mono font-bold">Rug Rate &gt; 50%</span>
              </li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
