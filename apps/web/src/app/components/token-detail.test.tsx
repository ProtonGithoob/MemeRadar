import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TokenDetailView } from "./token-detail";
import type {
  LaunchLifecycleRecord,
  ReadPage,
  ReadResult,
  TimelineRecord,
  TokenRecord
} from "../lib/read-api";

const TOKEN_ID = "22222222-2222-4222-8222-222222222222";
const token: TokenRecord = {
  id: TOKEN_ID,
  chain: "solana",
  mintAddress: "So11111111111111111111111111111111111111112",
  tokenProgram: "spl-token",
  symbol: "MOON",
  name: "Moon Fixture",
  decimals: 6,
  status: "ACTIVE",
  creatorWallet: "Vote111111111111111111111111111111111111111",
  pools: [
    {
      id: "55555555-5555-4555-8555-555555555555",
      venue: "Raydium",
      poolAddress: "So11111111111111111111111111111111111111112",
      quoteMint: "So11111111111111111111111111111111111111112"
    }
  ],
  candidate: {
    id: "11111111-1111-4111-8111-111111111111",
    tokenId: TOKEN_ID,
    chain: "solana",
    mintAddress: "So11111111111111111111111111111111111111112",
    symbol: "MOON",
    name: "Moon Fixture",
    state: "WATCH",
    discoveredAt: "2026-08-31T12:00:00.000Z",
    discoverySource: "fixture.discovery",
    stateChangedAt: "2026-08-31T12:01:00.000Z",
    score: 84,
    scoreConfidence: 0.9,
    riskDisposition: "PASS",
    riskQualityState: "FRESH",
    riskReasonCodes: ["AUTHORITY_CLEAR"],
    evidenceRefs: ["market:1"]
  },
  launchLifecycle: null
};

const lifecycle: LaunchLifecycleRecord = {
  lifecycleState: "BONDING",
  routeState: "BONDING_ROUTE",
  routeAvailable: null,
  launchpad: "fixturepad",
  creatorAddress: null,
  bondingCurveProgressBps: 4200,
  quoteAsset: "USDC",
  graduationThresholdBps: 8000,
  graduatedAt: null,
  firstVerifiedDexLiquidityAt: null,
  firstVerifiedSwapAt: null,
  liquidityLockState: null,
  poolAddress: null,
  venue: null,
  asOf: "2026-08-31T12:03:00.000Z",
  expiresAt: "2026-08-31T12:08:00.000Z",
  qualityState: "FRESH",
  timeQuality: "EXACT",
  confidence: 0.8,
  reasonCodes: ["BONDING_ROUTE_NOT_NO_ROUTE"],
  evidenceRefs: ["launch:fixture"],
  provenance: [{ provider: "fixture-launchpad", sourceId: "launch:fixture", observedAt: "2026-08-31T12:03:00.000Z", parserVersion: "fixture-v1" }],
  configHash: "launch-lifecycle-read-v2",
  version: "launch-lifecycle-v2"
};

const timeline: TimelineRecord[] = [
  {
    id: "66666666-6666-4666-8666-666666666666",
    tokenId: TOKEN_ID,
    kind: "score.snapshot",
    sourceId: "score:fixture",
    occurredAt: "2026-08-31T12:02:00.000Z",
    observedAt: "2026-08-31T12:02:00.000Z",
    ingestedAt: "2026-08-31T12:02:01.000Z",
    qualityState: "FRESH",
    timeQuality: "EXACT",
    reasonCodes: ["SCORE_READY"],
    evidenceRefs: ["feature:1"],
    payload: { alpha_score: 84, confidence: 0.9 },
    provenance: [{ provider: "score-engine", sourceId: "score:fixture", observedAt: "2026-08-31T12:02:00.000Z", parserVersion: "score-v1" }]
  },
  {
    id: "77777777-7777-4777-8777-777777777777",
    tokenId: TOKEN_ID,
    kind: "market.snapshot",
    sourceId: "market:fixture",
    occurredAt: "2026-08-31T12:03:00.000Z",
    observedAt: "2026-08-31T12:03:00.000Z",
    ingestedAt: "2026-08-31T12:03:01.000Z",
    qualityState: "FRESH",
    timeQuality: "EXACT",
    reasonCodes: [],
    evidenceRefs: ["market:fixture"],
    payload: { price: 1.2, liquidity: 125000, buy_volume: 900, sell_volume: 300 },
    provenance: [{ provider: "market-fixture", sourceId: "market:fixture", observedAt: "2026-08-31T12:03:00.000Z", parserVersion: "market-v1" }]
  },
  {
    id: "88888888-8888-4888-8888-888888888888",
    tokenId: TOKEN_ID,
    kind: "holder.snapshot",
    sourceId: "holder:fixture",
    occurredAt: "2026-08-31T12:04:00.000Z",
    observedAt: "2026-08-31T12:04:00.000Z",
    ingestedAt: "2026-08-31T12:04:01.000Z",
    qualityState: "FRESH",
    timeQuality: "EXACT",
    reasonCodes: ["HOLDER_CLUSTERED"],
    evidenceRefs: ["holder:fixture"],
    payload: { top10_hold_percent: 0.42, clustered_supply_pct: 0.55 },
    provenance: [{ provider: "holder-fixture", sourceId: "holder:fixture", observedAt: "2026-08-31T12:04:00.000Z", parserVersion: "holder-v1" }]
  },
  {
    id: "99999999-9999-4999-8999-999999999999",
    tokenId: TOKEN_ID,
    kind: "social.mention",
    sourceId: "social:fixture",
    occurredAt: "2026-08-31T12:05:00.000Z",
    observedAt: "2026-08-31T12:05:00.000Z",
    ingestedAt: "2026-08-31T12:05:01.000Z",
    qualityState: "FRESH",
    timeQuality: "EXACT",
    reasonCodes: ["SOCIAL_MENTION"],
    evidenceRefs: ["post:fixture"],
    payload: { text: "raw post must not be rendered", author_id: "author-fixture" },
    provenance: [{ provider: "social-fixture", sourceId: "post:fixture", observedAt: "2026-08-31T12:05:00.000Z", parserVersion: "social-v1" }]
  },
  {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    tokenId: TOKEN_ID,
    kind: "narrative.summary",
    sourceId: "narrative:fixture",
    occurredAt: "2026-08-31T12:06:00.000Z",
    observedAt: "2026-08-31T12:06:00.000Z",
    ingestedAt: "2026-08-31T12:06:01.000Z",
    qualityState: "FRESH",
    timeQuality: "EXACT",
    reasonCodes: ["NARRATIVE_ADVISORY"],
    evidenceRefs: ["narrative:fixture"],
    payload: { narrative: "raw narrative must not be rendered" },
    provenance: [{ provider: "narrative-fixture", sourceId: "narrative:fixture", observedAt: "2026-08-31T12:06:00.000Z", parserVersion: "narrative-v1" }]
  }
];

