"use client";

import Link from "next/link";
import { useState } from "react";

import type { CandidateRecord, EarlyRadarRecord } from "../lib/read-api";
import {
  Pill,
  formatAgeFrom,
  formatAgeSeconds,
  formatConfidence,
  formatScore,
  formatUsd,
  freshnessTone,
  riskTone,
  shortIdentity
} from "./format";

export interface RadarRow {
  candidate: CandidateRecord;
  early: EarlyRadarRecord | null;
}

type SortKey = "token" | "age" | "state" | "score" | "confidence" | "risk" | "liquidity";
type SortDirection = "asc" | "desc";

const COLUMNS: Array<{ key: SortKey; label: string; numeric?: boolean }> = [
  { key: "token", label: "Token" },
  { key: "age", label: "Age", numeric: true },
  { key: "state", label: "State" },
  { key: "score", label: "Score", numeric: true },
  { key: "confidence", label: "Conf", numeric: true },
  { key: "risk", label: "Risk" },
  { key: "liquidity", label: "Liquidity", numeric: true }
];

const RISK_ORDER: Record<string, number> = { PASS: 0, WARN: 1, BLOCK: 2, UNKNOWN: 3 };

function ageSeconds(row: RadarRow): number | null {
  if (row.early?.launchAgeSeconds !== null && row.early?.launchAgeSeconds !== undefined) {
    return row.early.launchAgeSeconds;
  }
  const at = Date.parse(row.candidate.discoveredAt);
  return Number.isFinite(at) ? Math.max(0, (Date.now() - at) / 1000) : null;
}

function scoreOf(row: RadarRow): number | null {
  return row.candidate.score ?? row.early?.earlyScore ?? null;
}

function confidenceOf(row: RadarRow): number | null {
  return row.candidate.scoreConfidence ?? row.early?.earlyScoreConfidence ?? null;
}

function compareRows(key: SortKey, a: RadarRow, b: RadarRow): number {
  switch (key) {
    case "token":
      return (a.candidate.symbol ?? a.candidate.name ?? "").localeCompare(
        b.candidate.symbol ?? b.candidate.name ?? ""
      );
    case "state":
      return a.candidate.state.localeCompare(b.candidate.state);
    case "risk":
      return (RISK_ORDER[a.candidate.riskDisposition] ?? 4) - (RISK_ORDER[b.candidate.riskDisposition] ?? 4);
    case "age":
      return (ageSeconds(a) ?? Number.POSITIVE_INFINITY) - (ageSeconds(b) ?? Number.POSITIVE_INFINITY);
    case "score":
      return (scoreOf(a) ?? -1) - (scoreOf(b) ?? -1);
    case "confidence":
      return (confidenceOf(a) ?? -1) - (confidenceOf(b) ?? -1);
    case "liquidity":
      return (a.early?.liquidityUsd ?? -1) - (b.early?.liquidityUsd ?? -1);
  }
}

function Row({ row, now }: { row: RadarRow; now: number }) {
  const { candidate, early } = row;
  const displayName = candidate.symbol || candidate.name || "UNNAMED";
  const score = scoreOf(row);
  const confidence = confidenceOf(row);
  const age = ageSeconds(row);
  const reasons = candidate.riskReasonCodes.slice(0, 2);
  return (
    <tr>
      <td>
        <div className="dt-token">
          <Link href={`/tokens/${candidate.tokenId}`}>{displayName}</Link>
          <code title={candidate.mintAddress}>{shortIdentity(candidate.mintAddress)}</code>
        </div>
      </td>
      <td className="num" suppressHydrationWarning>
        {early?.launchAgeSeconds !== null && early?.launchAgeSeconds !== undefined
          ? formatAgeSeconds(early.launchAgeSeconds)
          : formatAgeFrom(candidate.discoveredAt, now)}
      </td>
      <td><Pill label={candidate.state} tone="info" /></td>
      <td className="num">{score === null ? "UNKNOWN" : `${formatScore(score)}`}</td>
      <td className="num">{formatConfidence(confidence)}</td>
      <td><Pill label={candidate.riskDisposition} tone={riskTone(candidate.riskDisposition)} /></td>
      <td><Pill label={candidate.riskQualityState} tone={freshnessTone(candidate.riskQualityState)} /></td>
      <td className="num">{early ? formatUsd(early.liquidityUsd) : "UNKNOWN"}</td>
      <td className="dt-reasons" title={candidate.riskReasonCodes.join(", ")}>
        {reasons.length > 0 ? reasons.join(", ") : "—"}
      </td>
    </tr>
  );
}

export function RadarTable({ rows, ariaLabel = "Ranked candidates" }: { rows: RadarRow[]; ariaLabel?: string }) {
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection } | null>(null);
  const [now] = useState(() => Date.now());

  const ordered = sort === null
    ? rows
    : [...rows].sort((a, b) => {
        const base = compareRows(sort.key, a, b);
        return sort.direction === "asc" ? base : -base;
      });

  return (
    <div className="dt-wrap">
      <table aria-label={ariaLabel} className="dt">
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                aria-sort={
                  sort?.key === column.key
                    ? sort.direction === "asc" ? "ascending" : "descending"
                    : undefined
                }
                className={column.numeric ? "num" : undefined}
                key={column.key}
                scope="col"
              >
                <button
                  aria-label={`Sort by ${column.label}`}
                  onClick={() =>
                    setSort((current) =>
                      current?.key === column.key
                        ? current.direction === "asc"
                          ? { key: column.key, direction: "desc" }
                          : null
                        : { key: column.key, direction: column.numeric ? "desc" : "asc" }
                    )
                  }
                  type="button"
                >
                  {column.label}
                </button>
              </th>
            ))}
            <th scope="col">Freshness</th>
            <th scope="col">Risk reasons</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((row) => <Row key={row.candidate.id} now={now} row={row} />)}
        </tbody>
      </table>
    </div>
  );
}
