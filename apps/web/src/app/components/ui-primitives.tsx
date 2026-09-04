"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RealtimeStatus } from "./realtime-status";
import { ThemeToggle } from "./theme-toggle";

/* -------------------------------------------------------------------------- */
/*  TYPES & UTILS                                                              */
/* -------------------------------------------------------------------------- */

export type StatusVariant = "safe" | "paper" | "warning" | "danger" | "muted" | "info";

/* -------------------------------------------------------------------------- */
/*  STATUS PILL & BADGES                                                       */
/* -------------------------------------------------------------------------- */

export interface StatusPillProps {
  label: string;
  value: string;
  variant?: StatusVariant;
  subtext?: string;
  className?: string;
}

export function StatusPill({
  label,
  value,
  variant = "info",
  subtext,
  className = "",
}: StatusPillProps) {
  const variantStyles: Record<StatusVariant, string> = {
    safe: "border-emerald-500/30 text-emerald-400 bg-emerald-950/20",
    paper: "border-amber-500/30 text-amber-400 bg-amber-950/20",
    warning: "border-yellow-500/30 text-yellow-400 bg-yellow-950/20",
    danger: "border-rose-500/30 text-rose-400 bg-rose-950/20",
    muted: "border-gray-500/30 text-gray-400 bg-gray-950/20",
    info: "border-cyan-500/30 text-cyan-400 bg-cyan-950/20",
  };

  return (
    <div
      className={`inline-flex flex-col gap-0.5 rounded-lg border px-2.5 py-1 text-xs font-mono transition-colors ${variantStyles[variant]} ${className}`}
    >
      <span className="text-[10px] uppercase tracking-wider text-gray-400 font-sans">{label}</span>
      <strong className="font-semibold">{value}</strong>
      {subtext && <span className="text-[9px] text-gray-400 font-sans">{subtext}</span>}
    </div>
  );
}

export function RiskChip({ disposition }: { disposition?: string | null }) {
  const disp = (disposition || "UNKNOWN").toUpperCase();
  let variant: StatusVariant = "muted";
  if (disp === "PASS") variant = "safe";
  else if (disp === "WARN") variant = "warning";
  else if (disp === "BLOCK") variant = "danger";
  else if (disp === "UNKNOWN") variant = "muted";

  return <StatusPill label="Risk" value={disp} variant={variant} />;
}

export function FreshnessIndicator({ quality }: { quality?: string | null }) {
  const q = (quality || "UNKNOWN").toUpperCase();
  let variant: StatusVariant = "muted";
  if (q === "FRESH") variant = "safe";
  else if (q === "STALE") variant = "warning";
  else if (q === "INVALID" || q === "CONFLICTED") variant = "danger";

  return (
    <span
      aria-label={`Freshness: ${q}`}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono border ${
        variant === "safe"
          ? "border-emerald-500/40 text-emerald-400 bg-emerald-950/30"
          : variant === "warning"
          ? "border-amber-500/40 text-amber-400 bg-amber-950/30"
          : "border-rose-500/40 text-rose-400 bg-rose-950/30"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          variant === "safe" ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-amber-400"
        }`}
      />
      {q}
    </span>
  );
}

export function ScoreGauge({
  score,
  label = "Score",
  confidence,
}: {
  score: number | null;
  label?: string;
  confidence?: number | null;
}) {
  if (score === null || score === undefined) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] uppercase tracking-wider text-gray-400">{label}</span>
        <span className="text-xs font-mono text-amber-400/90 font-bold">UNKNOWN</span>
      </div>
    );
  }

  const rounded = Math.round(score);
  let color = "text-emerald-400";
  if (rounded < 40) color = "text-rose-400";
  else if (rounded < 70) color = "text-amber-400";

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-400">{label}</span>
        {confidence !== undefined && confidence !== null && (
          <span className="text-[9px] font-mono text-gray-400">
            {(confidence * 100).toFixed(0)}% conf
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold font-mono ${color}`}>{rounded}/100</span>
        <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full transition-all ${
              rounded >= 70
                ? "bg-emerald-400"
                : rounded >= 40
                ? "bg-amber-400"
                : "bg-rose-400"
            }`}
            style={{ width: `${Math.min(100, Math.max(0, rounded))}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  METRIC CARD & CARDS                                                        */
/* -------------------------------------------------------------------------- */

export interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: React.ReactNode;
  trend?: string;
  variant?: StatusVariant;
  className?: string;
}

