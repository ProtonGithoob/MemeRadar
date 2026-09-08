import Link from "next/link";

import { SafetyBadge } from "./status-badges";
import type {
  ControlConfigRecord,
  ControlStateRecord,
  ReadFailureReason,
  ReadResult,
  RuntimeSettingRecord,
  RuntimeSettingsRecord
} from "../lib/read-api";

const configFields = [
  ["alert_max_messages_per_window", "Alert messages / window"],
  ["alert_rate_limit_window_seconds", "Alert window seconds"],
  ["decision_watch_threshold", "Watch threshold"],
  ["decision_strong_setup_threshold", "Strong setup threshold"],
  ["decision_entry_ready_threshold", "Entry-ready threshold"],
  ["decision_minimum_confidence", "Minimum confidence"]
] as const;

const permissions = [
  ["VIEWER", "Read state and validated configuration"],
  ["OPERATOR", "Viewer access plus pause/resume analysis and activate the restrictive execution stop"],
  ["ADMIN", "Operator access plus validated configuration mutation"],
  ["EXECUTION", "Read access plus activate the restrictive execution stop"]
] as const;

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function failureMessage(reason: ReadFailureReason, subject: string): string {
  switch (reason) {
    case "NOT_CONFIGURED": return `${subject} NOT CONFIGURED`;
    case "UNAUTHORIZED": return `${subject} AUTHORIZATION UNAVAILABLE`;
    case "INVALID_RESPONSE": return "INVALID READ RESPONSE";
    case "UNAVAILABLE": return `${subject} UNAVAILABLE`;
  }
}

function configDisplayValue(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "UNKNOWN";
}

function runtimeLabel(value: string): string {
  return value.replaceAll("_", " ").toUpperCase();
}

function runtimeValue(item: RuntimeSettingRecord): React.ReactNode {
  if (item.secret) return <strong>SECRET VALUE HIDDEN</strong>;
  if (item.value === null) return <strong>{item.state}</strong>;
  if (typeof item.value === "boolean") return <strong>{item.value ? "ENABLED" : "DISABLED"}</strong>;
  return <strong>{String(item.value)}</strong>;
}

