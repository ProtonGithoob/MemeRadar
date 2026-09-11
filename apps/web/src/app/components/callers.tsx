"use client";

import { useMemo, useState } from "react";

import { SafetyBadge, FreshnessBadge } from "./status-badges";
import type {
  CallerConvergenceRecord,
  CallerProfileRecord,
  ReadPage,
  ReadResult,
  SocialCallRecord
} from "../lib/read-api";

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : "UNKNOWN TIME";
}

function percent(value: number | null): string {
  return value === null ? "UNKNOWN" : `${Math.round(value * 100)}%`;
}

function provenanceSummary(provenance: CallerProfileRecord["provenance"]): string {
  const first = provenance[0];
  return first ? `${first.provider} / ${first.sourceId}` : "PROVENANCE UNKNOWN";
}

function Failure({ label, result }: { label: string; result: ReadResult<unknown> }) {
  if (result.ok) return null;
  return (
    <div className="read-state read-state--error" role="status">
      <span className="eyebrow">{label} / READ-ONLY</span>
      <strong>CALLER INTELLIGENCE UNAVAILABLE</strong>
      <p>No caller evidence was substituted after the bounded read failed.</p>
    </div>
  );
}

function ProfileEvidence({ profile }: { profile: CallerProfileRecord }) {
  const multipleEntries = Object.entries(profile.executableWinRates).slice(0, 4);
  const specialization = Object.entries(profile.specialization)
    .flatMap(([family, values]) => Object.entries(values).map(([label, count]) => `${family}:${label} ${count}`))
    .slice(0, 4);
  return (
    <article className="detail-panel">
      <div className="section-heading">
        <div>
          <span className="card-label">{profile.platform.toUpperCase()} / CALLER PROFILE</span>
          <h4>{profile.callerId}</h4>
          <small>{profile.handle ?? profile.authorId}</small>
        </div>
        <FreshnessBadge value={profile.qualityState} />
      </div>
      <div className="operations-summary">
        <div>
          <span className="card-label">HISTORY</span>
          <strong>{profile.status}</strong>
          <small>{profile.knownOutcomeCount} known / {profile.sampleCount} samples</small>
        </div>
        <div>
          <span className="card-label">CONFIDENCE</span>
          <strong>{percent(profile.confidence)}</strong>
          <small>UNCERTAINTY {percent(profile.uncertainty)}</small>
        </div>
        <div>
          <span className="card-label">EVIDENCE CLASS</span>
          <strong>{profile.evidenceClass}</strong>
          <small>{profile.noLookaheadVerified ? "NO-LOOKAHEAD VERIFIED" : "NO-LOOKAHEAD UNKNOWN"}</small>
        </div>
        <div>
          <span className="card-label">PROVENANCE</span>
          <strong>{provenanceSummary(profile.provenance)}</strong>
          <small>AS OF {readableDate(profile.asOf)}</small>
        </div>
      </div>
      <div className="operations-summary">
        <div>
          <span className="card-label">EXECUTABLE MULTIPLES</span>
          {multipleEntries.length === 0 ? <strong>UNKNOWN</strong> : multipleEntries.map(([label, value]) => (
            <small key={label}>{label} {percent(value)}</small>
          ))}
        </div>
        <div>
          <span className="card-label">EXECUTABLE MFE / MAE</span>
          <strong>{profile.medianExecutableMfe ?? "UNKNOWN"} / {profile.medianExecutableMae ?? "UNKNOWN"}</strong>
          <small>RUGS {profile.rugCount} / FAILURES {profile.failureCount}</small>
        </div>
        <div>
          <span className="card-label">SPECIALIZATION</span>
          <strong>{specialization.length === 0 ? "UNKNOWN" : specialization.join(" · ")}</strong>
          <small>Measurement-only historical evidence</small>
        </div>
      </div>
    </article>
  );
}

function ProfileSection({ result }: { result: ReadResult<ReadPage<CallerProfileRecord>> }) {
  if (!result.ok) return <Failure label="CALLER PROFILES" result={result} />;
  if (result.data.items.length === 0) {
    return <div className="read-state" role="status"><strong>NO CALLER PROFILES AVAILABLE</strong></div>;
  }
  return <div className="wallet-list" aria-label="Caller performance profiles">
    {result.data.items.map((profile) => <ProfileEvidence key={profile.callerId} profile={profile} />)}
  </div>;
}

