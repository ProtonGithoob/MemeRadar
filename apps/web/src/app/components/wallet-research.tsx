import type {
  ReadPage,
  ReadResult,
  WalletRecord,
  WinnerRegistryRecord
} from "../lib/read-api";
import { PageHeader } from "./ui";

const RISK_CATEGORIES = new Set([
  "CREATOR_LINKED",
  "POTENTIAL_INSIDER",
  "POTENTIAL_WASH_TRADER",
  "POTENTIAL_MANIPULATION_CLUSTER"
]);

function short(value: string): string {
  return value.length > 20 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}

function sol(value: number | null): string {
  return value === null ? "UNKNOWN" : `${value.toFixed(1)} SOL`;
}

function failure(reason: string, subject: string): string {
  switch (reason) {
    case "NOT_CONFIGURED":
      return `${subject} READ API NOT CONFIGURED`;
    case "UNAUTHORIZED":
      return `${subject} READ AUTHORIZATION UNAVAILABLE`;
    case "INVALID_RESPONSE":
      return "INVALID READ RESPONSE";
    default:
      return `${subject} UNAVAILABLE`;
  }
}

function outcomeLabel(outcome: string, censor: string | null, peak: number | null): string {
  if (outcome === "PENDING") return "PENDING (horizon not mature)";
  if (outcome === "CENSORED") return `CENSORED${censor ? ` · ${censor}` : ""}`;
  const multiple = peak === null ? "" : ` (${peak.toFixed(2)}x)`;
  return `${outcome}${multiple}${censor ? ` · lower bound: ${censor}` : ""}`;
}

export function RegistryTable({ records }: { records: WinnerRegistryRecord[] }) {
  if (records.length === 0) {
    return <div className="read-state" role="status">
        <strong>NO RESEARCHED LAUNCHES YET</strong>
        <p>Enable WALLET_RESEARCH_ENABLED on the worker to collect 24-48 h old launches daily.</p>
      </div>;
  }
  const horizons = ["1h", "6h", "24h", "7d", "30d"];
  return (
    <div className="dt-wrap">
    <table aria-label="Extreme winner registry" className="dt">
      <thead>
        <tr>
          <th>Token</th>
          <th>Initial → peak cap</th>
          <th>Trades / buyers</th>
          <th>Migrated</th>
          <th>History</th>
          {horizons.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {records.map((record) => (
          <tr key={record.mint}>
            <td><code title={record.mint}>{short(record.mint)}</code></td>
            <td>{sol(record.initialMarketCapSol)} → {sol(record.peakMarketCapSol)}</td>
            <td>{record.tradeCount} / {record.uniqueBuyers}</td>
            <td>{record.migratedAt ? "YES" : "NO"}</td>
            <td>
              {record.historyComplete === null ? "UNKNOWN" : record.historyComplete ? "COMPLETE" : "PARTIAL"}
              {record.ammTradesDecoded === false && record.migratedAt ? " · AMM UNDECODED" : ""}
            </td>
            {horizons.map((h) => {
              const outcome = record.outcomes.find((o) => o.horizon === h);
              return (
                <td key={h}>
                  {outcome ? outcomeLabel(outcome.outcome, outcome.censorReason, outcome.peakMultiple) : "—"}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

export function WalletResearchDashboard({
  registry,
  wallets
}: {
  registry: ReadResult<WinnerRegistryRecord[]>;
  wallets: ReadResult<ReadPage<WalletRecord>>;
}) {
  const walletItems = wallets.ok ? wallets.data.items : [];
  const risky = walletItems.filter((w) => w.reasonCodes.some((code) => RISK_CATEGORIES.has(code)));
  const candidates = walletItems.filter((w) =>
    w.reasonCodes.includes("EARLY_SMART_MONEY_CANDIDATE") &&
    !w.reasonCodes.some((code) => RISK_CATEGORIES.has(code))
  );
  return (
    <section className="section-block" aria-labelledby="wallet-research-title">
      <PageHeader
        id="wallet-research-title"
        eyebrow="RESEARCH"
        title="Wallet Intelligence"
        note="Verified on-chain observations, heuristic classifications and missing evidence are labelled separately. Nothing here is calibrated or an instruction to trade."
      />
      <section className="section-block" aria-labelledby="registry-heading">
        <h2 id="registry-heading">Extreme Winner Registry · VERIFIED ON-CHAIN TRADES</h2>
        <p className="section-note">
          All researched launches, including tokens that never moved. PENDING and CENSORED are not outcomes.
        </p>
        {registry.ok ? <RegistryTable records={registry.data} /> : (
          <div className="read-state read-state--error" role="alert">
            <strong>{failure(registry.reason, "REGISTRY")}</strong>
          </div>
        )}
      </section>
      <section className="section-block" aria-labelledby="wallet-heading">
        <h2 id="wallet-heading">Wallet classifications · HEURISTIC, NOT CALIBRATED</h2>
        {wallets.ok ? (
          <ul className="metric-strip">
            <li>Profiled wallets: {walletItems.length}</li>
            <li>Early smart-money candidates (unvalidated): {candidates.length}</li>
            <li>Manipulation-risk wallets (risk evidence only): {risky.length}</li>
          </ul>
        ) : (
          <div className="read-state read-state--error" role="alert">
            <strong>{failure(wallets.reason, "WALLET")}</strong>
          </div>
        )}
        <p className="section-note">
          Risk-category wallets never qualify as copy or entry signals. Common funding or synchronized buying does not prove common ownership.
        </p>
      </section>
    </section>
  );
}
