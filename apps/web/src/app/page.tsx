import { RealtimeStatus } from "./components/realtime-status";
import {
  FreshnessBadge,
  RiskBadge,
  SafetyBadge,
  ScoreBadge
} from "./components/status-badges";
import { ThemeToggle } from "./components/theme-toggle";

const operatingModes = [
  {
    label: "ANALYSIS ONLY",
    value: "Enabled",
    detail: "Evidence collection remains on.",
    tone: "safe"
  },
  {
    label: "PAPER TRADING",
    value: "Enabled",
    detail: "Simulated outcomes only.",
    tone: "paper"
  },
  {
    label: "MANUAL EXECUTION",
    value: "Disabled",
    detail: "Operator approval path is locked.",
    tone: "disabled"
  },
  {
    label: "AUTO EXECUTION",
    value: "Disabled",
    detail: "No autonomous orders are possible.",
    tone: "disabled"
  }
] as const;

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <p className="eyebrow">SOLANA INTELLIGENCE / OPERATOR CONSOLE</p>
          <h1>MemeRadar</h1>
        </div>
        <div className="topbar__actions">
          <span className="environment-badge">LOCAL ANALYSIS</span>
          <RealtimeStatus />
          <ThemeToggle />
        </div>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__copy">
          <p className="eyebrow">EVIDENCE BEFORE EXECUTION</p>
          <h2 id="hero-title">A calmer view of a noisy market.</h2>
          <p className="lede">
            MemeRadar correlates normalized observations, risk evidence and explainable scoring.
            The operator surface stays useful even when providers are unavailable.
          </p>
          <div className="badge-row" aria-label="Data boundaries">
            <SafetyBadge label="LIVE DATA" value="UNAVAILABLE" tone="disabled" />
            <SafetyBadge label="ADVISORY OUTPUT" value="ONLY" tone="advisory" />
          </div>
        </div>
        <div className="status-orb" aria-label="Analysis system status: protected">
          <span aria-hidden="true" />
          <strong>PROTECTED</strong>
          <small>NO LIVE ORDERS</small>
        </div>
      </section>

      <section className="section-block" aria-labelledby="modes-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">OPERATING POLICY</p>
            <h3 id="modes-title">Protected modes</h3>
          </div>
          <p className="section-note">These values are enforced by the API configuration.</p>
        </div>
        <div className="mode-grid">
          {operatingModes.map((mode) => (
            <article className={`mode-card mode-card--${mode.tone}`} key={mode.label}>
              <span className="card-label">{mode.label}</span>
              <strong className={`mode-value mode-value--${mode.tone}`}>{mode.value}</strong>
              <small>{mode.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block" aria-labelledby="signal-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SIGNAL QUALITY</p>
            <h3 id="signal-title">No evidence loaded</h3>
          </div>
          <p className="section-note">Unavailable is a state, not a score.</p>
        </div>
        <div className="signal-grid">
          <article className="signal-card">
            <ScoreBadge value={null} />
            <p>AlphaScore appears only after a bounded feature snapshot is available.</p>
          </article>
          <article className="signal-card">
            <RiskBadge value="UNKNOWN" />
            <p>Critical risk evidence is never assumed safe when missing.</p>
          </article>
          <article className="signal-card">
            <FreshnessBadge value="UNKNOWN" />
            <p>Observed time and freshness will remain visible with each record.</p>
          </article>
        </div>
      </section>

      <section className="queue-card" aria-labelledby="queue-title">
        <div className="queue-card__icon" aria-hidden="true">◎</div>
        <div>
          <p className="eyebrow">RADAR QUEUE / READ-ONLY</p>
          <h3 id="queue-title">Waiting for normalized observations</h3>
          <p>Connect a read-only provider to begin building an evidence timeline.</p>
        </div>
        <span className="queue-card__state">NO LIVE DATA</span>
      </section>
    </main>
  );
}
