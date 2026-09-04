import Link from "next/link";

import { WorkstationTopBar, SectionHeader } from "../../components/ui-primitives";
import { TokenDetailView } from "../../components/token-detail";
import { UltraEarlyPanel } from "../../components/ultra-early";
import {
  fetchCreatorReputation,
  fetchEarlyRadar,
  fetchPositions,
  fetchTimeline,
  fetchToken,
  isValidTokenId
} from "../../lib/read-api";

export default async function TokenPage({
  params
}: {
  params: Promise<{ tokenId: string }>;
}) {
  const { tokenId } = await params;
  if (!isValidTokenId(tokenId)) {
    return (
      <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
        <WorkstationTopBar />
        <div className="max-w-[1550px] mx-auto w-full p-6">
          <div className="read-state read-state--error p-8 text-center bg-gray-900 border border-rose-900/50 rounded-xl" role="status">
            <span className="eyebrow text-xs text-rose-400 font-bold tracking-wider uppercase block mb-1">TOKEN ROUTE</span>
            <strong className="text-lg text-rose-200 block mb-2">INVALID TOKEN IDENTIFIER</strong>
            <p className="text-sm text-gray-400 mb-4">Only a canonical token UUID can be requested from the read API.</p>
            <Link href="/" className="text-xs text-indigo-400 hover:text-indigo-300 underline font-semibold">BACK TO RADAR</Link>
          </div>
        </div>
      </main>
    );
  }

  const [tokenResult, timelineResult, earlyRadarResult, positionsResult] = await Promise.all([
    fetchToken(tokenId),
    fetchTimeline(tokenId),
    fetchEarlyRadar(),
    fetchPositions()
  ]);

  const earlyRadarItem = earlyRadarResult.ok
    ? earlyRadarResult.data.items.find((item) => item.tokenId === tokenId) ?? null
    : null;

  const positionItem = positionsResult.ok
    ? positionsResult.data.items.find((item) => item.tokenId === tokenId) ?? null
    : null;

  const creatorWallet = tokenResult.ok ? tokenResult.data?.creatorWallet : null;
  const creatorReputationResult = creatorWallet ? await fetchCreatorReputation(creatorWallet) : null;
  const creatorReputationRecord = creatorReputationResult?.ok ? creatorReputationResult.data : null;

  const earlyResultForToken = earlyRadarResult.ok
    ? {
        ok: true as const,
        data: {
          ...earlyRadarResult.data,
          items: earlyRadarResult.data.items.filter((item) => item.tokenId === tokenId)
        }
      }
    : earlyRadarResult;

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 flex flex-col font-sans">
      <WorkstationTopBar />

      <div className="max-w-[1550px] mx-auto w-full p-4 md:p-6 space-y-6">
        <div className="flex items-center justify-between">
          <Link className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1 font-medium no-underline" href="/">
            ← BACK TO RADAR COMMAND CENTER
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-2 py-0.5 rounded font-mono">
              ANALYSIS_ONLY=true
            </span>
            <span className="text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800 px-2 py-0.5 rounded font-mono">
              PAPER_TRADING=true
            </span>
          </div>
        </div>

        <section className="section-block detail-section" aria-label="Token detail">
          <TokenDetailView
            tokenResult={tokenResult}
            timelineResult={timelineResult}
            earlyRadarRecord={earlyRadarItem}
            positionRecord={positionItem}
            creatorReputationRecord={creatorReputationRecord}
          />
        </section>

        <UltraEarlyPanel result={earlyResultForToken} />

        <section className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex items-center justify-between" aria-label="Execution boundary">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-gray-400 flex items-center justify-center font-mono font-bold text-sm" aria-hidden="true">
              ◎
            </div>
            <div>
              <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">OPERATOR BOUNDARY / ADVISORY</p>
              <h3 className="text-xs font-bold text-gray-200">No execution authority in this view</h3>
              <p className="text-[11px] text-gray-400">Evidence and external labels remain read-only context for review.</p>
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
