import Link from "next/link";

import { SafetyBadge } from "./status-badges";
import { OperatorHeader } from "./operator-header";
import { ProtectedShell } from "./radar";
import type {
  AuditEventRecord,
  ConfigVersionRecord,
  ReadFailureReason,
  ReadPage,
  ReadResult
} from "../lib/read-api";

const safeAuditKeys = new Set([
  "analysis_paused",
  "execution_kill_switch",
  "version",
  "updated_by",
  "correlation_id",
  "config_hash",
  "decision_affecting",
  "alert_max_messages_per_window",
  "alert_rate_limit_window_seconds",
  "decision_watch_threshold",
  "decision_strong_setup_threshold",
  "decision_entry_ready_threshold",
  "decision_minimum_confidence"
]);
const secretValuePattern = /(?:bearer|secret|password|private[_ -]?key|seed|api[_ -]?key|token)/i;

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function safePrimitive(value: unknown): string | null {
  if (typeof value === "boolean") return String(value);
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.length <= 256 && !secretValuePattern.test(value)) return value;
  return null;
}

function SafeFields({ values, label }: { values: Record<string, unknown>; label: string }) {
  const entries = Object.entries(values)
    .filter(([key]) => safeAuditKeys.has(key))
    .map(([key, value]) => [key, safePrimitive(value)] as const)
    .filter((entry): entry is readonly [string, string] => entry[1] !== null);
  return (
    <div className="audit-fields">
      <span className="card-label">{label}</span>
      {entries.length === 0 ? <small>NO SAFE FIELDS</small> : (
        <ul>
          {entries.map(([key, value]) => <li key={`${label}:${key}`}><code>{key}</code><span>{value}</span></li>)}
        </ul>
      )}
    </div>
  );
}

function auditFailure(reason: ReadFailureReason, subject: string): string {
  switch (reason) {
    case "NOT_CONFIGURED": return `${subject} NOT CONFIGURED`;
    case "UNAUTHORIZED": return `${subject} AUTHORIZATION UNAVAILABLE`;
    case "INVALID_RESPONSE": return "INVALID READ RESPONSE";
    case "UNAVAILABLE": return `${subject} UNAVAILABLE`;
  }
}

function AuditEvents({ result }: { result: ReadResult<ReadPage<AuditEventRecord>> }) {
  if (!result.ok) {
    return <div className="read-state read-state--error" role="status"><strong>{auditFailure(result.reason, "AUDIT EVENTS")}</strong><p>No audit event data was substituted.</p></div>;
  }
  if (result.data.items.length === 0) {
    return <div className="read-state" role="status"><strong>NO AUDIT EVENTS</strong><p>The immutable audit page is empty.</p></div>;
  }
  return (
    <div className="audit-list" aria-label="Audit events">
      {result.data.items.map((event) => (
        <article className="audit-card" key={event.id}>
          <div className="audit-card__heading">
            <div><strong>{event.action}</strong><small>{event.target}</small></div>
            <time dateTime={event.occurredAt}>{readableDate(event.occurredAt)}</time>
          </div>
          <div className="audit-meta"><span>ACTOR {event.actor}</span><span>CORRELATION {event.correlationId}</span></div>
          <div className="audit-change-grid">
            <SafeFields values={event.before} label="BEFORE" />
            <SafeFields values={event.after} label="AFTER" />
          </div>
        </article>
      ))}
    </div>
  );
}

function ConfigHistory({ result }: { result: ReadResult<ReadPage<ConfigVersionRecord>> }) {
  if (!result.ok) {
    return <div className="read-state read-state--error" role="status"><strong>{auditFailure(result.reason, "CONFIGURATION HISTORY")}</strong><p>No configuration history was substituted.</p></div>;
  }
  if (result.data.items.length === 0) {
    return <div className="read-state" role="status"><strong>NO CONFIGURATION HISTORY</strong><p>No immutable config versions are available.</p></div>;
  }
  return (
    <div className="config-history" aria-label="Configuration history">
      {result.data.items.map((config) => (
        <article className="config-history-card" key={config.id}>
          <div className="audit-card__heading">
            <div><strong>{config.version}</strong><small>{config.actor}</small></div>
            <time dateTime={config.createdAt}>{readableDate(config.createdAt)}</time>
          </div>
          <div className="audit-meta"><span>HASH {config.configHash}</span><span>{config.decisionAffecting ? "DECISION-AFFECTING" : "NON-DECISION"}</span></div>
          <SafeFields values={config.config} label="VALIDATED FIELDS" />
        </article>
      ))}
    </div>
  );
}

export function AuditDashboard({
  auditResult,
  configResult
}: {
  auditResult: ReadResult<ReadPage<AuditEventRecord>>;
  configResult: ReadResult<ReadPage<ConfigVersionRecord>>;
}) {
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <section className="section-block intelligence-section" aria-labelledby="audit-title">
        <div className="section-heading">
          <div><p className="eyebrow">IMMUTABLE CONTROL HISTORY / READ-ONLY</p><h3 id="audit-title">Audit explorer</h3></div>
          <p className="section-note">Audit and config projections are evidence, not permissions.</p>
        </div>
        <section className="settings-block" aria-labelledby="audit-events-title">
          <div className="panel-heading"><div><p className="eyebrow">OPERATOR / SYSTEM EVENTS</p><h3 id="audit-events-title">Audit events</h3></div><SafetyBadge label="MUTATION" value="API-GATED" tone="disabled" /></div>
          <AuditEvents result={auditResult} />
        </section>
        <section className="settings-block" aria-labelledby="config-history-title">
          <div className="panel-heading"><div><p className="eyebrow">REPLAY IDENTITY</p><h3 id="config-history-title">Configuration history</h3></div></div>
          <ConfigHistory result={configResult} />
        </section>
      </section>
      <section className="queue-card" aria-labelledby="audit-boundary-title">
        <div className="queue-card__icon" aria-hidden="true">⌁</div>
        <div><p className="eyebrow">SAFE PROJECTION</p><h3 id="audit-boundary-title">Sensitive values are withheld</h3><p>Only bounded allow-listed fields and correlation metadata are rendered.</p></div>
        <Link className="back-link" href="/settings">VIEW SETTINGS</Link>
      </section>
    </main>
  );
}

