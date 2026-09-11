import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CallersDashboard } from "./callers";
import type {
  CallerConvergenceRecord,
  CallerProfileRecord,
  ReadPage,
  ReadResult,
  SocialCallRecord
} from "../lib/read-api";

const profile = {
  callerId: "telegram:alpha",
  platform: "telegram",
  authorId: "alpha",
  asOf: "2026-09-07T08:00:00.000Z",
  expiresAt: "2026-09-07T08:15:00.000Z",
  status: "INSUFFICIENT_SAMPLES",
  evidenceClass: "SYNTHETIC_REDACTED",
  handle: "alpha",
  displayName: "Alpha Caller",
  sampleCount: 1,
  maturedSampleCount: 0,
  knownOutcomeCount: 0,
  evidenceCoverage: null,
  earlyEntryPercentile: null,
  earlyEntryQuality: null,
  medianCallTimeMarketCap: null,
  medianTokenAgeSeconds: null,
  executableWinRates: {},
  medianExecutableMfe: null,
  medianExecutableMae: null,
  rugCount: 0,
  failureCount: 0,
  rugAvoidanceRate: null,
  consistencyRate: null,
  recencyStability: null,
  specialization: {},
  smartWalletConfirmationRate: null,
  earlyCallCount: 0,
  lateCallCount: 0,
  earlyCallRate: null,
  lateCallRate: null,
  editedCallRate: null,
  deletedCallRate: null,
  paidPromotionRate: null,
  confidenceIntervals: {},
  confidence: 0,
  uncertainty: 1,
  qualityState: "UNKNOWN" as const,
  noLookaheadVerified: true,
  provenance: [{ provider: "fixture", sourceId: "profile:1", observedAt: "2026-09-07T08:00:00.000Z", parserVersion: "v1" }],
  evidenceRefs: ["profile:1"],
  reasonCodes: ["CALLER_HISTORY_UNKNOWN"],
  configHash: "sha256:profile",
  version: "caller-performance-v1"
} satisfies CallerProfileRecord;

const evaluatedProfile = {
  ...profile,
  callerId: "x:beta",
  platform: "x",
  authorId: "beta",
  status: "EVALUATED",
  evidenceClass: "HISTORICAL_REAL",
  sampleCount: 20,
  maturedSampleCount: 18,
  knownOutcomeCount: 18,
  evidenceCoverage: 0.9,
  executableWinRates: { "1h:2x": 0.75, "1h:5x": 0.4 },
  medianExecutableMfe: 1.5,
  medianExecutableMae: -0.2,
  rugCount: 1,
  failureCount: 3,
  specialization: { chain: { SOLANA: 12, BNB: 8 } },
  confidence: 0.7,
  uncertainty: 0.3
} satisfies CallerProfileRecord;

const call = {
  id: "telegram:call-1",
  source: "telegram",
  messageId: "call-1",
  callerId: "telegram:alpha",
  platform: "telegram",
  authorId: "alpha",
  publishedAt: "2026-09-07T08:00:00.000Z",
  observedAt: "2026-09-07T08:00:00.000Z",
  ingestedAt: "2026-09-07T08:00:00.000Z",
  chain: "bnb",
  assetAddress: "0x1111111111111111111111111111111111111111",
  assetId: "bnb:0x1111111111111111111111111111111111111111",
  referencedAddress: null,
  unresolvedReferences: [],
  intent: "BULLISH",
  declaredEntry: null,
  declaredTargets: [],
  disclosure: {},
  edited: null,
  deleted: null,
  handle: "alpha",
  displayName: "Alpha Caller",
  confidence: 0.8,
  qualityState: "FRESH" as const,
  provenance: [{ provider: "fixture", sourceId: "call:1", observedAt: "2026-09-07T08:00:00.000Z", parserVersion: "v1" }],
  evidenceRefs: ["call:1"]
} satisfies SocialCallRecord;

const convergence = {
  id: "bnb:0x1111111111111111111111111111111111111111:1",
  tokenId: "bnb:0x1111111111111111111111111111111111111111",
  chain: "bnb",
  assetAddress: "0x1111111111111111111111111111111111111111",
  asOf: "2026-09-07T08:00:00.000Z",
  expiresAt: "2026-09-07T08:05:00.000Z",
  state: "CALLER_ONLY",
  rawCallerCount: 1,
  independentCallerCount: 1,
  clusterAdjustedCallerCount: 1,
  highQualityCallerCount: null,
  callerIds: ["telegram:alpha"],
  independentCallerIds: ["telegram:alpha"],
  earliestCallAt: null,
  latestCallAt: null,
  temporalDispersionSeconds: null,
  smartWalletConfirmation: null,
  narrativeAlignment: null,
  contradictoryCallCount: 0,
  distributionDetected: null,
  riskDisposition: null,
  riskQualityState: "UNKNOWN" as const,
  riskBlocked: null,
  confidence: 0.5,
  qualityState: "UNKNOWN" as const,
  noLookaheadVerified: true,
  provenance: [{ provider: "fixture", sourceId: "convergence:1", observedAt: "2026-09-07T08:00:00.000Z", parserVersion: "v1" }],
  evidenceRefs: ["convergence:1"],
  reasonCodes: ["CALLER_CONVERGENCE_RISK_UNKNOWN"],
  configHash: "sha256:convergence",
  version: "caller-convergence-v1"
} satisfies CallerConvergenceRecord;

function page<T>(items: T[]): ReadResult<ReadPage<T>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("CallersDashboard", () => {
  afterEach(() => cleanup());

  it("renders caller, call and convergence evidence without execution controls", () => {
    render(
      <CallersDashboard
        calls={page([call])}
        convergence={page([convergence])}
        profiles={page([profile])}
      />
    );

    expect(screen.getByRole("heading", { name: "Caller intelligence" })).toBeInTheDocument();
    expect(screen.getAllByText("telegram:alpha")).toHaveLength(2);
    expect(screen.getAllByText("bnb:0x1111111111111111111111111111111111111111")).toHaveLength(2);
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
    expect(screen.getByRole("status", { name: "EXECUTION: LOCKED" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|order|follow|copy/i })).not.toBeInTheDocument();
  });

  it("keeps unavailable caller reads explicit", () => {
    render(
      <CallersDashboard
        calls={{ ok: false, reason: "UNAVAILABLE" }}
        convergence={{ ok: false, reason: "UNAVAILABLE" }}
        profiles={{ ok: false, reason: "UNAVAILABLE" }}
      />
    );

    expect(screen.getAllByText("CALLER INTELLIGENCE UNAVAILABLE")).toHaveLength(3);
  });

  it("renders leaderboard outcome evidence and keeps sparse evidence explicit", () => {
    render(
      <CallersDashboard
        calls={page([])}
        convergence={page([])}
        profiles={page([evaluatedProfile, profile])}
      />
    );

    expect(screen.getByRole("heading", { name: "Caller leaderboard" })).toBeInTheDocument();
    expect(screen.getAllByText("HISTORICAL_REAL").length).toBeGreaterThan(0);
    expect(screen.getByText("1h:2x 75%")).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT_SAMPLES")).toBeInTheDocument();
    expect(screen.queryByText(/guaranteed alpha|buy now|copy trade/i)).not.toBeInTheDocument();
  });
});
