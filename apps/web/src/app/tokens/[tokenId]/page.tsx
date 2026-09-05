import Link from "next/link";

import { TokenDetailView } from "../../components/token-detail";
import { fetchEarlyRadar, fetchTimeline, fetchToken, isValidTokenId } from "../../lib/read-api";

export default async function TokenPage({
  params
}: {
  params: Promise<{ tokenId: string }>;
}) {
  const { tokenId } = await params;
  if (!isValidTokenId(tokenId)) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">Token route</span>
        <strong>INVALID TOKEN IDENTIFIER</strong>
        <p>Only a canonical token UUID can be requested from the read API.</p>
        <Link href="/radar">BACK TO RADAR</Link>
      </div>
    );
  }

  const [tokenResult, timelineResult, earlyRadarResult] = await Promise.all([
    fetchToken(tokenId),
    fetchTimeline(tokenId),
    fetchEarlyRadar()
  ]);
  const early = earlyRadarResult.ok
    ? earlyRadarResult.data.items.find((item) => item.tokenId === tokenId) ?? null
    : null;

  return (
    <>
      <Link className="back-link" href="/radar">← BACK TO RADAR</Link>
      <section className="section-block" aria-label="Token detail" style={{ marginTop: 12 }}>
        <TokenDetailView early={early} timelineResult={timelineResult} tokenResult={tokenResult} />
      </section>
    </>
  );
}
