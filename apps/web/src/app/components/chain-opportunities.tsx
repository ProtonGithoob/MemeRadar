import { Fragment, type ReactNode } from "react";

import { FreshnessBadge } from "./status-badges";
import { formatConfidence, Unknown, Pill } from "./format";
import type { ChainOpportunityRecord, ReadPage, ReadResult } from "../lib/read-api";

function failureMessage(result: ReadResult<ReadPage<ChainOpportunityRecord>>): string {
  if (result.ok) return "";
  switch (result.reason) {
    case "NOT_CONFIGURED": return "CHAIN OPPORTUNITIES NOT CONFIGURED";
    case "UNAUTHORIZED": return "CHAIN OPPORTUNITIES AUTHORIZATION UNAVAILABLE";
    case "UNAVAILABLE": return "CHAIN OPPORTUNITIES UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID READ RESPONSE";
  }
}

function value(value: number | null, format: (item: number) => string = String): ReactNode {
  return value === null ? <Unknown /> : <span>{format(value)}</span>;
}

function fixed(value: number): string {
  return value.toFixed(2);
}

function listValue(values: string[]): string {
  return values.length === 0 ? "UNKNOWN" : values.join(" · ");
}

function OpportunityDetails({ item }: { item: ChainOpportunityRecord }) {
  return (
    <details className="opportunity-details">
      <summary>OPEN FULL EVIDENCE</summary>
      <div className="opportunity-details__grid">
        <span>AS OF / EXPIRES <b>{item.asOf} / {item.expiresAt}</b></span>
        <span>NEW TOKENS 1H / 24H <b>{item.newTokenCount1h ?? "UNKNOWN"} / {item.newTokenCount24h ?? "UNKNOWN"}</b></span>
        <span>NEW POOLS 1H / 24H <b>{item.newPoolCount1h ?? "UNKNOWN"} / {item.newPoolCount24h ?? "UNKNOWN"}</b></span>
        <span>TRANSACTIONS 1H / ACCELERATION <b>{item.transactionCount1h ?? "UNKNOWN"} / {item.transactionAcceleration ?? "UNKNOWN"}</b></span>
        <span>DEX VOLUME 1H / ACCELERATION <b>{item.dexVolume1h ?? "UNKNOWN"} / {item.dexVolumeAcceleration ?? "UNKNOWN"}</b></span>
        <span>LIQUIDITY 1H / ACCELERATION <b>{item.liquidityInflow1h ?? "UNKNOWN"} / {item.liquidityInflowAcceleration ?? "UNKNOWN"}</b></span>
        <span>ACTIVE WALLET ACCELERATION <b>{item.activeWalletAcceleration ?? "UNKNOWN"}</b></span>
        <span>LAUNCHPAD LAUNCH / GRADUATION <b>{item.launchpadLaunchCount5m ?? "UNKNOWN"} / {item.launchpadGraduationCount5m ?? "UNKNOWN"}</b></span>
        <span>SUCCESSFUL LAUNCH RATIO <b>{item.successfulLaunchRatio5m ?? "UNKNOWN"}</b></span>
        <span>SOURCE INDEPENDENCE / DIVERSITY <b>{item.sourceIndependenceCount} / {item.sourceDiversityConfidence}</b></span>
        <span>VERSION / CONFIG HASH <b>{item.version} / {item.configHash}</b></span>
        <span>REASON CODES <b>{listValue(item.reasonCodes)}</b></span>
        <span>EVIDENCE REFS <b>{listValue(item.evidenceRefs)}</b></span>
        <span>PROVENANCE <b>{item.provenance.length === 0 ? "UNKNOWN" : item.provenance.map((item) => `${item.provider}/${item.sourceId}`).join(" · ")}</b></span>
      </div>
    </details>
  );
}

function ChainOpportunityTable({ items }: { items: ChainOpportunityRecord[] }) {
  return (
    <div className="dt-wrap">
      <table aria-label="Chain opportunity evidence" className="dt">
        <thead>
          <tr>
            <th>Chain</th>
            <th className="num">New tokens / 5m</th>
            <th className="num">New pools / 5m</th>
            <th className="num">Active wallets / 5m</th>
            <th className="num">Transactions / 5m</th>
            <th className="num">DEX volume / 5m</th>
            <th className="num">Liquidity inflow / 5m</th>
            <th>Quality</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <Fragment key={`${item.chain}-${item.asOf}`}>
            <tr>
              <td><strong>{item.chain.toUpperCase()}</strong></td>
              <td className="num">{value(item.newTokenCount5m)}</td>
              <td className="num">{value(item.newPoolCount5m)}</td>
              <td className="num">{value(item.activeWalletCount5m)}</td>
              <td className="num">{value(item.transactionCount5m)}</td>
              <td className="num">{value(item.dexVolume5m, fixed)}</td>
              <td className="num">{value(item.liquidityInflow5m, fixed)}</td>
              <td><FreshnessBadge value={item.qualityState} /></td>
              <td><Pill label={formatConfidence(item.confidence)} tone="info" /></td>
            </tr>
            <tr key={`${item.chain}-${item.asOf}-details`}>
              <td colSpan={9}><OpportunityDetails item={item} /></td>
            </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChainOpportunitiesDashboard({
  result
}: {
  result: ReadResult<ReadPage<ChainOpportunityRecord>>;
}) {
  return (
    <main className="workspace-main">
      <div className="page-heading">
        <div>
          <p className="eyebrow">RESEARCH / MULTI-CHAIN EVIDENCE</p>
          <h2>Chain opportunities</h2>
        </div>
        <small>BOUNDED READ · NO EXECUTION AUTHORITY</small>
      </div>
      <p className="section-note">Recent chain activity is corroborating evidence, not a trade signal.</p>
      {!result.ok ? (
        <div className="read-state read-state--error" role="status">
          <strong>{failureMessage(result)}</strong>
          <p>No chain opportunity was inferred from the failed read.</p>
        </div>
      ) : result.data.items.length === 0 ? (
        <div className="read-state" role="status">
          <strong>NO CHAIN OPPORTUNITY EVIDENCE</strong>
          <p>The bounded catalog is empty. Empty is not healthy.</p>
        </div>
      ) : (
        <section className="section-block intelligence-section" aria-labelledby="chain-opportunities-title">
          <div className="page-heading">
            <h3 id="chain-opportunities-title">Five-minute activity</h3>
            <small>{result.data.items.length} chain{result.data.items.length === 1 ? "" : "s"}</small>
          </div>
          <ChainOpportunityTable items={result.data.items} />
        </section>
      )}
      <section className="boundary-strip" aria-label="Execution boundary">
        <strong>EXECUTION LOCKED</strong>
        <span>Chain evidence remains advisory and cannot authorize a position.</span>
      </section>
    </main>
  );
}
