import Link from "next/link";

import type { OperationsRecord, ReadResult } from "../lib/read-api";
import { RealtimeStatus } from "./realtime-status";
import { SearchForm, SidebarNav } from "./shell-client";
import { ThemeToggle } from "./theme-toggle";

type ChipTone = "ok" | "warn" | "danger" | "info" | "disabled" | "unknown";

function StatusChip({ label, value, tone }: { label: string; value: string; tone: ChipTone }) {
  return (
    <span className={`chip chip--${tone}`} role="status" aria-label={`${label}: ${value}`}>
      {label} {value}
    </span>
  );
}

function toneForState(state: string): ChipTone {
  if (state === "HEALTHY") return "ok";
  if (state === "DEGRADED") return "warn";
  if (state === "DOWN") return "danger";
  return "unknown";
}

function TopBarStatus({ operations }: { operations: ReadResult<OperationsRecord> }) {
  if (!operations.ok) {
    return (
      <div className="ws-topbar__status" aria-label="System status">
        <StatusChip label="STACK" value="UNKNOWN" tone="unknown" />
        <StatusChip label="PROVIDERS" value="UNKNOWN" tone="unknown" />
      </div>
    );
  }
  const overview = operations.data;
  const providers = overview.providers;
  const down = providers.filter((provider) => provider.state === "DOWN").length;
  const degraded = providers.filter((provider) => provider.state === "DEGRADED").length;
  const providerSummary = providers.length === 0
    ? "UNKNOWN"
    : down > 0
      ? `${down} DOWN`
      : degraded > 0
        ? `${degraded} DEGRADED`
        : "READY";
  const providerTone: ChipTone = providers.length === 0
    ? "unknown"
    : down > 0
      ? "danger"
      : degraded > 0
        ? "warn"
        : "ok";
  return (
    <div className="ws-topbar__status" aria-label="System status">
      <StatusChip label="STACK" value={overview.overallState} tone={toneForState(overview.overallState)} />
      <StatusChip label="PROVIDERS" value={providerSummary} tone={providerTone} />
    </div>
  );
}

export function WorkstationShell({
  children,
  operations
}: Readonly<{
  children: React.ReactNode;
  operations: ReadResult<OperationsRecord>;
}>) {
  return (
    <div className="ws">
      <header className="ws-topbar">
        <div className="ws-brand">
          <Link className="ws-brand__name" href="/">MemeRadar</Link>
          <span className="ws-brand__tag">SOLANA INTELLIGENCE</span>
        </div>
        <TopBarStatus operations={operations} />
        <div className="ws-topbar__search">
          <SearchForm />
        </div>
        <div className="ws-topbar__actions" aria-label="Protected operating modes">
          <span className="chip chip--ok chip--mode">ANALYSIS ONLY</span>
          <span className="chip chip--warn chip--mode">PAPER TRADING</span>
          <span className="chip chip--disabled chip--mode">EXECUTION LOCKED</span>
          <RealtimeStatus />
          <ThemeToggle />
        </div>
      </header>
      <div className="ws-body">
        <SidebarNav />
        <main className="ws-main">
          <div className="ws-main__inner">{children}</div>
        </main>
      </div>
    </div>
  );
}