function RuntimeSettingsPanel({ result }: { result: ReadResult<RuntimeSettingsRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{failureMessage(result.reason, "RUNTIME SETTINGS")}</strong>
        <p>No runtime provider or credential values were substituted.</p>
      </div>
    );
  }
  return (
    <div className="settings-runtime">
      <div className="settings-config__meta">
        <span><b>API</b> {result.data.apiVersion}</span>
        <span><b>AS OF</b> {readableDate(result.data.asOf)}</span>
        <span><b>BOUNDARY</b> LOCKED</span>
      </div>
      <div className="settings-runtime-grid">
        {Object.entries(result.data.groups).map(([group, items]) => (
          <section className="settings-runtime-group" key={group} aria-labelledby={`runtime-${group}`}>
            <h4 id={`runtime-${group}`}>{runtimeLabel(group)}</h4>
            {items.length === 0 ? <p className="muted-copy">UNAVAILABLE</p> : (
              <dl className="settings-runtime-list">
                {items.map((item) => (
                  <div key={item.key}>
                    <dt>{runtimeLabel(item.key)}</dt>
                    <dd>{runtimeValue(item)}<small>{item.state}</small></dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}

function ProtectedModesPanel({ result }: { result: ReadResult<ControlStateRecord> }) {
  const modes = result.ok ? result.data.protectedModes : null;
  const entries = [
    { label: "ANALYSIS ONLY", value: modes ? modes.analysisOnly : null, tone: "safe", detail: "Evidence collection stays on." },
    { label: "PAPER TRADING", value: modes ? modes.paperTrading : null, tone: "paper", detail: "Simulated outcomes only." },
    { label: "MANUAL EXECUTION", value: modes ? modes.manualExecution : null, tone: "disabled", detail: "Operator approval path is locked." },
    { label: "AUTO EXECUTION", value: modes ? modes.autoExecution : null, tone: "disabled", detail: "No autonomous orders are possible." }
  ] as const;
  return (
    <div className="settings-block">
      <div className="panel-heading">
        <div><p className="eyebrow">PROTECTED MODES</p><h3>Operating policy</h3></div>
        <small>ENFORCED BY API CONFIGURATION</small>
      </div>
      <div className="mode-grid">
        {entries.map((entry) => (
          <article className={`mode-card mode-card--${entry.tone}`} key={entry.label}>
            <span className="card-label">{entry.label}</span>
            <strong className={`mode-value mode-value--${entry.tone}`}>
              {entry.value === null ? "UNKNOWN" : entry.value ? "Enabled" : "Disabled"}
            </strong>
            <small>{entry.detail}</small>
          </article>
        ))}
      </div>
    </div>
  );
}

function StatePanel({ result }: { result: ReadResult<ControlStateRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{failureMessage(result.reason, "CONTROL STATE")}</strong>
        <p>Protected mode labels remain visible; no state was inferred from this failed read.</p>
      </div>
    );
  }
  return (
    <div className="settings-state-grid">
      <div className="settings-state-card">
        <span className="card-label">ANALYSIS CONTROL</span>
        <strong>{result.data.analysisPaused ? "ANALYSIS PAUSED" : "ANALYSIS ACTIVE"}</strong>
        <small>Updated by {result.data.updatedBy} at {readableDate(result.data.updatedAt)}</small>
      </div>
      <div className="settings-state-card settings-state-card--locked">
        <span className="card-label">EXECUTION CONTROL</span>
        <strong>{result.data.executionKillSwitch ? "EXECUTION KILL SWITCH ACTIVE" : "EXECUTION KILL SWITCH INACTIVE"}</strong>
        <small>Version {result.data.version}; correlation {result.data.correlationId}</small>
      </div>
    </div>
  );
}

function ConfigPanel({ result }: { result: ReadResult<ControlConfigRecord> }) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{failureMessage(result.reason, "CONTROL CONFIG")}</strong>
        <p>No configuration values were substituted.</p>
      </div>
    );
  }
  const config = result.data.config;
  return (
    <div className="settings-config">
      <div className="settings-config__meta">
        <span><b>VERSION</b> {result.data.version}</span>
        <span><b>HASH</b> {result.data.configHash}</span>
        <span><b>ACTOR</b> {result.data.actor}</span>
        <span><b>CREATED</b> {readableDate(result.data.createdAt)}</span>
      </div>
      <div className="settings-config__status">
        <SafetyBadge label="CONFIGURATION" value="VALIDATED" tone="safe" />
        <span>{result.data.decisionAffecting ? "DECISION-AFFECTING" : "NON-DECISION"}</span>
      </div>
      <dl className="settings-field-list">
        {configFields.map(([key, label]) => (
          <div key={key}>
            <dt title={label}>{key}</dt>
            <dd>{configDisplayValue(config[key])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function PermissionMatrix() {
  return (
    <section className="detail-panel permission-panel" aria-labelledby="permission-title">
      <div className="panel-heading">
        <div><p className="eyebrow">AUTHENTICATED CONTROL BOUNDARY</p><h3 id="permission-title">Permission gates</h3></div>
        <small>READ-ONLY UI</small>
      </div>
      <p className="muted-copy">The API, not the browser, enforces each role. Settings changes require a server-side authenticated control request.</p>
      <div className="permission-list">
        {permissions.map(([role, description]) => (
          <div className="permission-row" key={role}>
            <strong>{role}</strong>
            <span>{description}</span>
          </div>
        ))}
      </div>
      <p className="muted-copy">Protected operating modes cannot be edited here. No signing or order submission path exists.</p>
    </section>
  );
}

export function SettingsDashboard({
  stateResult,
  configResult,
  runtimeSettingsResult
}: {
  stateResult: ReadResult<ControlStateRecord>;
  configResult: ReadResult<ControlConfigRecord>;
  runtimeSettingsResult: ReadResult<RuntimeSettingsRecord>;
}) {
  return (
    <>
      <section className="section-block intelligence-section" aria-labelledby="settings-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CONTROL PLANE / VALIDATED READ</p>
            <h3 id="settings-title">Settings and controls</h3>
          </div>
          <p className="section-note">Configuration is immutable, audited and permission-gated.</p>
        </div>
        <ProtectedModesPanel result={stateResult} />
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">EMERGENCY STATE</p><h3>Current control state</h3></div></div>
          <StatePanel result={stateResult} />
        </div>
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">REPLAY IDENTITY</p><h3>Validated configuration</h3></div></div>
          <ConfigPanel result={configResult} />
        </div>
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">RUNTIME / SECRET-SAFE READ</p><h3>Runtime configuration</h3></div><small>VALUES ARE ALLOW-LISTED</small></div>
          <RuntimeSettingsPanel result={runtimeSettingsResult} />
        </div>
        <PermissionMatrix />
      </section>
      <section className="boundary-strip" aria-labelledby="settings-boundary-title">
        <div>
          <p className="eyebrow">PROTECTED MODES</p>
          <h3 id="settings-boundary-title">No browser-side control authority</h3>
          <p>Use the authenticated API boundary for permitted analysis controls; execution remains locked.</p>
        </div>
        <Link className="back-link" href="/audit">VIEW AUDIT</Link>
      </section>
    </>
  );
}