function CallEvidence({ call }: { call: SocialCallRecord }) {
  return (
    <article className="detail-panel">
      <div className="section-heading">
        <div>
          <span className="card-label">{call.source.toUpperCase()} / SOCIAL CALL</span>
          <h4>{call.callerId}</h4>
          <code>{call.assetId ?? "ASSET UNKNOWN"}</code>
        </div>
        <FreshnessBadge value={call.qualityState} />
      </div>
      <div className="operations-summary">
        <div>
          <span className="card-label">INTENT</span>
          <strong>{call.intent}</strong>
          <small>{percent(call.confidence)} confidence</small>
        </div>
        <div>
          <span className="card-label">PUBLISHED</span>
          <strong>{readableDate(call.publishedAt)}</strong>
          <small>MESSAGE {call.messageId}</small>
        </div>
        <div>
          <span className="card-label">PROVENANCE</span>
          <strong>{provenanceSummary(call.provenance)}</strong>
          <small>{call.evidenceRefs.length} evidence reference{call.evidenceRefs.length === 1 ? "" : "s"}</small>
        </div>
      </div>
    </article>
  );
}

function CallsSection({ result }: { result: ReadResult<ReadPage<SocialCallRecord>> }) {
  if (!result.ok) return <Failure label="SOCIAL CALLS" result={result} />;
  if (result.data.items.length === 0) {
    return <div className="read-state" role="status"><strong>NO SOCIAL CALLS AVAILABLE</strong></div>;
  }
  return <div className="wallet-list" aria-label="Social call evidence">
    {result.data.items.map((call) => <CallEvidence key={call.id} call={call} />)}
  </div>;
}

function ConvergenceEvidence({ convergence }: { convergence: CallerConvergenceRecord }) {
  return (
    <article className="detail-panel">
      <div className="section-heading">
        <div>
          <span className="card-label">{convergence.chain.toUpperCase()} / CONVERGENCE</span>
          <h4>{convergence.tokenId}</h4>
          <small>{convergence.state}</small>
        </div>
        <FreshnessBadge value={convergence.qualityState} />
      </div>
      <div className="operations-summary">
        <div>
          <span className="card-label">CALLERS</span>
          <strong>{convergence.independentCallerCount ?? "UNKNOWN"}</strong>
          <small>independent / {convergence.rawCallerCount ?? "UNKNOWN"} raw</small>
        </div>
        <div>
          <span className="card-label">RISK QUALITY</span>
          <strong>{convergence.riskQualityState}</strong>
          <small>{convergence.riskDisposition ?? "RISK UNKNOWN"}</small>
        </div>
        <div>
          <span className="card-label">KOL / SIDE-WALLET</span>
          <strong>{convergence.kolBundleState ?? "UNKNOWN"} / {convergence.kolBundleConfidenceTier ?? "UNKNOWN"}</strong>
          <small>{convergence.probableRelatedSideWalletCount ?? "UNKNOWN"} probable wallets · {convergence.kolBundleCount ?? "UNKNOWN"} bundles</small>
          <small>{convergence.kolBundleTemporalProximitySeconds ?? "UNKNOWN"}s temporal proximity</small>
          <small>POSITION {convergence.visibleCallerPosition ?? "UNKNOWN"} · CLUSTER ACCUMULATION {convergence.clusterAdjustedAccumulation ?? "UNKNOWN"}</small>
          <small>{percent(convergence.kolBundleConfidence ?? null)} confidence · {(convergence.kolBundleReasonCodes ?? []).join(" · ") || "REASONS UNKNOWN"}</small>
        </div>
        <div>
          <span className="card-label">PROVENANCE</span>
          <strong>{provenanceSummary(convergence.provenance)}</strong>
          <small>AS OF {readableDate(convergence.asOf)}</small>
        </div>
      </div>
      <small>{convergence.noLookaheadVerified ? "NO-LOOKAHEAD VERIFIED" : "NO-LOOKAHEAD UNKNOWN"}</small>
    </article>
  );
}

function ConvergenceSection({ result }: { result: ReadResult<ReadPage<CallerConvergenceRecord>> }) {
  if (!result.ok) return <Failure label="CALLER CONVERGENCE" result={result} />;
  if (result.data.items.length === 0) {
    return <div className="read-state" role="status"><strong>NO CALLER CONVERGENCE AVAILABLE</strong></div>;
  }
  return <div className="wallet-list" aria-label="Caller convergence evidence">
    {result.data.items.map((convergence) => (
      <ConvergenceEvidence key={convergence.id} convergence={convergence} />
    ))}
  </div>;
}

