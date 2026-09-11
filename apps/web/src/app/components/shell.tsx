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

function chainState(
  providers: OperationsRecord["providers"],
  chain: string
): OperationalState {
  const matches = providers.filter((provider) => provider.chains?.includes(chain) === true);
  if (matches.length === 0) return "UNKNOWN";
  if (matches.some((provider) => provider.state === "DOWN")) return "DOWN";
  if (matches.some((provider) => provider.state === "DEGRADED")) return "DEGRADED";
  if (matches.some((provider) => provider.state === "UNKNOWN")) return "UNKNOWN";
  return matches.every((provider) => provider.state === "HEALTHY") ? "HEALTHY" : "UNKNOWN";
}

type OperationalState = OperationsRecord["overallState"];

function ChainStatus({
  label,
  providers,
  chain
}: {
  label: string;
  providers: OperationsRecord["providers"];
  chain: string;
}) {
  const state = chainState(providers, chain);
  return <StatusChip label={label} value={state} tone={toneForState(state)} />;
}

function TopBarStatus({ operations }: { operations: ReadResult<OperationsRecord> }) {
  if (!operations.ok) {
    return (
      <div className="ws-topbar__status" aria-label="System status">
        <StatusChip label="STACK" value="UNKNOWN" tone="unknown" />
        <StatusChip label="PROVIDERS" value="UNKNOWN" tone="unknown" />
        <ChainStatus label="SOLANA" providers={[]} chain="solana" />
        <ChainStatus label="BNB" providers={[]} chain="bnb" />
        <ChainStatus label="ROBINHOOD" providers={[]} chain="robinhood" />
      </div>
    );
  }
  const overview = operations.data;
  const providers = overview.providers;
  const down = providers.filter((provider) => provider.state === "DOWN").length;
  const degraded = providers.filter((provider) => provider.state === "DEGRADED").length;
  const unknown = providers.filter((provider) => provider.state === "UNKNOWN").length;
  const providerSummary = providers.length === 0
    ? "UNKNOWN"
    : down > 0
      ? `${down} DOWN`
      : degraded > 0
        ? `${degraded} DEGRADED`
        : unknown > 0
          ? `${unknown} UNKNOWN`
          : "READY";
  const providerTone: ChipTone = providers.length === 0
    ? "unknown"
    : down > 0
      ? "danger"
      : degraded > 0
        ? "warn"
        : unknown > 0
          ? "unknown"
        : "ok";
  return (
    <div className="ws-topbar__status" aria-label="System status">
      <StatusChip label="STACK" value={overview.overallState} tone={toneForState(overview.overallState)} />
      <StatusChip label="PROVIDERS" value={providerSummary} tone={providerTone} />
      <ChainStatus label="SOLANA" providers={providers} chain="solana" />
      <ChainStatus label="BNB" providers={providers} chain="bnb" />
      <ChainStatus label="ROBINHOOD" providers={providers} chain="robinhood" />
    </div>
  );
}

function ProtectedModeStatus({ operations }: { operations: ReadResult<OperationsRecord> }) {
  if (!operations.ok) {
    return (
      <div className="ws-topbar__actions" aria-label="Protected operating modes">
        <StatusChip label="ANALYSIS ONLY" value="UNKNOWN" tone="unknown" />
        <StatusChip label="PAPER TRADING" value="UNKNOWN" tone="unknown" />
        <StatusChip label="EXECUTION" value="UNKNOWN" tone="unknown" />
        <RealtimeStatus />
        <ThemeToggle />
      </div>
    );
  }
  const modes = operations.data.modes;
  return (
    <div className="ws-topbar__actions" aria-label="Protected operating modes">
      <StatusChip label="ANALYSIS ONLY" value={modes.analysisOnly ? "ON" : "INVALID"} tone={modes.analysisOnly ? "ok" : "danger"} />
      <StatusChip label="PAPER TRADING" value={modes.paperTrading ? "ON" : "INVALID"} tone={modes.paperTrading ? "warn" : "danger"} />
      <StatusChip label="EXECUTION" value={!modes.manualExecution && !modes.autoExecution ? "LOCKED" : "INVALID"} tone={!modes.manualExecution && !modes.autoExecution ? "disabled" : "danger"} />
      <RealtimeStatus />
      <ThemeToggle />
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
          <span className="ws-brand__tag">MULTICHAIN INTELLIGENCE</span>
        </div>
        <TopBarStatus operations={operations} />
        <div className="ws-topbar__search">
          <SearchForm />
        </div>
        <ProtectedModeStatus operations={operations} />
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
