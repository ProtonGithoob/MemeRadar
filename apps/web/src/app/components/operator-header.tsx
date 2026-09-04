import Link from "next/link";

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
      <nav className="operator-nav" aria-label="Operator sections">
        <Link href="/">Radar</Link>
        <Link href="/positions">Positions</Link>
        <Link href="/wallets">Wallets</Link>
        <Link href="/wallet-graph">Graph</Link>
        <Link href="/providers">Providers</Link>
        <Link href="/operations">Operations</Link>
        <Link href="/settings">Settings</Link>
        <Link href="/audit">Audit</Link>
      </nav>
    </header>
  );
}
