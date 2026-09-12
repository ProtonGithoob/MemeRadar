import Link from "next/link";

import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./status-badges";
import {
  Pill,
  evidenceTone,
  formatAgeSeconds,
  formatConfidence,
  formatScore,
  formatUsd,
  riskTone,
  shortIdentity
} from "./format";
import { Inspector } from "./inspector";
import type {
  EarlyRadarRecord,
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
    if (value !== null && entry.occurredAt !== null) points.push({ at: entry.occurredAt, value });
  }
  return points.slice(-MAX_CHART_POINTS);
}

function netFlowPointsFor(entries: TimelineRecord[]): MetricPoint[] {
  const points: MetricPoint[] = [];
  for (const entry of entries) {
    const buy = metricFromEntry(entry, METRIC_KEYS.buy);
    const sell = metricFromEntry(entry, METRIC_KEYS.sell);
    if (buy !== null && sell !== null && entry.occurredAt !== null) {
      points.push({ at: entry.occurredAt, value: buy - sell });
    }
  }
  return points.slice(-MAX_CHART_POINTS);
}

function displayDate(value: string | null): string {
  if (value === null) return "UNKNOWN TIME";
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : "UNKNOWN TIME";
}

function displayNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "UNKNOWN";
  if (Math.abs(value) >= 1_000_000) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function displayPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0 || value > 100) return "UNKNOWN";
  const normalized = value <= 1 ? value * 100 : value;
  return normalized > 100 ? "UNKNOWN" : `${normalized.toFixed(1)}%`;
}

const EARLY_ALPHA_CHANGE_FIELDS = [
  ["smart_wallets", "Smart Wallets"],
  ["holders", "Holders"],
  ["graduation", "Graduation"],
  ["volume_acceleration", "Volume Accel"],
  ["alpha_score", "AlphaScore"],
  ["confidence", "Confidence"]
] as const;

function boundedEvidenceValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNKNOWN";
  if (typeof value === "string") return value.slice(0, 128);
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "YES" : "NO";
  return "UNKNOWN";
}

function earlyAlphaPayload(entry: TimelineRecord): Record<string, unknown> | null {
  if (entry.kind !== "alert.early_alpha") return null;
  const payload = entry.payload.early_alpha;
  return isRecord(payload) ? payload : null;
}

function EarlyAlphaEvidence({ entry }: { entry: TimelineRecord }) {
  const alpha = earlyAlphaPayload(entry);
  if (alpha === null) return null;
  const transition = isRecord(alpha.early_alpha_transition) ? alpha.early_alpha_transition : null;
  const changes = isRecord(alpha.changes) ? alpha.changes : null;
  const changeRows = changes === null ? [] : EARLY_ALPHA_CHANGE_FIELDS.flatMap(([key, label]) => {
    const change = changes[key];
    if (!isRecord(change)) return [];
    return [[label, `${boundedEvidenceValue(change.previous)} → ${boundedEvidenceValue(change.current)}`] as const];
  });
  const cohorts = isRecord(alpha.cohort_similarity) ? alpha.cohort_similarity : null;
  return (
    <div className="detail-list" aria-label="Early Alpha canonical evidence">
      <div><dt>EARLY ALPHA STATE</dt><dd>{boundedEvidenceValue(alpha.early_alpha_state ?? alpha.state)}</dd></div>
      <div><dt>RISK GATES</dt><dd>{boundedEvidenceValue(alpha.risk_gates)}</dd></div>
      {transition ? (
        <div>
          <dt>TRANSITION</dt>
          <dd>{boundedEvidenceValue(transition.previous)} → {boundedEvidenceValue(transition.current)}</dd>
        </div>
      ) : null}
      {changeRows.length > 0 ? (
        <div>
          <dt>EVIDENCE BEFORE → NOW</dt>
          <dd>{changeRows.map(([label, value]) => <span key={label}>{label}: {value}; </span>)}</dd>
        </div>
      ) : null}
      {cohorts ? (
        <div>
          <dt>COHORT SIMILARITY</dt>
          <dd>{["10x", "50x", "100x"].map((key) => `${key}: ${boundedEvidenceValue(cohorts[key])}`).join("; ")}</dd>
        </div>
      ) : null}
      <div><dt>CORRELATION</dt><dd>{boundedEvidenceValue(alpha.early_alpha_correlation_id)}</dd></div>
    </div>
  );
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
        <strong>{displayNumber(points[points.length - 1]?.value ?? null)}</strong>
      </div>
      <svg
        aria-label={`${label} evidence chart`}
        className="metric-chart__svg"
        preserveAspectRatio="none"
        role="img"
        viewBox="0 0 100 100"
      >
        <title>{`${label} evidence chart, ${points.length} event-time points`}</title>
        <line className="metric-chart__axis" x1="0" x2="100" y1="92" y2="92" />
        <polyline className="metric-chart__line" points={coordinates} />
      </svg>
      <small>{points.length} event-time point{points.length === 1 ? "" : "s"}; API order preserved</small>
    </div>
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
      <div aria-hidden="true" className="holder-bar"><span style={{ width: `${width}%` }} /></div>
    </div>
  );
}

