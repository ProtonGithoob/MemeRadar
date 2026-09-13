"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SafetyBadge } from "./status-badges";
import { PageHeader } from "./ui";
import type {
  ControlConfigRecord,
  ControlStateRecord,
  ReadFailureReason,
  ReadResult,
  RuntimeSettingRecord,
  RuntimeSettingsRecord
} from "../lib/read-api";

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

function runtimeLabel(value: string): string {
  return value.replaceAll("_", " ").toUpperCase();
}

function runtimeValue(item: RuntimeSettingRecord): React.ReactNode {
  if (item.secret) return <strong>SECRET VALUE HIDDEN</strong>;
  const value = item.currentEffectiveValue ?? item.value;
  if (value === null) return <strong>{item.state}</strong>;
  if (typeof value === "boolean") return <strong>{value ? "ENABLED" : "DISABLED"}</strong>;
  return <strong>{String(value)}</strong>;
}

function settingLabel(item: RuntimeSettingRecord): string {
  return runtimeLabel(item.key);
}

function settingValue(item: RuntimeSettingRecord): string | number | boolean {
  const value = item.currentEffectiveValue ?? item.value;
  if (typeof value === "boolean" || typeof value === "number") return value;
  return value ?? "";
}

function effectiveItems(data: RuntimeSettingsRecord): Array<RuntimeSettingRecord & { category: string }> {
  if (data.settings && data.settings.length > 0) {
    return data.settings.map((item) => ({ ...item, category: item.category ?? "general/runtime" }));
  }
  return Object.entries(data.groups).flatMap(([category, items]) =>
    items.map((item) => ({ ...item, category }))
  );
}

export type RuntimeSettingDraftResult =
  | { ok: true; value: string | number | boolean | null }
  | { ok: false; reason: "REQUIRED" | "INVALID_NUMBER" | "INTEGER_REQUIRED" | "BELOW_MINIMUM" | "ABOVE_MAXIMUM" };

export function validateRuntimeSettingDraft(
  item: RuntimeSettingRecord,
  raw: string | number | boolean
): RuntimeSettingDraftResult {
  if (typeof raw === "boolean" || (item.type !== "integer" && item.type !== "number")) {
    return { ok: true, value: raw };
  }
  const text = typeof raw === "number" ? String(raw) : raw.trim();
  if (text === "") return item.nullable === true ? { ok: true, value: null } : { ok: false, reason: "REQUIRED" };
  const value = Number(text);
  if (!Number.isFinite(value)) return { ok: false, reason: "INVALID_NUMBER" };
  if (item.type === "integer" && !Number.isInteger(value)) return { ok: false, reason: "INTEGER_REQUIRED" };
  if (item.minimum !== null && item.minimum !== undefined && value < item.minimum) {
    return { ok: false, reason: "BELOW_MINIMUM" };
  }
  if (item.maximum !== null && item.maximum !== undefined && value > item.maximum) {
    return { ok: false, reason: "ABOVE_MAXIMUM" };
  }
  return { ok: true, value };
}

