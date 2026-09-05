import type { CandidateQuality, RiskDisposition } from "../lib/read-api";

export function shortIdentity(value: string, visible = 6): string {
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}…${value.slice(-visible)}`;
}

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "UNKNOWN";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  if (abs >= 1) return `$${value.toFixed(2)}`;
  return `$${value.toPrecision(2)}`;
}

export function formatAgeSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return "UNKNOWN";
  }
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3_600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3_600)}h`;
  return `${Math.floor(seconds / 86_400)}d`;
}

export function formatAgeFrom(isoTimestamp: string, now: number): string {
  const at = Date.parse(isoTimestamp);
  if (!Number.isFinite(at)) return "UNKNOWN";
  return formatAgeSeconds(Math.max(0, (now - at) / 1000));
}

export function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toISOString() : "UNKNOWN TIME";
}

export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "UNKNOWN";
  return `${Math.round(value * 100)}%`;
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "UNKNOWN";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function formatCompactMap(value: Record<string, unknown>, limit = 2): string {
  const entries = Object.entries(value).slice(0, limit);
  if (entries.length === 0) return "UNKNOWN";
  return entries.map(([key, item]) => `${key}=${String(item)}`).join(" ");
}

export function riskTone(value: RiskDisposition): string {
  return value.toLowerCase();
}

export function freshnessTone(value: CandidateQuality): string {
  return value.toLowerCase();
}

/** Maps a backend evidence level string into a semantic pill tone. */
export function evidenceTone(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (["low", "pass", "clear", "healthy", "fresh", "sellable", "none"].includes(normalized)) return "low";
  if (["medium", "moderate", "warn", "stale", "degraded", "conflicted"].includes(normalized)) return "medium";
  if (["high", "critical", "block", "blocked", "down", "unsellable", "severe"].includes(normalized)) return "high";
  return "unknown";
}

export function Pill({ label, tone, title }: { label: string; tone: string; title?: string }) {
  return (
    <span className={`pill pill--${tone}`} title={title ?? label}>
      {label}
    </span>
  );
}

export function Unknown() {
  return <span className="dt-unknown">UNKNOWN</span>;
}
