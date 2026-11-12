import Link from "next/link";

import { ScanRefresh } from "../components/scan-refresh";
import { fetchCandidates, fetchEarlyRadar, fetchOperations, fetchRuntimeSettings } from "../lib/read-api";

const objectRows = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> =>
        typeof item === "object" && item !== null && !Array.isArray(item))
    : [];
const displayValue = (value: unknown) =>
  typeof value === "string" || typeof value === "number" ? String(value) : "UNKNOWN";
/** One named metric group from the operations payload, or null when absent. */
const metricGroup = (metrics: Record<string, unknown> | null, key: string): Record<string, unknown> | null => {
  const value = metrics?.[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
};
/** A numeric counter as text; a missing or non-numeric value is UNKNOWN, never zero. */
const counter = (group: Record<string, unknown> | null, key: string) =>
  typeof group?.[key] === "number" ? String(group[key]) : "UNKNOWN";

export default async function ScanMonitorPage() {
  const [candidates, early, operations, settings] = await Promise.all([
    fetchCandidates({}), fetchEarlyRadar(), fetchOperations(), fetchRuntimeSettings()
  ]);
  const rejected = early.ok
    ? early.data.items.filter((item) => item.earlyState === "REJECT/LOW" || item.riskDisposition === "BLOCK")
    : [];
  const telegramSettings = settings.ok ? settings.data.settings ?? [] : [];
  const telegramReady = ["telegram_bot_token", "telegram_chat_id"].every((key) =>
    telegramSettings.some((item) => item.key === key && item.configuredState === "CONFIGURED")
  );
  const metrics = operations.ok ? operations.data.metrics as Record<string, unknown> : null;
  const delivery = metricGroup(metrics, "notification_delivery");
  const coverage = metricGroup(metrics, "stream_coverage");
  const ingestion = metricGroup(metrics, "ingestion");
  const unresolvedRanges = objectRows(coverage?.unresolved_ranges);
  const verificationRanges = objectRows(coverage?.verification_ranges);
  const preIdentity = metricGroup(metrics, "pre_identity");
  const deliveryCount = (key: string) => counter(delivery, key);
  const coverageCount = (key: string) => counter(coverage, key);
  const preIdentityCount = (key: string) => counter(preIdentity, key);
  const ingestionCount = (key: string) => counter(ingestion, key);
  const unknownAge = typeof delivery?.delivery_unknown_oldest_age_seconds === "number"
    ? `${delivery.delivery_unknown_oldest_age_seconds} seconds`
    : "UNKNOWN";
  const unknownReasons = delivery?.delivery_unknown_reason_counts_sample
    && typeof delivery.delivery_unknown_reason_counts_sample === "object"
    && !Array.isArray(delivery.delivery_unknown_reason_counts_sample)
    ? Object.entries(delivery.delivery_unknown_reason_counts_sample as Record<string, unknown>)
        .filter((entry): entry is [string, number] => typeof entry[1] === "number")
        .map(([code, count]) => `${code} (${count})`).join(", ") || "No reason recorded"
    : "UNKNOWN";
  const reasonSampleNote = delivery?.delivery_unknown_reason_sample_truncated === true ? " (first 100 oldest)" : "";

  return (
    <div className="scan-monitor">
      <header className="scan-header">
        <div><p className="eyebrow">DISCOVERY / OBSERVABILITY</p><h1>Scan Monitor</h1>
          <p>See recorded candidates, rejected or blocked decisions, and provider activity.</p></div>
        <div><ScanRefresh /><p className="section-note">Refreshes every 30 seconds while this page is visible.</p></div>
      </header>

      <section className="section-block" aria-labelledby="scan-status">
        <div className="section-heading"><div><p className="eyebrow">SYSTEM STATUS</p><h2 id="scan-status">Is data flowing?</h2></div></div>
        {!operations.ok ? <p role="status">Operations data unavailable: {operations.reason}. Activity cannot be confirmed.</p> : <>
          <div className="operations-counter-grid">
            <div className="detail-panel"><span className="card-label">OPERATIONS STATE</span><strong>{operations.data.overallState}</strong><small>Snapshot: {operations.data.asOf}</small></div>
            <div className="detail-panel"><span className="card-label">RECORDED CANDIDATES</span><strong>{candidates.ok ? candidates.data.items.length : "UNKNOWN"}</strong><small>Items in this page, not a total</small></div>
            <div className="detail-panel"><span className="card-label">REJECTED / BLOCKED</span><strong>{early.ok ? rejected.length : "UNKNOWN"}</strong><small>Early radar items in this page</small></div>
            <div className="detail-panel"><span className="card-label">SOURCE COVERAGE</span><strong>{typeof coverage?.state === "string" ? coverage.state : "UNKNOWN"}</strong><small>Known unresolved gaps: {coverageCount("unresolved_gap_count")}</small><small>Verified recovery ranges: {coverageCount("verified_recovery_ranges")}</small><small>Subscription completeness is not proven.</small>
              {unresolvedRanges.length > 0 ? <details><summary>Unresolved slot ranges ({unresolvedRanges.length})</summary><ul>{unresolvedRanges.map((range, index) => <li key={`${displayValue(range.gap_id)}:${index}`}>{displayValue(range.provider)} · {displayValue(range.stream_id)} · slots {displayValue(range.from_slot)}–{displayValue(range.to_slot)} · {displayValue(range.status)} · {displayValue(range.last_error_class)}</li>)}</ul>{coverage?.unresolved_ranges_truncated === true ? <small>Additional ranges are omitted from this bounded view.</small> : null}</details> : null}
              {verificationRanges.length > 0 ? <details><summary>Recovery verification ranges ({verificationRanges.length})</summary><ul>{verificationRanges.map((range, index) => <li key={`${displayValue(range.gap_id)}:${index}`}>slots {displayValue(range.from_slot)}–{displayValue(range.to_slot)} · {displayValue(range.verification_status)} · provider {displayValue(range.provider)} · program {displayValue(range.program_scope)} · commitment {displayValue(range.commitment)}</li>)}</ul>{coverage?.verification_ranges_truncated === true ? <small>Additional verification records are omitted from this bounded view.</small> : null}<small>Range verification does not establish complete program-subscription coverage.</small></details> : null}
            </div>
            <div className="detail-panel"><span className="card-label">LIVE INGESTION</span><strong>Launches: {ingestionCount("launches_observed")}</strong>
              <small>Trade tape events: {ingestionCount("trade_events_emitted")} · capped: {ingestionCount("trade_events_capped")}</small>
              <small>Decode failures: {ingestionCount("decoder_failures")} launch · {ingestionCount("trade_event_decode_failures")} trade</small>
              <small>Reconnects: {ingestionCount("stream_reconnects")} · unavailable transactions: {ingestionCount("transactions_unavailable")}</small>
              <small>Launches in last hour: {ingestionCount("launches_per_hour")} · p95 latency: {typeof ingestion?.latency_p95_ms === "number" ? `${ingestion.latency_p95_ms} ms` : "UNKNOWN"}</small>
              <small>Counters since worker start; snapshot age: {typeof ingestion?.snapshot_age_seconds === "number" ? `${ingestion.snapshot_age_seconds} seconds` : "UNKNOWN"}</small></div>
            <div className="detail-panel"><span className="card-label">PRE-IDENTITY DIAGNOSTICS</span><strong>Recorded: {preIdentityCount("recorded_rejections")}</strong><small>Identity-linked projections: {preIdentityCount("identity_linked_projections")}</small><small>Persisted fetch/decode failures only; this is not a complete source-event denominator.</small></div>
          </div>
          <p className="section-note">A provider state is a health snapshot; it does not by itself prove that a scan is running now.</p>
          {operations.data.providers.length === 0 ? <p>No provider health evidence available.</p> : <div className="scan-list">{operations.data.providers.map((provider, index) => <article className="detail-panel scan-row" key={`${provider.provider}:${provider.capability}:${index}`}>
            <div><strong>{provider.displayName || provider.provider}</strong><p>{provider.capability} · {provider.chains?.join(", ") || "chain unknown"}</p></div>
            <div><strong>{provider.state}</strong><p>Checked: {provider.checkedAt}</p><small>{provider.reasonCodes.join(", ") || provider.errorClass || "No reason reported"}</small></div>
          </article>)}</div>}
        </>}
      </section>

      <section className="section-block" aria-labelledby="scan-telegram">
        <div className="section-heading"><div><p className="eyebrow">NOTIFICATIONS</p><h2 id="scan-telegram">Telegram</h2></div><Link href="/settings">Open settings →</Link></div>
        <div className="detail-panel">
          <strong>{!settings.ok ? "CONFIGURATION UNKNOWN" : telegramReady ? "BOT AND CHAT CONFIGURED" : "BOT OR CHAT NOT CONFIGURED"}</strong>
          <p>Delivered alerts: {deliveryCount("delivered_alerts")} · Pending: {deliveryCount("pending")} · Processing: {deliveryCount("processing")} · Dead letter: {deliveryCount("dead_letter")}</p>
          <p>Unknown delivery outcomes: {deliveryCount("delivery_unknown")}</p>
          <p>Oldest unknown: {unknownAge} · Reasons{reasonSampleNote}: {unknownReasons}</p>
          <p>Last delivered: {!delivery ? "UNKNOWN" : typeof delivery.last_delivered_at === "string" ? delivery.last_delivered_at : "No recorded delivery"}</p>
          <small>Only EARLY WATCH or stronger signals with fresh, passed safety evidence and no unresolved stream gap are queued. Signals older than five minutes are not sent. Delivery history includes alerts sent before the current filter. Configuration alone does not confirm delivery.</small>
        </div>
      </section>

      <section className="section-block" aria-labelledby="scan-candidates">
        <div className="section-heading"><div><p className="eyebrow">RECORDED DISCOVERY</p><h2 id="scan-candidates">Scanned candidates</h2></div><Link href="/radar">Open radar →</Link></div>
        {!candidates.ok ? <p role="status">Candidates unavailable: {candidates.reason}.</p> : candidates.data.items.length === 0 ? <p>No candidate records returned. This does not confirm that scanning is active.</p> : <div className="scan-list">{candidates.data.items.map((item) => <article className="detail-panel scan-row" key={item.id}>
          <div><Link href={`/tokens/${item.tokenId}`}><strong>{item.symbol || item.mintAddress}</strong></Link><p>{item.chain} · {item.discoverySource}</p><small>{item.mintAddress}</small></div>
          <div><strong>{item.state} · {item.riskDisposition}</strong><p>Discovered: {item.discoveredAt}</p><small>{item.riskReasonCodes.join(", ") || "No risk reason reported"}</small></div>
        </article>)}</div>}
        {candidates.ok && candidates.data.hasMore ? <p className="section-note">More records exist; this view shows the first page.</p> : null}
      </section>

      <section className="section-block" aria-labelledby="scan-rejected">
        <div className="section-heading"><div><p className="eyebrow">RECORDED DECISIONS</p><h2 id="scan-rejected">Rejected or blocked</h2></div><Link href="/ultra-early">Open ultra-early →</Link></div>
        {!early.ok ? <p role="status">Early decisions unavailable: {early.reason}.</p> : rejected.length === 0 ? <p>No rejected or blocked decisions in the returned page.</p> : <div className="scan-list">{rejected.map((item) => <article className="detail-panel scan-row" key={item.candidateId}>
          <div><Link href={`/tokens/${item.tokenId}`}><strong>{item.symbol || item.mintAddress}</strong></Link><p>{item.firstSeenSource} · {item.firstSeenAt}</p></div>
          <div><strong>{item.earlyState} · {item.riskDisposition}</strong><p>{[...new Set([...item.hardBlockReasons, ...item.reasonCodes])].join(", ") || "No reason reported"}</p></div>
        </article>)}</div>}
        <p className="section-note">Only saved early-radar decisions are shown. The pre-identity counters above cover persisted fetch/decode failures; events never delivered by a source remain unknown, so this is not a complete ignored-event log.{early.ok && early.data.hasMore ? " More early-radar records exist beyond this page." : ""}</p>
      </section>
    </div>
  );
}
