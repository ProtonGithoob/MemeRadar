import Link from "next/link";

import type {
  EarlyRadarRecord,
  ReadPage,
  ReadResult
} from "../lib/read-api";

function displayMetric(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "UNKNOWN";
  return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function displayMap(value: Record<string, unknown>): string {
  const entries = Object.entries(value).slice(0, 3);
  if (entries.length === 0) return "UNKNOWN";
  return entries.map(([key, item]) => `${key}=${String(item)}`).join(", ");
}

function errorMessage(result: ReadResult<unknown>): string {
  if (result.ok) return "";
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "EARLY RADAR NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "EARLY RADAR AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID EARLY RADAR RESPONSE";
    case "UNAVAILABLE":
      return "EARLY RADAR UNAVAILABLE";
  }
}

function Entry({ entry }: { entry: EarlyRadarRecord }) {
  const displayName = entry.symbol || entry.name || "UNNAMED TOKEN";
  const score = entry.earlyScore === null
    ? "UNKNOWN"
    : `${displayMetric(entry.earlyScore)} / 100`;
  return (
    <article className="early-radar-card">
      <div className="early-radar-card__heading">
        <div>
          <p className="eyebrow">{entry.earlyState}</p>
          <h4>{displayName}</h4>
          <Link href={`/tokens/${entry.tokenId}`}>OPEN TOKEN DETAIL</Link>
        </div>
        <strong>EarlyScore {score}</strong>
      </div>
      <div className="early-radar-card__grid">
        <div><span>AGE</span><strong>{displayMetric(entry.launchAgeSeconds)}s</strong></div>
        <div><span>FIRST SEEN</span><strong>{entry.firstSeenSource}</strong></div>
        <div><span>LATENCY</span><strong>{displayMetric(entry.firstSeenLatencyMs)}ms</strong></div>
        <div><span>CONFIDENCE</span><strong>{entry.earlyScoreConfidence === null ? "UNKNOWN" : `${Math.round(entry.earlyScoreConfidence * 100)}%`}</strong></div>
        <div><span>BUY VELOCITY</span><strong>{displayMap(entry.buyVelocity)}</strong></div>
        <div><span>BUY ACCELERATION</span><strong>{displayMap(entry.buyAcceleration)}</strong></div>
        <div><span>UNIQUE BUYERS</span><strong>{displayMap(entry.uniqueBuyers)}</strong></div>
        <div><span>QUOTE INFLOW</span><strong>{displayMap(entry.quoteInflow)}</strong></div>
        <div><span>LIQUIDITY / IMPACT</span><strong>{displayMetric(entry.liquidityUsd)} / {displayMetric(entry.priceImpactBps)}bps</strong></div>
        <div><span>CREATOR / BUNDLE / HOLDER</span><strong>{entry.creatorRisk} / {entry.bundleRisk} / {entry.holderRisk}</strong></div>
        <div><span>SMART MONEY</span><strong>{displayMetric(entry.smartMoneyConfluence)}</strong></div>
        <div><span>SELLABILITY</span><strong>{entry.sellability}</strong></div>
      </div>
      <div className="early-radar-card__footer">
        <span>Shadow entry: {entry.shadowEntryStatus}</span>
        <span>External lead: {displayMetric(entry.externalCallLeadTimeMs)}ms</span>
        <strong>Auto execution: LOCKED</strong>
      </div>
      {entry.hardBlockReasons.length > 0 ? (
        <p className="early-radar-card__blocks">Hard blocks: {entry.hardBlockReasons.join(", ")}</p>
      ) : null}
    </article>
  );
}

export function UltraEarlyPanel({
  result
}: {
  result: ReadResult<ReadPage<EarlyRadarRecord>>;
}) {
  if (!result.ok) {
    return (
      <section className="section-block ultra-early-section" aria-labelledby="ultra-early-title">
        <div className="section-heading">
          <div><p className="eyebrow">LAUNCH INTELLIGENCE / READ-ONLY</p><h3 id="ultra-early-title">Ultra-Early Detection</h3></div>
        </div>
        <div className="read-state read-state--error" role="status">
          <strong>{errorMessage(result)}</strong>
          <p>No launch projection was substituted.</p>
          <Link href="/">RETRY</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="section-block ultra-early-section" aria-labelledby="ultra-early-title">
      <div className="section-heading">
        <div><p className="eyebrow">LAUNCH INTELLIGENCE / READ-ONLY</p><h3 id="ultra-early-title">Ultra-Early Detection</h3></div>
        <p className="section-note">Observed, derived and paper-only fields; UNKNOWN remains explicit.</p>
      </div>
      {result.data.items.length === 0 ? (
        <div className="read-state" role="status"><strong>NO ULTRA-EARLY CANDIDATES</strong><p>No launch projection matched the current read boundary.</p></div>
      ) : (
        <div className="early-radar-list" aria-label="Ultra-early launch candidates">
          {result.data.items.map((entry) => <Entry entry={entry} key={entry.candidateId} />)}
        </div>
      )}
    </section>
  );
}

