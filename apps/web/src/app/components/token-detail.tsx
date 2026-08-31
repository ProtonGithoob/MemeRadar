import Link from "next/link";

import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./status-badges";
import type {
  CandidateRecord,
  ReadPage,
  ReadResult,
  TimelineRecord,
  TokenRecord
} from "../lib/read-api";

type MetricPoint = { at: string; value: number };

const MAX_CHART_POINTS = 24;
const METRIC_KEYS = {
  price: ["price"],
  liquidity: ["liquidity", "liquidity_usd"],
  buy: ["buy_volume", "buyVolume24h"],
  sell: ["sell_volume", "sellVolume24h"]
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteMetric(value: unknown): number | null {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && (value.length > 32 || value.trim() === "")) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1_000_000_000_000_000
    ? parsed
    : null;
}

function metricFromEntry(entry: TimelineRecord, keys: readonly string[]): number | null {
  const payload = entry.payload;
  const containers: Record<string, unknown>[] = [payload];
  for (const key of ["values", "metrics", "snapshot"]) {
    const nested = payload[key];
    if (isRecord(nested)) containers.push(nested);
  }
  for (const container of containers) {
    for (const key of keys) {
      const value = finiteMetric(container[key]);
      if (value !== null) return value;
    }
  }
  return null;
}

function pointsFor(entries: TimelineRecord[], keys: readonly string[]): MetricPoint[] {
  const points: MetricPoint[] = [];
  for (const entry of entries) {
    const value = metricFromEntry(entry, keys);
    if (value !== null) points.push({ at: entry.occurredAt, value });
  }
  return points.slice(-MAX_CHART_POINTS);
}

function netFlowPointsFor(entries: TimelineRecord[]): MetricPoint[] {
  const points: MetricPoint[] = [];
  for (const entry of entries) {
    const buy = metricFromEntry(entry, METRIC_KEYS.buy);
    const sell = metricFromEntry(entry, METRIC_KEYS.sell);
    if (buy !== null && sell !== null) {
      points.push({ at: entry.occurredAt, value: buy - sell });
    }
  }
  return points.slice(-MAX_CHART_POINTS);
}

function shortIdentity(value: string, visible = 9): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

function displayDate(value: string): string {
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : "UNKNOWN TIME";
}

function displayNumber(value: number): string {
  if (Math.abs(value) >= 1_000_000) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function displayPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0 || value > 100) return "UNKNOWN";
  const normalized = value <= 1 ? value * 100 : value;
  return normalized > 100 ? "UNKNOWN" : `${normalized.toFixed(1)}%`;
}

function holderMetric(entries: TimelineRecord[], keys: readonly string[]): number | null {
  let value: number | null = null;
  for (const entry of entries) {
    if (!entry.kind.startsWith("holder.")) continue;
    const next = metricFromEntry(entry, keys);
    if (next !== null) value = next;
  }
  return value;
}

function failureMessage(
  result: ReadResult<unknown>,
  scope: "radar" | "detail" = "detail"
): string {
  if (result.ok) return "";
  switch (result.reason) {
    case "NOT_CONFIGURED":
      return "READ API NOT CONFIGURED";
    case "UNAUTHORIZED":
      return "READ API AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE":
      return "INVALID READ RESPONSE";
    case "UNAVAILABLE":
      return scope === "radar" ? "RADAR UNAVAILABLE" : "DETAIL UNAVAILABLE";
  }
}

export function MetricChart({ label, points }: { label: string; points: MetricPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="metric-chart metric-chart--empty" role="status">
        <span>{label.toUpperCase()}</span>
        <strong>NO DATA</strong>
      </div>
    );
  }

  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const coordinates = points
    .map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
      const y = 92 - ((point.value - minimum) / span) * 76;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <div className="metric-chart">
      <div className="metric-chart__heading">
        <span>{label.toUpperCase()}</span>
        <strong>{displayNumber(points[points.length - 1]?.value ?? 0)}</strong>
      </div>
      <svg
        className="metric-chart__svg"
        viewBox="0 0 100 100"
        role="img"
        aria-label={`${label} evidence chart`}
        preserveAspectRatio="none"
      >
        <title>{`${label} evidence chart, ${points.length} event-time points`}</title>
        <line x1="0" y1="92" x2="100" y2="92" className="metric-chart__axis" />
        <polyline points={coordinates} className="metric-chart__line" />
      </svg>
      <small>{points.length} event-time point{points.length === 1 ? "" : "s"}; API order preserved</small>
    </div>
  );
}