function withItems<T>(result: ReadResult<ReadPage<T>>, items: T[]): ReadResult<ReadPage<T>> {
  return result.ok ? { ...result, data: { ...result.data, items } } : result;
}

function numberForSort(value: number | null): number {
  return value ?? Number.NEGATIVE_INFINITY;
}

function CallerFilters({
  platform,
  setPlatform,
  chain,
  setChain,
  evidenceClass,
  setEvidenceClass,
  minSamples,
  setMinSamples,
  minConfidence,
  setMinConfidence,
  kolTier,
  setKolTier,
  sort,
  setSort,
  platformOptions,
  chainOptions,
  evidenceOptions,
  kolOptions
}: {
  platform: string;
  setPlatform: (value: string) => void;
  chain: string;
  setChain: (value: string) => void;
  evidenceClass: string;
  setEvidenceClass: (value: string) => void;
  minSamples: string;
  setMinSamples: (value: string) => void;
  minConfidence: string;
  setMinConfidence: (value: string) => void;
  kolTier: string;
  setKolTier: (value: string) => void;
  sort: string;
  setSort: (value: string) => void;
  platformOptions: string[];
  chainOptions: string[];
  evidenceOptions: string[];
  kolOptions: string[];
}) {
  return (
    <div className="caller-filters" aria-label="Caller filters and sort">
      <label>PLATFORM<select value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="">ALL</option>{platformOptions.map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}</select></label>
      <label>CHAIN<select value={chain} onChange={(event) => setChain(event.target.value)}><option value="">ALL</option>{chainOptions.map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}</select></label>
      <label>EVIDENCE<select value={evidenceClass} onChange={(event) => setEvidenceClass(event.target.value)}><option value="">ALL</option>{evidenceOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>MIN SAMPLES<input min="0" onChange={(event) => setMinSamples(event.target.value)} type="number" value={minSamples} /></label>
      <label>MIN CONFIDENCE<input max="1" min="0" onChange={(event) => setMinConfidence(event.target.value)} step="0.05" type="number" value={minConfidence} /></label>
      <label>KOL BUNDLE<select value={kolTier} onChange={(event) => setKolTier(event.target.value)}><option value="">ALL</option>{kolOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>SORT<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="confidence">CONFIDENCE</option><option value="samples">SAMPLE COUNT</option><option value="mfe">EXECUTABLE MFE</option><option value="early">EARLIEST-ENTRY QUALITY</option></select></label>
    </div>
  );
}

export function CallersDashboard({
  profiles,
  calls,
  convergence
}: {
  profiles: ReadResult<ReadPage<CallerProfileRecord>>;
  calls: ReadResult<ReadPage<SocialCallRecord>>;
  convergence: ReadResult<ReadPage<CallerConvergenceRecord>>;
}) {
  const [platform, setPlatform] = useState("");
  const [chain, setChain] = useState("");
  const [evidenceClass, setEvidenceClass] = useState("");
  const [minSamples, setMinSamples] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [kolTier, setKolTier] = useState("");
  const [sort, setSort] = useState("confidence");
  const platformOptions = useMemo(() => Array.from(new Set([
    ...(profiles.ok ? profiles.data.items.map((item) => item.platform) : []),
    ...(calls.ok ? calls.data.items.map((item) => item.source) : [])
  ])).sort(), [calls, profiles]);
  const chainOptions = useMemo(() => Array.from(new Set([
    ...(calls.ok ? calls.data.items.map((item) => item.chain) : []),
    ...(convergence.ok ? convergence.data.items.map((item) => item.chain) : [])
  ])).filter((value): value is string => value !== null).sort(), [calls, convergence]);
  const evidenceOptions = useMemo(() => Array.from(new Set(
    profiles.ok ? profiles.data.items.map((item) => item.evidenceClass) : []
  )).sort(), [profiles]);
  const kolOptions = useMemo(() => Array.from(new Set(
    convergence.ok ? convergence.data.items.map((item) => item.kolBundleConfidenceTier ?? "UNKNOWN") : []
  )).sort(), [convergence]);
  const filteredProfiles = useMemo(() => {
    if (!profiles.ok) return profiles;
    const sampleMinimum = minSamples === "" ? 0 : Number(minSamples);
    const confidenceMinimum = minConfidence === "" ? 0 : Number(minConfidence);
    const values = profiles.data.items.filter((profile) =>
      (!platform || profile.platform.toLowerCase() === platform) &&
      (!evidenceClass || profile.evidenceClass.toUpperCase() === evidenceClass) &&
      profile.sampleCount >= sampleMinimum && profile.confidence >= confidenceMinimum
    );
    values.sort((left, right) => {
      const l = sort === "samples" ? left.sampleCount : sort === "mfe" ? numberForSort(left.medianExecutableMfe) : sort === "early" ? numberForSort(left.earlyEntryQuality) : left.confidence;
      const r = sort === "samples" ? right.sampleCount : sort === "mfe" ? numberForSort(right.medianExecutableMfe) : sort === "early" ? numberForSort(right.earlyEntryQuality) : right.confidence;
      return r - l;
    });
    return withItems(profiles, values);
  }, [evidenceClass, minConfidence, minSamples, platform, profiles, sort]);
  const filteredCalls = useMemo(() => {
    if (!calls.ok) return calls;
    return withItems(calls, calls.data.items.filter((call) => !platform || call.source.toLowerCase() === platform).filter((call) => !chain || call.chain === chain));
  }, [calls, chain, platform]);
  const filteredConvergence = useMemo(() => {
    if (!convergence.ok) return convergence;
    return withItems(convergence, convergence.data.items.filter((item) =>
      (!chain || item.chain === chain) && (!kolTier || (item.kolBundleConfidenceTier ?? "UNKNOWN") === kolTier)
    ));
  }, [chain, convergence, kolTier]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">X / TELEGRAM / MULTICHAIN RESEARCH</p>
          <h2>Caller intelligence</h2>
        </div>
        <small>Historical caller and convergence evidence is advisory and no-lookahead scoped.</small>
      </div>
      <section className="section-block" aria-labelledby="caller-filters-title">
        <div className="section-heading"><div><p className="eyebrow">EXISTING EVIDENCE FIELDS</p><h3 id="caller-filters-title">Filter and sort</h3></div><p className="section-note">No unsupported statistics are calculated in the browser.</p></div>
        <CallerFilters
          chain={chain} evidenceClass={evidenceClass} kolTier={kolTier} minConfidence={minConfidence}
          minSamples={minSamples} platform={platform} setChain={setChain} setEvidenceClass={setEvidenceClass}
          setKolTier={setKolTier} setMinConfidence={setMinConfidence} setMinSamples={setMinSamples}
          setPlatform={setPlatform} setSort={setSort} sort={sort}
          platformOptions={platformOptions} chainOptions={chainOptions}
          evidenceOptions={evidenceOptions} kolOptions={kolOptions}
        />
        <p className="section-note">CURRENT PAGE FILTER · profiles: platform/evidence/samples/confidence · calls: platform/chain · convergence: chain/KOL bundle</p>
      </section>
      <section className="section-block intelligence-section" aria-labelledby="caller-profiles-title">
        <div className="section-heading">
          <div><p className="eyebrow">MEASUREMENT-ONLY HISTORY</p><h3 id="caller-profiles-title">Caller leaderboard</h3></div>
          <p className="section-note">Unknown outcomes remain unknown.</p>
        </div>
        <ProfileSection result={filteredProfiles} />
      </section>
      <section className="section-block intelligence-section" aria-labelledby="social-calls-title">
        <div className="section-heading">
          <div><p className="eyebrow">NORMALIZED PUBLIC EVIDENCE</p><h3 id="social-calls-title">Social calls</h3></div>
          <p className="section-note">X and Telegram observations retain provenance.</p>
        </div>
        <CallsSection result={filteredCalls} />
      </section>
      <section className="section-block intelligence-section" aria-labelledby="caller-convergence-title">
        <div className="section-heading">
          <div><p className="eyebrow">SMART-MONEY / CALLER JOIN</p><h3 id="caller-convergence-title">Caller convergence</h3></div>
          <p className="section-note">Convergence is evidence, not a strategy promotion.</p>
        </div>
        <ConvergenceSection result={filteredConvergence} />
      </section>
      <section className="boundary-strip" aria-labelledby="caller-boundary-title">
        <div>
          <p className="eyebrow">ADVISORY READ SURFACE</p>
          <h3 id="caller-boundary-title">Caller evidence never authorizes execution</h3>
          <p>Profiles, calls and convergence remain measurement-only until replay and promotion gates prove value.</p>
        </div>
        <SafetyBadge label="EXECUTION" value="LOCKED" tone="disabled" />
      </section>
    </>
  );
}