function RuntimeSettingEditor({ data }: { data: RuntimeSettingsRecord }) {
  const items = useMemo(() => effectiveItems(data), [data]);
  const categories = useMemo(
    () => Array.from(new Set(items.map((item) => item.category))),
    [items]
  );
  const [category, setCategory] = useState(categories[0] ?? "general/runtime");
  const [drafts, setDrafts] = useState<Record<string, string | number | boolean>>({});
  const [clearKeys, setClearKeys] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const dirty = Object.keys(drafts).length > 0 || clearKeys.length > 0;
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [clearKeys.length, drafts]);

  const selectedCategory = categories.includes(category) ? category : categories[0] ?? "general/runtime";
  const visibleItems = items.filter((item) => item.category === selectedCategory);
  const canMutate = data.canMutate === true;
  const dirty = Object.keys(drafts).length > 0 || clearKeys.length > 0;
  const draftItems = new Map(items.map((item) => [item.key, item]));
  const invalidDraft = Object.entries(drafts).some(([key, raw]) => {
    const item = draftItems.get(key);
    return item !== undefined && !validateRuntimeSettingDraft(item, raw).ok;
  });

  function updateDraft(item: RuntimeSettingRecord, raw: string | boolean): void {
    setDrafts((current) => ({ ...current, [item.key]: raw }));
    setClearKeys((current) => current.filter((key) => key !== item.key));
    setMessage(null);
  }

  function clearSecret(key: string): void {
    setDrafts((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setClearKeys((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key]);
    setMessage(null);
  }

  async function save(): Promise<void> {
    if (!canMutate || !dirty || invalidDraft || reason.trim().length === 0) {
      setMessage("Enter an audit reason and change at least one setting.");
      return;
    }
    const changes: Record<string, string | number | boolean | null> = {};
    for (const [key, raw] of Object.entries(drafts)) {
      const item = draftItems.get(key);
      if (item === undefined) continue;
      const validation = validateRuntimeSettingDraft(item, raw);
      if (!validation.ok) {
        setMessage(`INVALID ${runtimeLabel(key)} — ${validation.reason}`);
        return;
      }
      changes[key] = validation.value;
    }
    setSaving(true);
    setMessage(null);
    try {
      const response = await fetch("/api/control/runtime-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          changes,
          clear: clearKeys,
          reason: reason.trim(),
          version: data.version ?? null
        })
      });
      if (response.status === 409) {
        setMessage("VERSION CONFLICT — reload effective state and review the changes.");
      } else if (!response.ok) {
        setMessage("SETTINGS UPDATE FAILED — no values were applied.");
      } else {
        setMessage("SETTINGS SAVED — reloading effective state.");
        window.setTimeout(() => window.location.reload(), 250);
      }
    } catch {
      setMessage("CONTROL GATEWAY UNAVAILABLE — no values were applied.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="settings-runtime">
      <div className="settings-config__meta">
        <span><b>API</b> {data.apiVersion}</span>
        <span><b>VERSION</b> {data.version ?? "runtime-settings-v0"}</span>
        <span><b>UPDATED</b> {readableDate(data.updatedAt ?? data.asOf)}</span>
        <span><b>BOUNDARY</b> LOCKED</span>
      </div>
      <div className="settings-category-tabs" role="tablist" aria-label="Runtime setting categories">
        {categories.map((item) => (
          <button
            aria-selected={selectedCategory === item}
            className={selectedCategory === item ? "preset-chip preset-chip--active" : "preset-chip"}
            key={item}
            onClick={() => setCategory(item)}
            role="tab"
            type="button"
          >
            {runtimeLabel(item)}
          </button>
        ))}
      </div>
      <section className="settings-runtime-group" aria-labelledby="runtime-category">
        <h4 id="runtime-category">{runtimeLabel(selectedCategory)}</h4>
        {visibleItems.length === 0 ? <p className="muted-copy">UNAVAILABLE</p> : (
          <div className="settings-runtime-editor">
            {visibleItems.map((item) => {
              const current = settingValue(item);
              const draft = drafts[item.key];
              const value = draft ?? current;
              const editable = canMutate && item.mutable === true && item.protected !== true;
              const isSecret = item.secret;
              return (
                <div className="settings-runtime-row" key={item.key}>
                  <div className="settings-runtime-row__label">
                    <strong>{settingLabel(item)}</strong>
                    <small>{item.description ?? "Runtime setting"}</small>
                  </div>
                  <div className="settings-runtime-row__control">
                    {isSecret ? (
                      <div className="settings-secret-control">
                        <span>{item.configuredState ?? (item.state === "CONFIGURED" ? "CONFIGURED" : "NOT CONFIGURED")}</span>
                        {editable ? (
                          <>
                            <input
                              aria-label={"Replace " + settingLabel(item)}
                              onChange={(event) => updateDraft(item, event.target.value)}
                              placeholder="Replace secret"
                              type="password"
                              value={typeof draft === "string" ? draft : ""}
                            />
                            <button onClick={() => clearSecret(item.key)} type="button">
                              {clearKeys.includes(item.key) ? "Undo clear" : "Clear"}
                            </button>
                          </>
                        ) : null}
                      </div>
                    ) : item.type === "boolean" ? (
                      <label className="settings-toggle">
                        <input
                          aria-label={settingLabel(item)}
                          checked={Boolean(value)}
                          disabled={!editable}
                          onChange={(event) => updateDraft(item, event.target.checked)}
                          type="checkbox"
                        />
                        <span>{value ? "ENABLED" : "DISABLED"}</span>
                      </label>
                    ) : item.allowedValues && item.allowedValues.length > 0 ? (
                      <select
                        aria-label={settingLabel(item)}
                        disabled={!editable}
                        onChange={(event) => updateDraft(item, event.target.value)}
                        value={String(value)}
                      >
                        {item.allowedValues.map((allowed) => <option key={allowed} value={allowed}>{allowed}</option>)}
                      </select>
                    ) : (
                      <input
                        aria-label={settingLabel(item)}
                        disabled={!editable}
                        max={item.maximum ?? undefined}
                        min={item.minimum ?? undefined}
                        onChange={(event) => updateDraft(item, event.target.value)}
                        step={item.type === "integer" ? 1 : "any"}
                        type={item.type === "integer" || item.type === "number" ? "number" : "text"}
                        value={String(value)}
                      />
                    )}
                    <div className="settings-runtime-row__meta">
                      <span className="settings-mode-badge">{item.mode ?? "READ ONLY"}</span>
                      {item.pendingValue !== null && item.pendingValue !== undefined ? (
                        <span className="settings-pending">PENDING {String(item.pendingValue)}</span>
                      ) : item.pendingConfiguredState ? (
                        <span className="settings-pending">PENDING {item.pendingConfiguredState}</span>
                      ) : null}
                      {!isSecret ? <span>{runtimeValue(item)}</span> : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
      {canMutate ? (
        <div className="settings-runtime-actions">
          <label>
            <span>AUDIT REASON</span>
            <input
              aria-label="Audit reason"
              onChange={(event) => setReason(event.target.value)}
              placeholder="Why is this setting changing?"
              value={reason}
            />
          </label>
          <div>
            <button disabled={!dirty || invalidDraft || saving} onClick={() => void save()} type="button">
              {saving ? "SAVING…" : "SAVE CHANGED SETTINGS"}
            </button>
            <button onClick={() => window.location.reload()} type="button">RELOAD EFFECTIVE STATE</button>
            {dirty ? <span className="settings-dirty-warning">UNSAVED CHANGES</span> : null}
            {message ? <span className="settings-save-message" role="status">{message}</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
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
  return <RuntimeSettingEditor data={result.data} />;
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

function ConfigPanel({
  result,
  runtimeSettings
}: {
  result: ReadResult<ControlConfigRecord>;
  runtimeSettings: ReadResult<RuntimeSettingsRecord>;
}) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <strong>{failureMessage(result.reason, "CONTROL CONFIG")}</strong>
        <p>No configuration values were substituted.</p>
      </div>
    );
  }
  const canonicalItems = runtimeSettings.ok
    ? effectiveItems(runtimeSettings.data).filter((item) => item.decisionAffecting === true)
    : [];
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
        {canonicalItems.length === 0 ? <p className="muted-copy">DECISION SETTINGS UNKNOWN — OPEN RUNTIME CONFIGURATION</p> : canonicalItems.map((item) => (
          <div key={item.key}>
            <dt>{item.key}</dt>
            <dd>{runtimeValue(item)}</dd>
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
        <small>VIEWER / OPERATOR READ-ONLY · ADMIN EDITS ALLOW-LIST</small>
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
        <PageHeader
          eyebrow="Control plane / validated read"
          id="settings-title"
          note="Runtime changes are allow-listed, audited and permission-gated."
          title="Settings and controls"
        />
        <ProtectedModesPanel result={stateResult} />
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">EMERGENCY STATE</p><h3>Current control state</h3></div></div>
          <StatePanel result={stateResult} />
        </div>
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">REPLAY IDENTITY</p><h3>Validated configuration</h3></div></div>
          <ConfigPanel result={configResult} runtimeSettings={runtimeSettingsResult} />
        </div>
        <div className="settings-block">
          <div className="panel-heading"><div><p className="eyebrow">RUNTIME / SECRET-SAFE CONTROL</p><h3>Runtime configuration</h3></div><small>VALUES ARE ALLOW-LISTED</small></div>
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