function page<T>(items: T[]): ReadResult<ReadPage<T>> {
  return { ok: true, data: { items, limit: 50, hasMore: false, nextCursor: null } };
}

describe("TokenDetailView", () => {
  afterEach(() => cleanup());

  it("renders overview, event-time evidence, charts, holder clustering and provenance", () => {
    render(<TokenDetailView tokenResult={{ ok: true, data: token }} timelineResult={page(timeline)} />);

    expect(screen.getByRole("heading", { name: /MOON/ })).toBeInTheDocument();
    expect(screen.getByText("Raydium")).toBeInTheDocument();
    expect(screen.getByText("CREATOR WALLET")).toBeInTheDocument();
    expect(screen.getByText("SCORE 84 / 100")).toBeInTheDocument();
    expect(screen.getByText("HOLDER CONCENTRATION / CLUSTERS")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Price evidence chart" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Liquidity evidence chart" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Net flow evidence chart" })).toBeInTheDocument();
    expect(screen.getByText("SOCIAL / NARRATIVE EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("social:fixture")).toBeInTheDocument();
    expect(screen.getByText("narrative:fixture")).toBeInTheDocument();
    expect(screen.queryByText("raw post must not be rendered")).not.toBeInTheDocument();
    expect(screen.queryByText("raw narrative must not be rendered")).not.toBeInTheDocument();
    expect(screen.queryByText("execution_eligible")).not.toBeInTheDocument();
    expect(screen.queryByText("viewer-server-secret")).not.toBeInTheDocument();
  });

  it("keeps empty evidence and unavailable detail explicit", () => {
    const { rerender } = render(
      <TokenDetailView
        tokenResult={{ ok: true, data: token }}
        timelineResult={page([])}
      />
    );
    expect(screen.getByText("NO EVIDENCE YET")).toBeInTheDocument();

    rerender(
      <TokenDetailView
        tokenResult={{ ok: false, reason: "UNAUTHORIZED", status: 401 }}
        timelineResult={{ ok: false, reason: "UNAUTHORIZED", status: 401 }}
      />
    );
    expect(screen.getByText("READ API AUTHORIZATION UNAVAILABLE")).toBeInTheDocument();

    rerender(
      <TokenDetailView
        tokenResult={{ ok: false, reason: "INVALID_RESPONSE" }}
        timelineResult={{ ok: false, reason: "INVALID_RESPONSE" }}
      />
    );
    expect(screen.getByText("INVALID READ RESPONSE")).toBeInTheDocument();
  });

  it("shows lifecycle evidence and keeps bonding route state visible", () => {
    render(
      <TokenDetailView
        tokenResult={{ ok: true, data: { ...token, launchLifecycle: lifecycle } }}
        timelineResult={page([])}
      />
    );

    expect(screen.getByLabelText("Launch lifecycle evidence")).toBeInTheDocument();
    expect(screen.getAllByText("BONDING").length).toBeGreaterThan(0);
    expect(screen.getByText("42.0%")).toBeInTheDocument();
    expect(screen.getByText("BONDING_ROUTE / UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("BONDING_ROUTE_NOT_NO_ROUTE")).toBeInTheDocument();
  });

  it("shows unknown instead of zero for unavailable lifecycle confidence", () => {
    render(
      <TokenDetailView
        tokenResult={{
          ok: true,
          data: {
            ...token,
            launchLifecycle: {
              ...lifecycle,
              lifecycleState: "UNKNOWN",
              routeState: "UNKNOWN",
              routeAvailable: null,
              qualityState: "UNKNOWN",
              confidence: 0,
            },
          },
        }}
        timelineResult={page([])}
      />
    );

    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });
});
