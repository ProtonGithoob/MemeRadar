import Link from "next/link";

import { ProviderActions } from "./provider-actions";
import { FreshnessBadge, SafetyBadge } from "./status-badges";
import type {
  ProviderHealthRecord,
  ProviderHealthState,
  ReadPage,
  ReadResult,
  RuntimeSettingRecord,
  RuntimeSettingsRecord
} from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function quotaSummary(quota: Record<string, unknown>): string {
  const remaining = quota.remaining;
  const limit = quota.limit;
  if (
    typeof remaining === "number" && Number.isFinite(remaining) && remaining >= 0 &&
    typeof limit === "number" && Number.isFinite(limit) && limit >= 0
  ) {
    return `${remaining} remaining / ${limit} limit`;
  }
  return "QUOTA UNKNOWN";
}

function stateClass(state: ProviderHealthState): string {
  return state.toLowerCase();
}

function failureMessage(result: ReadResult<ReadPage<ProviderHealthRecord>>): string | null {
  if (result.ok) return null;
  switch (result.reason) {
    case "NOT_CONFIGURED": return "PROVIDER HEALTH NOT CONFIGURED";
    case "UNAUTHORIZED": return "PROVIDER HEALTH AUTHORIZATION UNAVAILABLE";
    case "INVALID_RESPONSE": return "INVALID READ RESPONSE";
    case "UNAVAILABLE": return "PROVIDER HEALTH UNAVAILABLE";
  }
}

function runtimeItems(settings: ReadResult<RuntimeSettingsRecord> | undefined, provider: string): RuntimeSettingRecord[] {
  if (!settings || !settings.ok) return [];
  const items = settings.data.settings ?? Object.values(settings.data.groups).flat();
  const normalized = provider.toLowerCase();
  return items.filter((item) => {
    const key = item.key.toLowerCase();
    return key.includes(normalized) || (normalized === "market" && item.category?.includes("market"));
  }).slice(0, 8);
}

function configValue(item: RuntimeSettingRecord): string {
  if (item.secret) return item.configuredState === "CONFIGURED" ? "CONFIGURED" : "NOT CONFIGURED";
  const value = item.currentEffectiveValue ?? item.value;
  if (value === null) return item.state;
  if (typeof value === "boolean") return value ? "ENABLED" : "DISABLED";
  return String(value);
}

function ProviderConfiguration({ settings, provider }: { settings: ReadResult<RuntimeSettingsRecord>; provider: string }) {
  const items = runtimeItems(settings, provider);
  return (
    <div className="provider-card__configuration">
      <span className="card-label">CONFIGURATION</span>
      {items.length === 0 ? <small>UNKNOWN / OPEN SETTINGS</small> : items.map((item) => (
        <small key={item.key}>{item.key}={configValue(item)} · {item.mode ?? "UNKNOWN"}</small>
      ))}
    </div>
  );
}

function ProviderRow({ record, settings }: { record: ProviderHealthRecord; settings: ReadResult<RuntimeSettingsRecord> }) {
  return (
    <article className={`provider-card provider-card--${stateClass(record.state)}`}>
      <div className="provider-card__identity">
        <strong>{record.provider}</strong>
        <span>{record.capability}</span>
        <small>CHECKED {readableDate(record.checkedAt)}</small>
      </div>
      <div className="provider-card__state">
        <span className="card-label">CURRENT STATE</span>
        <strong>{record.state}</strong>
        <small>{record.consecutiveFailures} consecutive failure{record.consecutiveFailures === 1 ? "" : "s"}</small>
      </div>
      <ProviderConfiguration provider={record.provider} settings={settings} />
      <div className="provider-card__metrics">
        <span className="card-label">LATENCY</span>
        <strong>{record.latencyMs === null ? "UNKNOWN" : `${record.latencyMs.toFixed(0)} ms`}</strong>
        <span className="quota-copy">{quotaSummary(record.quota)}</span>
      </div>
      <div className="provider-card__quality">
        {record.freshnessState === null ? (
          <SafetyBadge label="FRESHNESS" value="UNKNOWN" tone="disabled" />
        ) : <FreshnessBadge value={record.freshnessState} />}
        <small>{record.errorClass ? `ERROR ${record.errorClass}` : "NO ERROR CLASS"}</small>
      </div>
      <ProviderActions provider={record.provider} />
    </article>
  );
}

function ProvidersContent({
  result,
  settings
}: {
  result: ReadResult<ReadPage<ProviderHealthRecord>>;
  settings: ReadResult<RuntimeSettingsRecord>;
}) {
  if (!result.ok) {
    return (
      <div className="read-state read-state--error" role="status">
        <span className="eyebrow">PROVIDER OBSERVABILITY / READ-ONLY</span>
        <strong>{failureMessage(result)}</strong>
        <p>No provider health was inferred from the failed read.</p>
        <Link href="/providers">RETRY</Link>
      </div>
    );
  }
  if (result.data.items.length === 0) {
    return (
      <div className="read-state" role="status">
        <span className="eyebrow">PROVIDER OBSERVABILITY</span>
        <strong>NO PROVIDER HEALTH EVIDENCE</strong>
        <p>The catalog is empty or not persisted. Empty is not healthy.</p>
      </div>
    );
  }
  return (
    <div className="provider-list" aria-label="Provider health records">
      {result.data.items.map((record) => (
        <ProviderRow key={`${record.provider}:${record.capability}`} record={record} settings={settings} />
      ))}
    </div>
  );
}

export function ProvidersDashboard({
  result,
  settings
}: {
  result: ReadResult<ReadPage<ProviderHealthRecord>>;
  settings?: ReadResult<RuntimeSettingsRecord>;
}) {
  const runtimeSettings = settings ?? { ok: false as const, reason: "NOT_CONFIGURED" as const };
  return (
    <>
      <section className="section-block intelligence-section" aria-labelledby="providers-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">TRANSPORT / QUOTA / FRESHNESS</p>
            <h3 id="providers-title">Provider health</h3>
          </div>
          <p className="section-note">Health is evidence quality, never a positive trade signal.</p>
        </div>
        <ProvidersContent result={result} settings={runtimeSettings} />
      </section>
      <section className="boundary-strip" aria-labelledby="provider-boundary-title">
        <div>
          <p className="eyebrow">FAIL-CLOSED OBSERVABILITY</p>
          <h3 id="provider-boundary-title">Degradation remains visible</h3>
          <p>Unknown, stale, down or conflicted providers reduce confidence; they never become safe.</p>
        </div>
        <SafetyBadge label="DATA" value="ADVISORY" tone="advisory" />
      </section>
    </>
  );
}
