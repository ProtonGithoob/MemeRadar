import { RealtimeStatus } from "./realtime-status";
import { ThemeToggle } from "./theme-toggle";

export function OperatorHeader() {
  return (
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
  );
}