function TokenHeader({ token, early }: { token: TokenRecord; early: EarlyRadarRecord | null }) {
  const candidate = token.candidate;
  const risk = candidate?.riskDisposition ?? early?.riskDisposition ?? "UNKNOWN";
  const freshness = candidate?.riskQualityState ?? early?.firstSeenQuality ?? "UNKNOWN";
  const score = candidate?.score ?? early?.earlyScore ?? null;
  return (
    <section aria-labelledby="token-overview-title" className="tw-header">
      <div className="tw-header__identity">
        <p className="eyebrow">Token workspace / read-only</p>
        <h2 id="token-overview-title">
          {token.symbol || "UNNAMED"}
          {token.name ? <span>{token.name}</span> : null}
        </h2>
        <code title={token.mintAddress}>{token.mintAddress}</code>
        <div className="badge-row">
          <SafetyBadge label="ADVISORY OUTPUT" tone="advisory" value="ONLY" />
          <SafetyBadge label="EXECUTION" tone="disabled" value="LOCKED" />
        </div>
      </div>
      <div className="tw-header__badges">
        <ScoreBadge value={score} />
        <RiskBadge value={risk} />
        <FreshnessBadge value={freshness} />
        {early ? (
          <span className="status-badge" role="status">
            <span className="status-badge__label">LAUNCH AGE</span>
            <strong>{early.launchAgeSeconds === null ? "UNKNOWN" : formatAgeSeconds(early.launchAgeSeconds)}</strong>
          </span>
        ) : null}
      </div>
    </section>
  );
}

function RiskFactors({ token, early }: { token: TokenRecord; early: EarlyRadarRecord | null }) {
  const candidate = token.candidate;
  const risk = candidate?.riskDisposition ?? early?.riskDisposition ?? "UNKNOWN";
  const freshness = candidate?.riskQualityState ?? early?.firstSeenQuality ?? "UNKNOWN";
  return (
    <article className="detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Explicit risk factors</p>
          <h3>RISK ANALYSIS</h3>
        </div>
        <small>UNKNOWN IS NOT SAFE</small>
      </div>
      <div className="risk-factor"><span>Overall disposition</span><Pill label={risk} tone={riskTone(risk)} /></div>
      <div className="risk-factor"><span>Creator / deployer</span><Pill label={early?.creatorRisk ?? "UNKNOWN"} tone={evidenceTone(early?.creatorRisk ?? "UNKNOWN")} /></div>
      <div className="risk-factor"><span>Bundle / sniper</span><Pill label={early?.bundleRisk ?? "UNKNOWN"} tone={evidenceTone(early?.bundleRisk ?? "UNKNOWN")} /></div>
      <div className="risk-factor"><span>Holder concentration</span><Pill label={early?.holderRisk ?? "UNKNOWN"} tone={evidenceTone(early?.holderRisk ?? "UNKNOWN")} /></div>
      <div className="risk-factor"><span>Sellability</span><Pill label={early?.sellability ?? "UNKNOWN"} tone={evidenceTone(early?.sellability ?? "UNKNOWN")} /></div>
      <div className="risk-factor"><span>Evidence freshness</span><Pill label={freshness} tone={freshness.toLowerCase()} /></div>
      {early && early.hardBlockReasons.length > 0 ? (
        <div className="risk-factor">
          <span>Hard blocks</span>
          <Pill label={early.hardBlockReasons.join(", ")} tone="high" />
        </div>
      ) : null}
    </article>
  );
}