function Overview({ token }: { token: TokenRecord }) {
  const candidate = token.candidate;
  const risk = candidate?.riskDisposition ?? "UNKNOWN";
  const freshness = candidate?.riskQualityState ?? "UNKNOWN";
  return (
    <>
      <section className="token-overview" aria-labelledby="token-overview-title">
        <div className="token-identity">
          <p className="eyebrow">TOKEN OVERVIEW / READ-ONLY</p>
          <h2 id="token-overview-title">
            {token.symbol || "UNNAMED"}
            {token.name ? <span>{token.name}</span> : null}
          </h2>
          <code title={token.mintAddress}>{shortIdentity(token.mintAddress, 12)}</code>
          <div className="badge-row">
            <SafetyBadge label="ADVISORY OUTPUT" value="ONLY" tone="advisory" />
            <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
          </div>
        </div>
        <div className="token-status-grid">
          <ScoreBadge value={candidate?.score ?? null} />
          <RiskBadge value={risk} />
          <FreshnessBadge value={freshness} />
        </div>
      </section>

      <section className="overview-grid" aria-label="Token metadata">
        <article className="detail-panel">
          <span className="card-label">IDENTITY</span>
          <dl className="detail-list">
            <div><dt>CHAIN</dt><dd>{token.chain}</dd></div>
            <div><dt>PROGRAM</dt><dd>{token.tokenProgram}</dd></div>
            <div><dt>STATUS</dt><dd>{token.status}</dd></div>
            <div><dt>DECIMALS</dt><dd>{token.decimals ?? "UNKNOWN"}</dd></div>
          </dl>
        </article>
        <article className="detail-panel">
          <span className="card-label">CREATOR WALLET</span>
          {token.creatorWallet ? (
            <code title={token.creatorWallet}>{shortIdentity(token.creatorWallet, 12)}</code>
          ) : <strong>UNKNOWN</strong>}
          <small className="muted-copy">Wallet identity is evidence, not execution authority.</small>
        </article>
        <article className="detail-panel detail-panel--wide">
          <div className="panel-heading">
            <span className="card-label">LIQUIDITY POOLS</span>
            <small>{token.pools.length} known</small>
          </div>
          {token.pools.length === 0 ? <strong>UNKNOWN</strong> : (
            <div className="pool-list">
              {token.pools.map((pool) => (
                <div className="pool-row" key={pool.id}>
                  <strong>{pool.venue}</strong>
                  <code title={pool.poolAddress}>{shortIdentity(pool.poolAddress, 9)}</code>
                  <small>QUOTE {shortIdentity(pool.quoteMint, 9)}</small>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </>
  );
}

function HolderBar({ label, value }: { label: string; value: number | null }) {
  const normalized = value === null ? null : value <= 1 ? value * 100 : value;
  const width = normalized === null || !Number.isFinite(normalized)
    ? 0
    : Math.min(100, Math.max(0, normalized));
  return (
    <div className="holder-metric">
      <div className="panel-heading">
        <span>{label}</span>
        <strong>{displayPercent(value)}</strong>
      </div>
      <div className="holder-bar" aria-hidden="true"><span style={{ width: `${width}%` }} /></div>
    </div>
  );
}

function EvidencePanels({ entries }: { entries: TimelineRecord[] }) {
  const top10 = holderMetric(entries, ["top10_hold_percent", "holder_supply_pct", "top10_concentration_pct"]);
  const clustered = holderMetric(entries, ["clustered_supply_pct", "clustered_supply_percent", "holder_cluster_pct"]);
  return (
    <section className="evidence-grid" aria-label="Explainable evidence panels">
      <article className="detail-panel chart-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">MARKET EVIDENCE</p>
            <h3>Event-time metrics</h3>
          </div>
          <small>ALLOW-LISTED ONLY</small>
        </div>
        <div className="charts-grid">
          <MetricChart label="Price" points={pointsFor(entries, METRIC_KEYS.price)} />
          <MetricChart label="Liquidity" points={pointsFor(entries, METRIC_KEYS.liquidity)} />
          <MetricChart label="Net flow" points={netFlowPointsFor(entries)} />
        </div>
      </article>
      <article className="detail-panel holder-panel">
        <p className="eyebrow">HOLDER EVIDENCE</p>
        <h3>HOLDER CONCENTRATION / CLUSTERS</h3>
        <p className="muted-copy">Normalized holder snapshots remain contextual evidence.</p>
        <HolderBar label="TOP 10 SUPPLY" value={top10} />
        <HolderBar label="CLUSTERED SUPPLY" value={clustered} />
      </article>
    </section>
  );
}

function TokenTimeline({ entries }: { entries: TimelineRecord[] }) {
  if (entries.length === 0) {
    return <div className="read-state" role="status"><strong>NO EVIDENCE YET</strong><p>No normalized timeline entries were returned.</p></div>;
  }
  return (
    <div className="timeline-list" aria-label="Event-time evidence timeline">
      {entries.map((entry) => (
        <article className="timeline-entry" key={entry.id}>
          <div className="timeline-entry__time">
            <strong>{displayDate(entry.occurredAt)}</strong>
            <small>OBSERVED {displayDate(entry.observedAt)}</small>
          </div>
          <div className="timeline-entry__body">
            <div className="timeline-entry__heading">
              <strong>{entry.kind}</strong>
              <FreshnessBadge value={entry.qualityState} />
            </div>
            <span>SOURCE {entry.sourceId}</span>
            <small>
              {entry.reasonCodes.length > 0 ? `REASONS ${entry.reasonCodes.join(", ")}` : "NO REASON CODES"}
            </small>
            {entry.provenance.length > 0 ? (
              <div className="provenance-list">
                {entry.provenance.map((provenance, index) => (
                  <small key={`${provenance.sourceId}-${index}`}>
                    PROVIDER {provenance.provider} / SOURCE {provenance.sourceId} / PARSER {provenance.parserVersion}
                  </small>
                ))}
              </div>
            ) : <small>PROVENANCE UNKNOWN</small>}
          </div>
        </article>
      ))}
    </div>
  );
}

function SocialNarrative({ entries }: { entries: TimelineRecord[] }) {
  const selected = entries.filter((entry) => entry.kind.startsWith("social.") || entry.kind.startsWith("narrative."));
  return (
    <section className="detail-panel social-panel" aria-labelledby="social-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">CORRELATED CONTEXT</p>
          <h3 id="social-title">SOCIAL / NARRATIVE EVIDENCE</h3>
        </div>
        <small>ADVISORY</small>
      </div>
      {selected.length === 0 ? <strong>UNKNOWN</strong> : (
        <div className="social-list">
          {selected.map((entry) => (
            <article className="social-row" key={entry.id}>
              <strong>{entry.kind}</strong>
              <span>{entry.sourceId}</span>
              <small>PROVIDER {entry.provenance[0]?.provider ?? "UNKNOWN"}</small>
              <small>OBSERVED {displayDate(entry.observedAt)}</small>
              {entry.reasonCodes.length > 0 ? <small>REASONS {entry.reasonCodes.join(", ")}</small> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function TokenDetailView({
  tokenResult,
  timelineResult
}: {
  tokenResult: ReadResult<TokenRecord>;
  timelineResult: ReadResult<ReadPage<TimelineRecord>>;
}) {
  if (!tokenResult.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">TOKEN READ</span>
        <strong>{failureMessage(tokenResult)}</strong>
        <p>The token projection could not be safely loaded.</p>
        <Link href="/">BACK TO RADAR</Link>
      </div>
    );
  }

  const token = tokenResult.data;
  if (!token) {
    return <div className="read-state" role="status"><strong>TOKEN NOT FOUND</strong><Link href="/">BACK TO RADAR</Link></div>;
  }
  if (!timelineResult.ok) {
    return (
      <>
        <Overview token={token} />
        <div className="read-state read-state--error" role="status">
          <span className="eyebrow">EVIDENCE TIMELINE</span>
          <strong>{failureMessage(timelineResult)}</strong>
          <p>Token metadata is available; evidence remains unavailable.</p>
        </div>
      </>
    );
  }

  const entries = timelineResult.data.items;
  return (
    <>
      <Overview token={token} />
      <EvidencePanels entries={entries} />
      <section className="detail-panel timeline-panel" aria-labelledby="timeline-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">NO-LOOKAHEAD EVIDENCE</p>
            <h3 id="timeline-title">Evidence timeline</h3>
          </div>
          <small>OCCURRED → OBSERVED → INGESTED</small>
        </div>
        <TokenTimeline entries={entries} />
      </section>
      <SocialNarrative entries={entries} />
    </>
  );
}
