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
          <span className="card-label">PROVENANCE</span>
          <strong>{provenanceSummary(profile.provenance)}</strong>
          <small>AS OF {readableDate(profile.asOf)}</small>
        </div>
      </div>
      <small>{profile.noLookaheadVerified ? "NO-LOOKAHEAD VERIFIED" : "NO-LOOKAHEAD UNKNOWN"}</small>
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

export function CallersDashboard({
  profiles,
  calls,
  convergence
}: {
  profiles: ReadResult<ReadPage<CallerProfileRecord>>;
  calls: ReadResult<ReadPage<SocialCallRecord>>;
  convergence: ReadResult<ReadPage<CallerConvergenceRecord>>;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">X / TELEGRAM / MULTICHAIN RESEARCH</p>
          <h2>Caller intelligence</h2>
        </div>
        <small>Historical caller and convergence evidence is advisory and no-lookahead scoped.</small>
      </div>
      <section className="section-block intelligence-section" aria-labelledby="caller-profiles-title">
        <div className="section-heading">
          <div><p className="eyebrow">MEASUREMENT-ONLY HISTORY</p><h3 id="caller-profiles-title">Caller profiles</h3></div>
          <p className="section-note">Unknown outcomes remain unknown.</p>
        </div>
        <ProfileSection result={profiles} />
      </section>
      <section className="section-block intelligence-section" aria-labelledby="social-calls-title">
        <div className="section-heading">
          <div><p className="eyebrow">NORMALIZED PUBLIC EVIDENCE</p><h3 id="social-calls-title">Social calls</h3></div>
          <p className="section-note">X and Telegram observations retain provenance.</p>
        </div>
        <CallsSection result={calls} />
      </section>
      <section className="section-block intelligence-section" aria-labelledby="caller-convergence-title">
        <div className="section-heading">
          <div><p className="eyebrow">SMART-MONEY / CALLER JOIN</p><h3 id="caller-convergence-title">Caller convergence</h3></div>
          <p className="section-note">Convergence is evidence, not a strategy promotion.</p>
        </div>
        <ConvergenceSection result={convergence} />
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