function InsiderEvidencePanel({ token }: { token: TokenRecord }) {
  const evidence = token.insiderEvidence;
  if (evidence === null) {
    return (
      <article className="detail-panel">
        <div className="panel-heading"><div><p className="eyebrow">Distribution evidence</p><h3>INSIDER PATTERN EVIDENCE</h3></div><small>UNKNOWN</small></div>
        <p className="muted-copy">No canonical insider-allocation projection is available.</p>
      </article>
    );
  }
  const wallets = evidence.topSuspiciousWallets.length === 0
    ? "UNKNOWN"
    : evidence.topSuspiciousWallets.map((wallet) => shortIdentity(wallet, 10)).join(", ");
  const reasons = evidence.reasonCodes.length === 0 ? "NONE RECORDED" : evidence.reasonCodes.join(", ");
  const providers = evidence.provenance.length === 0
    ? "UNKNOWN"
    : [...new Set(evidence.provenance.map((item) => item.provider))].join(", ");
  return (
    <article className="detail-panel" aria-label="Insider pattern evidence">
      <div className="panel-heading">
        <div><p className="eyebrow">Distribution evidence</p><h3>INSIDER PATTERN EVIDENCE</h3></div>
        <Pill label={evidence.suspicionState} tone={evidenceTone(evidence.suspicionState)} />
      </div>
      <dl className="detail-list">
        <div><dt>QUALITY</dt><dd>{evidence.qualityState}</dd></div>
        <div><dt>SUSPICIOUS HOLDERS</dt><dd>{evidence.suspiciousHolderCount ?? "UNKNOWN"}</dd></div>
        <div><dt>SUSPICIOUS SUPPLY</dt><dd>{displayPercent(evidence.suspiciousSupplyPct)}</dd></div>
        <div><dt>CONFIDENCE</dt><dd>{formatConfidence(evidence.confidence)}</dd></div>
        <div><dt>EXCLUDED INFRASTRUCTURE</dt><dd>{evidence.excludedAddressCount ?? "UNKNOWN"}</dd></div>
        <div><dt>EXCLUDED CATEGORIES</dt><dd>{evidence.excludedAddressCategories.join(", ") || "UNKNOWN"}</dd></div>
        <div><dt>TOP SUSPICIOUS WALLETS</dt><dd>{wallets}</dd></div>
        <div><dt>REASON CODES</dt><dd>{reasons}</dd></div>
        <div><dt>PROVENANCE</dt><dd>{providers}</dd></div>
        <div><dt>AS OF</dt><dd>{displayDate(evidence.asOf)}</dd></div>
      </dl>
    </article>
  );
}

type CheckState = "ok" | "fail" | "unknown";

function ChecklistItem({ label, state, value }: { label: string; state: CheckState; value: string }) {
  return (
    <li data-state={state}>
      <span>{label}</span>
      <strong>{value}</strong>
    </li>
  );
}