export function MetricCard({
  label,
  value,
  subtext,
  variant = "info",
  className = "",
}: MetricCardProps) {
  const borderColors: Record<StatusVariant, string> = {
    safe: "border-l-2 border-l-emerald-500",
    paper: "border-l-2 border-l-amber-500",
    warning: "border-l-2 border-l-yellow-500",
    danger: "border-l-2 border-l-rose-500",
    muted: "border-l-2 border-l-gray-600",
    info: "border-l-2 border-l-cyan-500",
  };

  return (
    <div
      className={`rounded-xl border border-gray-800 bg-gray-900/60 p-3.5 shadow-lg backdrop-blur-sm ${borderColors[variant]} ${className}`}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-gray-400">
        {label}
      </span>
      <div className="mt-1 text-xl font-bold font-mono text-gray-100">{value}</div>
      {subtext && <div className="mt-1 text-xs text-gray-400">{subtext}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  SECTION HEADER                                                             */
/* -------------------------------------------------------------------------- */

export function SectionHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-2 border-b border-gray-800">
      <div>
        <h2 className="text-lg font-bold tracking-tight text-gray-100 m-0">{title}</h2>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5 m-0">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  DATA TABLE COMPONENTS                                                      */
/* -------------------------------------------------------------------------- */

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  emptyText = "No data available",
  onRowClick,
}: {
  columns: {
    key: string;
    header: string;
    render: (item: T) => React.ReactNode;
    className?: string;
  }[];
  data: T[];
  keyExtractor: (item: T) => string;
  emptyText?: string;
  onRowClick?: (item: T) => void;
}) {
  if (!data || data.length === 0) {
    return <EmptyState title="No Records" description={emptyText} />;
  }

  return (
    <div className="w-full overflow-x-auto rounded-xl border border-gray-800 bg-gray-900/40">
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-gray-950/80 text-[10px] uppercase tracking-wider text-gray-400 border-b border-gray-800">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={`p-3 font-semibold ${col.className || ""}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/60 font-sans">
          {data.map((item) => (
            <tr
              key={keyExtractor(item)}
              onClick={() => onRowClick && onRowClick(item)}
              className={`transition-colors hover:bg-gray-800/40 ${
                onRowClick ? "cursor-pointer" : ""
              }`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`p-3 align-middle ${col.className || ""}`}>
                  {col.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  EMPTY / ERROR / SKELETON STATES                                           */
/* -------------------------------------------------------------------------- */

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-gray-800 bg-gray-950/30">
      <div className="w-10 h-10 rounded-full bg-gray-800/80 flex items-center justify-center text-gray-400 mb-3 text-lg">
        ø
      </div>
      <h3 className="text-sm font-semibold text-gray-300 m-0">{title}</h3>
      <p className="text-xs text-gray-500 mt-1 max-w-sm m-0">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  reason,
  onRetry,
}: {
  reason: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center rounded-xl border border-rose-900/50 bg-rose-950/20 text-rose-300">
      <span className="text-lg font-bold">⚠️ Data Unavailable</span>
      <p className="text-xs text-rose-400/90 mt-1 mb-3">{reason}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1.5 rounded-md bg-rose-900/60 hover:bg-rose-800 text-xs font-medium text-rose-100 transition-colors"
        >
          Retry Request
        </button>
      )}
    </div>
  );
}

export function Skeleton({ className = "h-8 w-full" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-800/60 ${className}`}
      aria-label="Loading..."
    />
  );
}

/* -------------------------------------------------------------------------- */
/*  TABS & TOOLTIPS                                                            */
/* -------------------------------------------------------------------------- */

export function Tabs({
  tabs,
  activeTab,
  onChange,
}: {
  tabs: { id: string; label: string; badge?: number | string }[];
  activeTab: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-1 border-b border-gray-800 pb-px overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 ${
              isActive
                ? "border-emerald-400 text-emerald-400 bg-gray-900/80"
                : "border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40"
            }`}
          >
            {tab.label}
            {tab.badge !== undefined && (
              <span
                className={`px-1.5 py-0.5 text-[10px] rounded-full font-mono ${
                  isActive
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-500/30"
                    : "bg-gray-800 text-gray-400"
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function Tooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs z-50 rounded bg-gray-900 border border-gray-700 p-2 text-[11px] text-gray-200 shadow-xl pointer-events-none">
          {text}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  DRAWER / INSPECTOR                                                         */
/* -------------------------------------------------------------------------- */

export function Drawer({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md h-full bg-gray-950 border-l border-gray-800 shadow-2xl flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h3 className="text-base font-bold text-gray-100 m-0">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 rounded text-gray-400 hover:text-gray-100 hover:bg-gray-800 text-sm"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  GLOBAL TOP BAR & SEARCH NAVIGATION                                         */
/* -------------------------------------------------------------------------- */

function useSafeRouter() {
  try {
    return useRouter();
  } catch {
    return null;
  }
}

export function WorkstationTopBar() {
  const [searchQuery, setSearchQuery] = useState("");
  const router = useSafeRouter();

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    // Direct routing based on search string pattern
    if (query.length >= 32) {
      // Address / Mint search
      if (router) {
        router.push(`/tokens/${encodeURIComponent(query)}`);
      } else {
        window.location.href = `/tokens/${encodeURIComponent(query)}`;
      }
    } else {
      if (router) {
        router.push(`/?search=${encodeURIComponent(query)}`);
      } else {
        window.location.href = `/?search=${encodeURIComponent(query)}`;
      }
    }
  };

  return (
    <header className="w-full bg-gray-950/90 border-b border-gray-800/80 sticky top-0 z-40 backdrop-blur-md px-4 py-2.5">
      <div className="max-w-[1550px] mx-auto flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Nav */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 no-underline">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
            <span className="font-bold text-base tracking-wider text-gray-100">
              Meme<span className="text-emerald-400">Radar</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
              v1.0-alpha
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-1 text-xs font-semibold text-gray-400">
            <Link href="/" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Radar
            </Link>
            <Link href="/ultra-early" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Ultra Early
            </Link>
            <Link href="/positions" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Positions
            </Link>
            <Link href="/wallet-graph" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Wallet Graph
            </Link>
            <Link href="/operations" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Providers & Shadow
            </Link>
            <Link href="/research" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Research
            </Link>
            <Link href="/audit" className="px-2.5 py-1.5 rounded hover:text-emerald-400 hover:bg-gray-900 transition-colors">
              Audit
            </Link>
          </nav>
        </div>

        {/* Global Search & Safety Badges */}
        <div className="flex items-center gap-3">
          <form onSubmit={handleSearchSubmit} className="relative">
            <input
              type="text"
              placeholder="Search mint / wallet / symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 sm:w-64 bg-gray-900 border border-gray-700/80 rounded-lg px-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-400 font-mono"
            />
            <button type="submit" className="absolute right-2 top-1.2 text-xs text-gray-400 hover:text-gray-200">
              🔍
            </button>
          </form>

          <span className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border border-emerald-500/30 text-emerald-400 bg-emerald-950/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            READ ONLY MODE
          </span>

          <RealtimeStatus />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------------- */
/*  PAGE SHELL                                                                 */
/* -------------------------------------------------------------------------- */

export function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans flex flex-col">
      <WorkstationTopBar />
      <main className="flex-1 max-w-[1550px] w-full mx-auto p-4 sm:p-6 space-y-6">
        {children}
      </main>
      <footer className="w-full border-t border-gray-900 bg-gray-950 py-4 px-6 text-center text-xs text-gray-500">
        MemeRadar Early-Alpha Workstation &bull; Mode: ANALYSIS_ONLY=true, PAPER_TRADING=true, MANUAL_EXECUTION=false, AUTO_EXECUTION=false &bull; Phase 12 Locked
      </footer>
    </div>
  );
}
