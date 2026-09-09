import Link from "next/link";

import { FreshnessBadge, SafetyBadge, ScoreBadge } from "./status-badges";
import type { ReadResult, WalletRecord } from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function percent(value: number | null): string {
  return value === null ? "UNKNOWN" : `${Math.round(value * 100)}%`;
}

function failureMessage(result: ReadResult<WalletRecord | null>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "WALLET READ API NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "WALLET READ AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID READ RESPONSE";
    case "UNAVAILABLE":
      return "WALLET INTELLIGENCE UNAVAILABLE";
  }
}

function ReadFailure({ result }: { result: ReadResult<WalletRecord | null> }) {
  return (
    <div className="read-state read-state--error" role="status">
      <span className="eyebrow">WALLET DETAIL / READ-ONLY</span>
      <strong>{failureMessage(result)}</strong>
      <p>No wallet detail was substituted.</p>
    </div>
  );
}

export function WalletDetailView({ result }: { result: ReadResult<WalletRecord | null> }) {
  if (!result.ok) return <ReadFailure result={result} />;
  if (result.data === null) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">WALLET DETAIL</span>
        <strong>WALLET NOT FOUND</strong>
        <p>The validated address has no matching wallet record.</p>
      </div>
    );
  }

  const wallet = result.data;
  return (
    <>
      <section className="token-overview wallet-overview" aria-labelledby="wallet-detail-title">
        <div className="token-identity">
          <p className="eyebrow">{(wallet.chain ?? "UNKNOWN").toUpperCase()} / WALLET INTELLIGENCE / ADVISORY</p>
          <h2 id="wallet-detail-title" aria-label={wallet.label}>{wallet.label}<span>{wallet.recommendedTier} RECOMMENDATION</span></h2>
          <code>{wallet.address}</code>
          <p className="muted-copy">Observed {readableDate(wallet.asOf)}; expires {readableDate(wallet.expiresAt)}.</p>
        </div>
        <div className="token-status-grid">
          <ScoreBadge value={wallet.score} />
          <FreshnessBadge value={wallet.qualityState} />
          <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
        </div>
      </section>
      <div className="overview-grid wallet-detail-grid">
        <section className="detail-panel" aria-labelledby="wallet-performance-title">
          <div className="panel-heading">
            <div><p className="eyebrow">OUTCOMES</p><h3 id="wallet-performance-title">Historical performance</h3></div>
          </div>
          <dl className="detail-list">
            <div><dt>REGISTRY TIER</dt><dd>{wallet.registryTier}</dd></div>
            <div><dt>RECOMMENDED TIER</dt><dd>{wallet.recommendedTier}</dd></div>
            <div><dt>WIN RATE</dt><dd>{percent(wallet.winRate)}</dd></div>
            <div><dt>REALIZED PNL</dt><dd>{wallet.realizedPnl === null ? "UNKNOWN" : wallet.realizedPnl.toFixed(2)}</dd></div>
            <div><dt>KNOWN OUTCOMES</dt><dd>{wallet.knownOutcomeCount}</dd></div>
            <div><dt>SAMPLE COUNT</dt><dd>{wallet.sampleCount}</dd></div>
          </dl>
        </section>
        <section className="detail-panel" aria-labelledby="wallet-evidence-title">
          <div className="panel-heading">
            <div><p className="eyebrow">EXPLAINABILITY</p><h3 id="wallet-evidence-title">Evidence references</h3></div>
          </div>
          {wallet.reasonCodes.length > 0 ? (
            <ul className="evidence-tags" aria-label="Wallet reason codes">
              {wallet.reasonCodes.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          ) : <p className="muted-copy">UNKNOWN REASONS</p>}
          {wallet.evidenceRefs.length > 0 ? (
            <ul className="evidence-tags" aria-label="Wallet evidence references">
              {wallet.evidenceRefs.map((reference) => <li key={reference}>{reference}</li>)}
            </ul>
          ) : <p className="muted-copy">UNKNOWN REFERENCES</p>}
        </section>
      </div>
      <section className="boundary-strip" aria-labelledby="wallet-detail-boundary-title">
        <div>
          <p className="eyebrow">SAFETY BOUNDARY</p>
          <h3 id="wallet-detail-boundary-title">Wallet evidence is not execution authority</h3>
          <p>Score, labels, outcomes and freshness remain corroborating analysis only.</p>
        </div>
        <Link className="back-link" href="/wallets">BACK TO WALLETS</Link>
      </section>
    </>
  );
}