function EntryChecklist({ token, early }: { token: TokenRecord; early: EarlyRadarRecord | null }) {
  const risk = token.candidate?.riskDisposition ?? early?.riskDisposition ?? "UNKNOWN";
  const confidence = token.candidate?.scoreConfidence ?? early?.earlyScoreConfidence ?? null;
  return (
    <article className="detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Evidence completeness</p>
          <h3>ENTRY READINESS CONTEXT</h3>
        </div>
        <small>NOT AN AUTHORIZATION</small>
      </div>
      <ul className="checklist">
        <ChecklistItem
          label="Risk disposition"
          state={risk === "PASS" ? "ok" : risk === "BLOCK" ? "fail" : "unknown"}
          value={risk}
        />
        <ChecklistItem
          label="Hard blocks"
          state={early === null ? "unknown" : early.hardBlockReasons.length === 0 ? "ok" : "fail"}
          value={early === null ? "UNKNOWN" : early.hardBlockReasons.length === 0 ? "NONE" : String(early.hardBlockReasons.length)}
        />
        <ChecklistItem
          label="Liquidity observed"
          state={early?.liquidityUsd != null ? "ok" : "unknown"}
          value={early?.liquidityUsd != null ? formatUsd(early.liquidityUsd) : "UNKNOWN"}
        />
        <ChecklistItem
          label="Price impact observed"
          state={early?.priceImpactBps != null ? "ok" : "unknown"}
          value={early?.priceImpactBps != null ? `${early.priceImpactBps} bps` : "UNKNOWN"}
        />
        <ChecklistItem
          label="Score confidence"
          state={confidence != null ? "ok" : "unknown"}
          value={formatConfidence(confidence)}
        />
        <ChecklistItem
          label="Smart money confluence"
          state={early?.smartMoneyConfluence != null ? "ok" : "unknown"}
          value={early?.smartMoneyConfluence != null ? formatScore(early.smartMoneyConfluence) : "UNKNOWN"}
        />
      </ul>
    </article>
  );
}

function SignalSummary({ early }: { early: EarlyRadarRecord | null }) {
  return (
    <article className="detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Ultra-early projection</p>
          <h3>SIGNAL SUMMARY</h3>
        </div>
        <small>ADVISORY</small>
      </div>
      {early === null ? (
        <p className="muted-copy">No ultra-early projection exists for this token in the current read page.</p>
      ) : (
        <dl className="detail-list">
          <div><dt>EARLY STATE</dt><dd>{early.earlyState}</dd></div>
          <div><dt>EARLY SCORE</dt><dd>{early.earlyScore === null ? "UNKNOWN" : `${formatScore(early.earlyScore)} / 100`}</dd></div>
          <div><dt>CONFIDENCE</dt><dd>{formatConfidence(early.earlyScoreConfidence)}</dd></div>
          <div><dt>SHADOW ENTRY</dt><dd>{early.shadowEntryStatus}</dd></div>
          <div><dt>EXTERNAL LEAD</dt><dd>{early.externalCallLeadTimeMs === null ? "UNKNOWN" : `${early.externalCallLeadTimeMs}ms`}</dd></div>
          <div><dt>FIRST-SEEN LATENCY</dt><dd>{early.firstSeenLatencyMs === null ? "UNKNOWN" : `${early.firstSeenLatencyMs}ms`}</dd></div>
        </dl>
      )}
    </article>
  );
}

function ProvenancePanel({ token, entries }: { token: TokenRecord; entries: TimelineRecord[] }) {
  const providers = new Set<string>();
  for (const entry of entries) {
    for (const provenance of entry.provenance) providers.add(provenance.provider);
  }
  return (
    <article className="detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Evidence provenance</p>
          <h3>PROVENANCE</h3>
        </div>
        <small>RUNTIME SOURCES</small>
      </div>
      <dl className="detail-list">
        <div><dt>CHAIN</dt><dd>{token.chain}</dd></div>
        <div><dt>PROGRAM</dt><dd>{token.tokenProgram}</dd></div>
        <div><dt>STATUS</dt><dd>{token.status}</dd></div>
        <div><dt>DECIMALS</dt><dd>{token.decimals ?? "UNKNOWN"}</dd></div>
      </dl>
      {providers.size === 0 ? (
        <p className="muted-copy">PROVENANCE UNKNOWN — no timeline providers reported.</p>
      ) : (
        <ul className="evidence-tags">
          {[...providers].map((provider) => <li key={provider}>{provider}</li>)}
        </ul>
      )}
    </article>
  );
}

