const modes = [
  ["ANALYSIS ONLY", "Enabled", "mode-safe"],
  ["PAPER TRADING", "Enabled", "mode-paper"],
  ["MANUAL EXECUTION", "Disabled", "mode-disabled"],
  ["AUTO EXECUTION", "Disabled", "mode-disabled"]
] as const;

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SOLANA INTELLIGENCE / OPERATOR CONSOLE</p>
          <h1>MemeRadar</h1>
        </div>
        <span className="environment-badge">LOCAL ANALYSIS</span>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <div>
          <p className="eyebrow">Evidence before execution</p>
          <h2 id="hero-title">Your radar is ready for signal.</h2>
          <p className="lede">
            Candidate discovery, risk evidence and explainable scoring will appear here as providers
            connect. No live-money execution is enabled.
          </p>
        </div>
        <div className="status-orb" aria-label="Analysis system status: ready">
          <span />
          <strong>READY</strong>
          <small>KEYLESS LOCAL MODE</small>
        </div>
      </section>

      <section className="mode-grid" aria-label="Operating modes">
        {modes.map(([label, value, className]) => (
          <article className="mode-card" key={label}>
            <span className="card-label">{label}</span>
            <strong className={className}>{value}</strong>
          </article>
        ))}
      </section>

      <section className="empty-state" aria-labelledby="empty-title">
        <div className="empty-icon" aria-hidden="true">◎</div>
        <div>
          <p className="eyebrow">RADAR QUEUE</p>
          <h3 id="empty-title">Waiting for normalized observations</h3>
          <p>Connect a read-only provider to begin building an evidence timeline.</p>
        </div>
      </section>
    </main>
  );
}
