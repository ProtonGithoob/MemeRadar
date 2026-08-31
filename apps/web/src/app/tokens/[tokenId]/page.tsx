import Link from "next/link";

import { OperatorHeader } from "../../components/operator-header";
import { ProtectedShell } from "../../components/radar";
import { TokenDetailView } from "../../components/token-detail";
import { fetchTimeline, fetchToken, isValidTokenId } from "../../lib/read-api";

export default async function TokenPage({
  params
}: {
  params: Promise<{ tokenId: string }>;
}) {
  const { tokenId } = await params;
  if (!isValidTokenId(tokenId)) {
    return (
      <main className="shell">
        <OperatorHeader />
        <div className="read-state read-state--error" role="status">
          <span className="eyebrow">TOKEN ROUTE</span>
          <strong>INVALID TOKEN IDENTIFIER</strong>
          <p>Only a canonical token UUID can be requested from the read API.</p>
          <Link href="/">BACK TO RADAR</Link>
        </div>
      </main>
    );
  }

  const [tokenResult, timelineResult] = await Promise.all([
    fetchToken(tokenId),
    fetchTimeline(tokenId)
  ]);

  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <Link className="back-link" href="/">← BACK TO RADAR</Link>
      <section className="section-block detail-section" aria-label="Token detail">
        <TokenDetailView tokenResult={tokenResult} timelineResult={timelineResult} />
      </section>
      <section className="queue-card detail-boundary" aria-label="Execution boundary">
        <div className="queue-card__icon" aria-hidden="true">◎</div>
        <div>
          <p className="eyebrow">OPERATOR BOUNDARY / ADVISORY</p>
          <h3>No execution authority in this view</h3>
          <p>Evidence and external labels remain read-only context for review.</p>
        </div>
        <span className="queue-card__state">NO LIVE ORDERS</span>
      </section>
    </main>
  );
}