function MetadataPanels({ token }: { token: TokenRecord }) {
  const lifecycle = token.launchLifecycle;
  const lifecycleState = lifecycle?.lifecycleState ?? "UNKNOWN";
  const routeState = lifecycle?.routeState ?? "UNKNOWN";
  const routeAvailable = lifecycle?.routeAvailable === null || lifecycle?.routeAvailable === undefined
    ? "UNKNOWN"
    : lifecycle.routeAvailable ? "YES" : "NO";
  const lifecycleNumber = (value: number | null, divisor = 1): string =>
    value === null || !Number.isFinite(value / divisor) ? "UNKNOWN" : (value / divisor).toFixed(1);
  const lifecycleDate = (value: string | null): string => displayDate(value);
  const lifecycleText = (value: string | null): string => value ?? "UNKNOWN";
  const lifecycleAddress = (value: string | null): string =>
    value === null ? "UNKNOWN" : shortIdentity(value, 10);
  const provenance = lifecycle?.provenance.length
    ? [...new Set(lifecycle.provenance.map((item) => item.provider))].join(", ")
    : "UNKNOWN";
  const lifecycleConfidence = lifecycle === null ||
    ["UNKNOWN", "CONFLICTED", "INVALID"].includes(lifecycle.qualityState)
    ? "UNKNOWN"
    : formatConfidence(lifecycle.confidence);
  return (
    <section aria-label="Token metadata" className="overview-grid">
      <article className="detail-panel">
        <span className="card-label">CREATOR WALLET</span>
        {token.creatorWallet ? (
          <Link href={`/wallets/${token.creatorWallet}`}>
            <code title={token.creatorWallet}>{shortIdentity(token.creatorWallet, 12)}</code>
          </Link>
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
      <article className="detail-panel">
        <span className="card-label">LAUNCH / ROUTE</span>
        <strong>{lifecycleState}</strong>
        <small className="muted-copy">ROUTE {routeState}; unknown remains unknown until discovery evidence is complete.</small>
      </article>
      <article aria-label="Launch lifecycle evidence" className="detail-panel detail-panel--wide">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Launch intelligence</p>
            <h3>LIFECYCLE EVIDENCE</h3>
          </div>
          <small>{lifecycle?.qualityState ?? "UNKNOWN"}</small>
        </div>
        <dl className="detail-list">
          <div><dt>ROUTE STATE</dt><dd>{routeState} / {routeAvailable}</dd></div>
          <div><dt>LAUNCHPAD</dt><dd>{lifecycleText(lifecycle?.launchpad ?? null)}</dd></div>
          <div><dt>CREATOR ADDRESS</dt><dd>{lifecycleAddress(lifecycle?.creatorAddress ?? null)}</dd></div>
          <div><dt>BONDING PROGRESS</dt><dd>{lifecycleNumber(lifecycle?.bondingCurveProgressBps ?? null, 100)}%</dd></div>
          <div><dt>QUOTE ASSET</dt><dd>{lifecycleText(lifecycle?.quoteAsset ?? null)}</dd></div>
          <div><dt>GRADUATION THRESHOLD</dt><dd>{lifecycleNumber(lifecycle?.graduationThresholdBps ?? null, 100)}%</dd></div>
          <div><dt>GRADUATED AT</dt><dd>{lifecycleDate(lifecycle?.graduatedAt ?? null)}</dd></div>
          <div><dt>FIRST VERIFIED LIQUIDITY</dt><dd>{lifecycleDate(lifecycle?.firstVerifiedDexLiquidityAt ?? null)}</dd></div>
          <div><dt>FIRST VERIFIED SWAP</dt><dd>{lifecycleDate(lifecycle?.firstVerifiedSwapAt ?? null)}</dd></div>
          <div><dt>POOL / VENUE</dt><dd>{lifecycleText(lifecycle?.poolAddress ?? null)} / {lifecycleText(lifecycle?.venue ?? null)}</dd></div>
          <div><dt>LIQUIDITY LOCK</dt><dd>{lifecycleText(lifecycle?.liquidityLockState ?? null)}</dd></div>
          <div><dt>AS OF / EXPIRES</dt><dd>{lifecycle ? `${lifecycleDate(lifecycle.asOf)} / ${lifecycleDate(lifecycle.expiresAt)}` : "UNKNOWN"}</dd></div>
          <div><dt>QUALITY / TIME</dt><dd>{lifecycle?.qualityState ?? "UNKNOWN"} / {lifecycle?.timeQuality ?? "UNKNOWN"}</dd></div>
          <div><dt>CONFIDENCE</dt><dd>{lifecycleConfidence}</dd></div>
          <div><dt>REASON CODES</dt><dd>{lifecycle?.reasonCodes.length ? lifecycle.reasonCodes.join(", ") : "UNKNOWN"}</dd></div>
          <div><dt>PROVENANCE</dt><dd>{provenance}</dd></div>
        </dl>
      </article>
    </section>
  );
}

function EvidencePanels({ entries }: { entries: TimelineRecord[] }) {
  const top10 = holderMetric(entries, ["top10_hold_percent", "holder_supply_pct", "top10_concentration_pct"]);
  const clustered = holderMetric(entries, ["clustered_supply_pct", "clustered_supply_percent", "holder_cluster_pct"]);
  return (
    <section aria-label="Explainable evidence panels" className="evidence-grid">
      <article className="detail-panel chart-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Market evidence</p>
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
        <p className="eyebrow">Holder evidence</p>
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
    <div aria-label="Event-time evidence timeline" className="timeline-list">
      {entries.map((entry) => (
        <article className="timeline-entry" key={entry.id}>
          <div className="timeline-entry__time">
            <strong>{displayDate(entry.occurredAt)}</strong>
            <small>TIME QUALITY {entry.timeQuality}</small>
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
            <EarlyAlphaEvidence entry={entry} />
          </div>
        </article>
      ))}
    </div>
  );
}

function SocialNarrative({ entries }: { entries: TimelineRecord[] }) {
  const selected = entries.filter((entry) => entry.kind.startsWith("social.") || entry.kind.startsWith("narrative."));
  return (
    <section aria-labelledby="social-title" className="detail-panel social-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Correlated context</p>
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
  timelineResult,
  early
}: {
  tokenResult: ReadResult<TokenRecord>;
  timelineResult: ReadResult<ReadPage<TimelineRecord>>;
  early?: EarlyRadarRecord | null;
}) {
  if (!tokenResult.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">Token read</span>
        <strong>{failureMessage(tokenResult)}</strong>
        <p>The token projection could not be safely loaded.</p>
        <Link href="/radar">BACK TO RADAR</Link>
      </div>
    );
  }

  const token = tokenResult.data;
  if (!token) {
    return <div className="read-state" role="status"><strong>TOKEN NOT FOUND</strong><Link href="/radar">BACK TO RADAR</Link></div>;
  }

  const earlyRecord = early ?? null;
  const entries = timelineResult.ok ? timelineResult.data.items : null;

  return (
    <>
      <TokenHeader early={earlyRecord} token={token} />
      <div className="tw-grid">
        <div className="tw-main">
          <MetadataPanels token={token} />
          {entries === null ? (
            <div className="read-state read-state--error" role="status">
              <span className="eyebrow">Evidence timeline</span>
              <strong>{failureMessage(timelineResult)}</strong>
              <p>Token metadata is available; evidence remains unavailable.</p>
            </div>
          ) : (
            <>
              <EvidencePanels entries={entries} />
              <section aria-labelledby="timeline-title" className="detail-panel timeline-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">No-lookahead evidence</p>
                    <h3 id="timeline-title">Evidence timeline</h3>
                  </div>
                  <small>OCCURRED → OBSERVED → INGESTED</small>
                </div>
                <TokenTimeline entries={entries} />
              </section>
              <SocialNarrative entries={entries} />
            </>
          )}
        </div>
        <Inspector>
          <RiskFactors early={earlyRecord} token={token} />
          <InsiderEvidencePanel token={token} />
          <EntryChecklist early={earlyRecord} token={token} />
          <SignalSummary early={earlyRecord} />
          <ProvenancePanel entries={entries ?? []} token={token} />
        </Inspector>
      </div>
      <div className="boundary-strip" role="note">
        <strong>NO LIVE ORDERS</strong>
        <span>Evidence and external labels remain read-only context for review.</span>
      </div>
    </>
  );
}
