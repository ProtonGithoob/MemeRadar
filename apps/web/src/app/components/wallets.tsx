import Link from "next/link";

import { FreshnessBadge, SafetyBadge, ScoreBadge } from "./status-badges";
import { isValidWalletAddress } from "../lib/read-api";
import type { ReadPage, ReadResult, WalletRecord } from "../lib/read-api";
import { PageHeader } from "./ui";

function shortIdentity(value: string, visible = 9): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function percent(value: number | null): string {
  return value === null ? "UNKNOWN" : `${Math.round(value * 100)}%`;
}

function pnl(value: number | null): string {
  return value === null || !Number.isFinite(value) ? "UNKNOWN" : value.toFixed(2);
}

function failureMessage(result: ReadResult<ReadPage<WalletRecord>>): string | null {
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

function WalletCard({ wallet, rank }: { wallet: WalletRecord; rank: number }) {
  const label = wallet.label || "UNLABELED WALLET";
  const chain = wallet.chain ?? "solana";
  const routeAddress = chain === "solana" ? wallet.address : chain + ":" + wallet.address;
  return (
    <article className="wallet-card">
      <div className="wallet-card__identity">
        <span className="wallet-rank">#{rank}</span>
        <div>
          {isValidWalletAddress(wallet.address) ? (
            <Link className="wallet-label" href={`/wallets/${routeAddress}`}>
              {label}
            </Link>
          ) : (
            <strong className="wallet-label">{label}</strong>
          )}
          <code title={wallet.address}>{shortIdentity(wallet.address, 10)}</code>
        </div>
        <small>{chain.toUpperCase()} · AS OF {readableDate(wallet.asOf)}</small>
      </div>
      <div className="wallet-card__tiers">
        <span className="card-label">REGISTRY / RECOMMENDED</span>
        <strong>{wallet.registryTier} / {wallet.recommendedTier}</strong>
        <small>{wallet.reasonCodes.length} reason{wallet.reasonCodes.length === 1 ? "" : "s"}</small>
      </div>
      <div className="wallet-card__score">
        <ScoreBadge value={wallet.score} />
        <span className="confidence-label">
          CONFIDENCE {wallet.confidence === null ? "UNKNOWN" : `${Math.round(wallet.confidence * 100)}%`}
        </span>
      </div>
      <div className="wallet-card__outcomes">
        <strong>{percent(wallet.winRate)} WIN RATE</strong>
        <span>{wallet.knownOutcomeCount} known / {wallet.sampleCount} samples</span>
        <span>PnL {pnl(wallet.realizedPnl)}</span>
        <FreshnessBadge value={wallet.qualityState} />
      </div>
    </article>
  );
}

function WalletsContent({ result }: { result: ReadResult<ReadPage<WalletRecord>> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">WALLET EVIDENCE / READ-ONLY</span>
        <strong>{failureMessage(result)}</strong>
        <p>No wallet evidence was substituted. Retry after the read dependency is available.</p>
        <Link href="/wallets">RETRY</Link>
      </div>
    );
  }
  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">SMART-MONEY CATALOG</span>
        <strong>NO WALLET CATALOG AVAILABLE</strong>
        <p>The bounded read API returned no wallet records. Empty is not a healthy signal.</p>
      </div>
    );
  }
  return (
    <div className="wallet-list" aria-label="Smart wallet leaderboard">
      {result.data.items.map((wallet, index) => (
        <WalletCard key={wallet.address} wallet={wallet} rank={index + 1} />
      ))}
    </div>
  );
}

export function WalletsDashboard({ result }: { result: ReadResult<ReadPage<WalletRecord>> }) {
  return (
    <>
      <section className="section-block intelligence-section" aria-labelledby="wallets-title">
        <PageHeader
          eyebrow="Internal wallet evidence / ranked read"
          id="wallets-title"
          note="Scores are historical evidence, not order authority."
          title="Smart wallets"
        />
        <WalletsContent result={result} />
      </section>
      <section className="boundary-strip" aria-labelledby="wallet-boundary-title">
        <div>
          <p className="eyebrow">CORROBORATING EVIDENCE / ADVISORY</p>
          <h3 id="wallet-boundary-title">Wallet labels never authorize entry</h3>
          <p>Internal scoring remains bounded and separate from external wallet labels.</p>
        </div>
        <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
      </section>
    </>
  );
}
