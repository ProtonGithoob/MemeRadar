/**
 * Server-side-by-convention gateway for the bounded operator read API.
 *
 * This module deliberately returns small, validated projections.  It is not
 * imported by client components and never forwards response bodies or private
 * environment values to the browser.
 */

export type ReadFailureReason =
  | "NOT_CONFIGURED"
  | "UNAUTHORIZED"
  | "UNAVAILABLE"
  | "INVALID_RESPONSE";

export type ReadResult<T> =
  | { ok: true; data: T }
  | { ok: false; reason: ReadFailureReason; status?: number };

export interface ReadPage<T> {
  items: T[];
  limit: number;
  hasMore: boolean;
  nextCursor: string | null;
}

export type RiskDisposition = "PASS" | "WARN" | "BLOCK" | "UNKNOWN";
export type CandidateQuality =
  | "FRESH"
  | "STALE"
  | "UNKNOWN"
  | "INVALID"
  | "CONFLICTED";
export type TimelineQuality = CandidateQuality;

export interface RadarFilters {
  state?: string;
  riskDisposition?: RiskDisposition;
  minScore?: number;
}

export interface CandidateRecord {
  id: string;
  tokenId: string;
  mintAddress: string;
  symbol: string | null;
  name: string | null;
  state: string;
  discoveredAt: string;
  discoverySource: string;
  stateChangedAt: string;
  score: number | null;
  scoreConfidence: number | null;
  scoreAsOf?: string | null;
  scoreExpiresAt?: string | null;
  riskDisposition: RiskDisposition;
  riskQualityState: CandidateQuality;
  riskReasonCodes: string[];
  evidenceRefs: string[];
}

export type EarlyRadarState =
  | "REJECT/LOW"
  | "WATCH"
  | "EARLY_WATCH"
  | "STRONG_SETUP"
  | "HIGH_CONFLUENCE"
  | "ENTRY_READY";

export interface AsymmetricAlphaProjectionRecord {
  earlyQualityScore: number;
  upsideEvidenceScore: number;
  rugDumpRisk: number;
  executionQuality: number;
  evidenceConfidence: number;
  launchAgeMs: number | null;
  marketCapAtDecision: number | null;
  reasonCodes: string[];
  strategyVersion: string;
  configHash: string;
}

export interface EarlyRadarRecord {
  candidateId: string;
  tokenId: string;
  mintAddress: string;
  symbol: string | null;
  name: string | null;
  launchAgeSeconds: number | null;
  firstSeenAt: string;
  firstSeenSource: string;
  firstSeenLatencyMs: number | null;
  firstSeenQuality: CandidateQuality;
  earlyScore: number | null;
  earlyScoreConfidence: number | null;
  earlyState: EarlyRadarState;
  riskDisposition: RiskDisposition;
  buyVelocity: Record<string, unknown>;
  buyAcceleration: Record<string, unknown>;
  uniqueBuyers: Record<string, unknown>;
  quoteInflow: Record<string, unknown>;
  liquidityUsd: number | null;
  priceImpactBps: number | null;
  creatorRisk: string;
  bundleRisk: string;
  holderRisk: string;
  smartMoneyConfluence: number | null;
  sellability: string;
  shadowEntryStatus: string;
  externalCallLeadTimeMs: number | null;
  hardBlockReasons: string[];
  latencyMs: Record<string, unknown>;
  evidenceRefs: string[];
  reasonCodes: string[];
  asymmetricAlpha?: AsymmetricAlphaProjectionRecord | null;
}

export interface PoolRecord {
  id: string;
  venue: string;
  poolAddress: string;
  quoteMint: string;
}

export interface TokenRecord {
  id: string;
  chain: string;
  mintAddress: string;
  tokenProgram: string;
  symbol: string | null;
  name: string | null;
  decimals: number | null;
  createdOnchainAt?: string | null;
  firstSeenAt?: string | null;
  status: string;
  creatorWallet: string | null;
  pools: PoolRecord[];
  candidate: CandidateRecord | null;
}

export interface ProvenanceRecord {
  provider: string;
  sourceId: string;
  observedAt: string;
  parserVersion: string;
}

export interface TimelineRecord {
  id: string;
  tokenId: string;
  kind: string;
  sourceId: string;
  occurredAt: string;
  observedAt: string;
  ingestedAt: string;
  qualityState: TimelineQuality;
  reasonCodes: string[];
  evidenceRefs: string[];
  payload: Record<string, unknown>;
  provenance: ProvenanceRecord[];
}

export type WalletTier = "CANDIDATE" | "TIER_A" | "TIER_B" | "BLOCKED" | "UNKNOWN";

export interface WalletRecord {
  address: string;
  label: string;
  registryTier: WalletTier;
  recommendedTier: WalletTier;
  asOf: string;
  expiresAt: string;
  score: number | null;
  confidence: number | null;
  sampleCount: number;
  knownOutcomeCount: number;
  winRate: number | null;
  realizedPnl: number | null;
  qualityState: TimelineQuality;
  reasonCodes: string[];
  evidenceRefs: string[];
}

export type ProviderHealthState = "HEALTHY" | "DEGRADED" | "DOWN" | "UNKNOWN";

export interface ProviderHealthRecord {
  provider: string;
  capability: string;
  state: ProviderHealthState;
  checkedAt: string;
  latencyMs: number | null;
  quota: Record<string, unknown>;
  freshnessState: TimelineQuality | null;
  errorClass: string | null;
  consecutiveFailures: number;
}

export type OperationalState = "HEALTHY" | "DEGRADED" | "DOWN" | "UNKNOWN";
export type OperationalSloState = "UNVERIFIED" | "MEASURED" | "VIOLATED";
export type OperationalAlertSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface OperationalProviderRecord {
  provider: string;
  capability: string;
  state: OperationalState;
  sloState: OperationalSloState;
  checkedAt: string;
  latencyMs: number | null;
  freshnessState: TimelineQuality | null;
  quotaLimit: number | null;
  quotaRemaining: number | null;
  quotaResetAt: string | null;
  costTodayUsd: number | null;
  costBudgetUsd: number | null;
  errorClass: string | null;
  consecutiveFailures: number;
  reasonCodes: string[];
}

export interface OperationalAlertRecord {
  code: string;
  severity: OperationalAlertSeverity;
  dedupeKey: string;
  provider: string | null;
  capability: string | null;
  message: string;
  observedAt: string;
  reasonCodes: string[];
}

export interface OperationsModesRecord {
  analysisOnly: true;
  paperTrading: true;
  manualExecution: false;
  autoExecution: false;
}

export interface OperationsRecord {
  schemaVersion: "operations-overview-v1";
  asOf: string;
  overallState: OperationalState;
  sloState: OperationalSloState;
  policyVersion: string;
  measurementMethod: string;
  providers: OperationalProviderRecord[];
  alerts: OperationalAlertRecord[];
  metrics: Record<string, unknown>;
  earlyDetection: Record<string, unknown>;
  modes: OperationsModesRecord;
  executionEligible: false;
}

export interface AuditEventRecord {
  id: string;
  actor: string;
  action: string;
  target: string;
  occurredAt: string;
  correlationId: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface ConfigVersionRecord {
  id: string;
  version: string;
  createdAt: string;
  actor: string;
  configHash: string;
  decisionAffecting: boolean;
  config: Record<string, unknown>;
}

export interface WalletFilters {
  tier?: Exclude<WalletTier, "UNKNOWN">;
  minScore?: number;
  minConfidence?: number;
  qualityState?: TimelineQuality;
}

export interface ProviderHealthFilters {
  provider?: string;
  capability?: string;
  state?: ProviderHealthState;
}

export interface AuditFilters {
  actor?: string;
  action?: string;
  target?: string;
}

export interface ConfigFilters {
  decisionAffecting?: boolean;
}

export interface ProtectedModesRecord {
  analysisOnly: boolean;
  paperTrading: boolean;
  manualExecution: boolean;
  autoExecution: boolean;
}

export interface ControlStateRecord {
  apiVersion: string;
  analysisPaused: boolean;
  executionKillSwitch: boolean;
  version: number;
  updatedAt: string;
  updatedBy: string;
  correlationId: string;
  protectedModes: ProtectedModesRecord;
}

export interface ControlConfigRecord {
  apiVersion: string;
  id: string;
  version: string;
  createdAt: string;
  actor: string;
  configHash: string;
  decisionAffecting: boolean;
  config: Record<string, unknown>;
}

export type PositionMode = "PAPER" | "LIVE";
export type PositionState = "PENDING" | "OPEN" | "EXIT_SIGNALLED" | "CLOSED";

export interface PositionMarkRecord {
  price: number | null;
  occurredAt: string;
  observedAt: string;
  ingestedAt: string;
  provider: string;
  sourceId: string;
  parserVersion: string;
  qualityState: TimelineQuality;
  evidenceRefs: string[];
}

export interface PositionPerformanceRecord {
  asOf: string;
  qualityState: TimelineQuality;
  realizedPnl: number;
  mfe: number;
  mae: number;
  highWatermark: number;
  currentValue: number | null;
  unrealizedPnl: number | null;
  totalPnl: number | null;
  returnRatio: number | null;
  evidenceRefs: string[];
}

export interface PositionExitRiskRecord {
  evaluationId: string;
  evaluatedAt: string;
  action: string;
  exitFraction: number;
  score: number;
  confidence: number;
  qualityState: TimelineQuality;
  triggeredRules: string[];
  reasonCodes: string[];
  evidenceRefs: string[];
  policyVersion: string;
  configHash: string;
}

export interface ClosedTradeExplanationRecord {
  evaluationId: string | null;
  closedAt: string;
  averageExit: number;
  realizedPnl: number;
  action: string;
  reasonCodes: string[];
  evidenceRefs: string[];
  beforeEvidenceRefs: string[];
  afterEvidenceRefs: string[];
  policyVersion: string | null;
  configHash: string | null;
}

export interface PositionRecord {
  id: string;
  portfolioId: string;
  tokenId: string;
  mintAddress: string;
  symbol: string | null;
  name: string | null;
  mode: PositionMode;
  state: PositionState;
  quantity: number;
  averageEntry: number;
  openedAt: string | null;
  closedAt: string | null;
  averageExit: number | null;
  realizedPnl: number;
  highWatermark: number;
  mfe: number;
  mae: number;
  currentMark: PositionMarkRecord | null;
  performance: PositionPerformanceRecord;
  exitRisk: PositionExitRiskRecord | null;
  closedTrade: ClosedTradeExplanationRecord | null;
  latestActivityAt: string | null;
}

export interface PositionFilters {
  portfolioId?: string;
  mode?: PositionMode;
  state?: PositionState;
  asOf?: string;
}

const DEFAULT_LIMIT = 50;
const MAX_PAGE_LIMIT = 100;
const MAX_STRING_LENGTH = 512;
const MAX_ARRAY_LENGTH = 64;
const MAX_PAYLOAD_KEYS = 64;
const MAX_PAYLOAD_DEPTH = 4;
const REQUEST_TIMEOUT_MS = 4_000;
const SECRET_KEY_PATTERN =
  /(?:api[_ -]?key|access[_ -]?token|authorization|bearer|bot[_ -]?token|client[_ -]?secret|cookie|password|private[_ -]?key|seed(?:[_ -]?phrase)?|session[_ -]?token)/i;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SOLANA_ADDRESS_PATTERN = /^[1-9A-HJ-NP-Za-km-z]{32,64}$/;
const CANDIDATE_STATES = new Set([
  "DISCOVERED",
  "ENRICHING",
  "RISK_REJECTED",
  "WATCH",
  "STRONG_SETUP",
  "ENTRY_READY",
  "PAPER_OPEN",
  "LIVE_PENDING_APPROVAL",
  "OPEN",
  "EXIT_SIGNALLED",
  "CLOSED"
]);
const RISK_DISPOSITIONS = new Set<RiskDisposition>(["PASS", "WARN", "BLOCK", "UNKNOWN"]);
const QUALITY_STATES = new Set<CandidateQuality>([
  "FRESH",
  "STALE",
  "UNKNOWN",
  "INVALID",
  "CONFLICTED"
]);
const WALLET_TIERS = new Set<WalletTier>([
  "CANDIDATE",
  "TIER_A",
  "TIER_B",
  "BLOCKED",
  "UNKNOWN"
]);
const PROVIDER_HEALTH_STATES = new Set<ProviderHealthState>([
  "HEALTHY",
  "DEGRADED",
  "DOWN",
  "UNKNOWN"
]);
const OPERATIONAL_STATES = new Set<OperationalState>(["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"]);
const OPERATIONAL_SLO_STATES = new Set<OperationalSloState>(["UNVERIFIED", "MEASURED", "VIOLATED"]);
const OPERATIONAL_ALERT_SEVERITIES = new Set<OperationalAlertSeverity>([
  "INFO",
  "WARNING",
  "CRITICAL"
]);
const POSITION_MODES = new Set<PositionMode>(["PAPER", "LIVE"]);
const POSITION_STATES = new Set<PositionState>([
  "PENDING",
  "OPEN",
  "EXIT_SIGNALLED",
  "CLOSED"
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function boundedString(value: unknown, maxLength = MAX_STRING_LENGTH): string | null {
  return typeof value === "string" && value.length > 0 && value.length <= maxLength ? value : null;
}

function nullableString(value: unknown, maxLength = MAX_STRING_LENGTH): string | null {
  if (value === null || value === undefined) return null;
  return boundedString(value, maxLength);
}

function uuid(value: unknown): string | null {
  return typeof value === "string" && UUID_PATTERN.test(value) ? value : null;
}

function timestamp(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64 || !value.includes("T")) return null;
  return Number.isFinite(Date.parse(value)) ? value : null;
}

function finiteNumber(value: unknown, minimum: number, maximum: number): number | null {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null;
}

function optionalFiniteNumber(
  value: unknown,
  minimum: number,
  maximum: number
): number | null | undefined {
  if (value === null || value === undefined) return null;
  const parsed = finiteNumber(value, minimum, maximum);
  return parsed === null ? undefined : parsed;
}

function stringArray(value: unknown, maxLength = MAX_STRING_LENGTH): string[] | null {
  if (!Array.isArray(value) || value.length > MAX_ARRAY_LENGTH) return null;
  const values = value.map((item) => boundedString(item, maxLength));
  return values.every((item): item is string => item !== null) ? values : null;
}

function safePayloadValue(value: unknown, depth: number): unknown | undefined {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "string") return value.length <= MAX_STRING_LENGTH ? value : undefined;
  if (typeof value === "number") return Number.isFinite(value) ? value : undefined;
  if (depth >= MAX_PAYLOAD_DEPTH) return undefined;
  if (Array.isArray(value)) {
    if (value.length > MAX_ARRAY_LENGTH) return undefined;
    const result: unknown[] = [];
    for (const item of value) {
      const parsed = safePayloadValue(item, depth + 1);
      if (parsed === undefined) return undefined;
      result.push(parsed);
    }
    return result;
  }
  if (!isRecord(value) || Object.keys(value).length > MAX_PAYLOAD_KEYS) return undefined;
  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    const safeKey = boundedString(key, 128);
    if (safeKey !== null && SECRET_KEY_PATTERN.test(safeKey)) {
      result[safeKey] = "[REDACTED]";
      continue;
    }
    const parsed = safePayloadValue(item, depth + 1);
    if (safeKey === null || parsed === undefined) return undefined;
    result[safeKey] = parsed;
  }
  return result;
}

function safePayload(value: unknown): Record<string, unknown> | null {
  const parsed = safePayloadValue(value, 0);
  return isRecord(parsed) ? parsed : null;
}

function parseCandidate(value: unknown): CandidateRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const tokenId = uuid(value.token_id);
  const mintAddress = boundedString(value.mint_address, 128);
  const symbol = nullableString(value.symbol, 64);
  const name = nullableString(value.name, 256);
  const state = boundedString(value.state, 64);
  const discoveredAt = timestamp(value.discovered_at);
  const discoverySource = boundedString(value.discovery_source, 256);
  const stateChangedAt = timestamp(value.state_changed_at);
  const score = optionalFiniteNumber(value.score, 0, 100);
  const scoreConfidence = optionalFiniteNumber(value.score_confidence, 0, 1);
  const scoreAsOf = value.score_as_of === null || value.score_as_of === undefined
    ? null
    : timestamp(value.score_as_of);
  const scoreExpiresAt = value.score_expires_at === null || value.score_expires_at === undefined
    ? null
    : timestamp(value.score_expires_at);
  const riskDisposition = value.risk_disposition === null || value.risk_disposition === undefined
    ? "UNKNOWN"
    : boundedString(value.risk_disposition, 16);
  const riskQualityState = value.risk_quality_state === null || value.risk_quality_state === undefined
    ? "UNKNOWN"
    : boundedString(value.risk_quality_state, 16);
  const riskReasonCodes = stringArray(value.risk_reason_codes, 128);
  const evidenceRefs = stringArray(value.evidence_refs, 256);

  if (
    id === null || tokenId === null || mintAddress === null || state === null ||
    !CANDIDATE_STATES.has(state) || discoveredAt === null || discoverySource === null ||
    stateChangedAt === null || score === undefined || scoreConfidence === undefined ||
    scoreAsOf === undefined || scoreExpiresAt === undefined || riskDisposition === null ||
    !RISK_DISPOSITIONS.has(riskDisposition as RiskDisposition) || riskQualityState === null ||
    !QUALITY_STATES.has(riskQualityState as CandidateQuality) || riskReasonCodes === null ||
    evidenceRefs === null
  ) {
    return null;
  }

  return {
    id,
    tokenId,
    mintAddress,
    symbol,
    name,
    state,
    discoveredAt,
    discoverySource,
    stateChangedAt,
    score,
    scoreConfidence,
    scoreAsOf,
    scoreExpiresAt,
    riskDisposition: riskDisposition as RiskDisposition,
    riskQualityState: riskQualityState as CandidateQuality,
    riskReasonCodes,
    evidenceRefs
  };
}

const EARLY_RADAR_STATES = new Set<EarlyRadarState>([
  "REJECT/LOW",
  "WATCH",
  "EARLY_WATCH",
  "STRONG_SETUP",
  "HIGH_CONFLUENCE",
  "ENTRY_READY"
]);

function parseEarlyRadar(value: unknown): EarlyRadarRecord | null {
  if (!isRecord(value)) return null;
  const candidateId = uuid(value.candidate_id);
  const tokenId = uuid(value.token_id);
  const mintAddress = boundedString(value.mint_address, 128);
  const symbol = nullableString(value.symbol, 64);
  const name = nullableString(value.name, 256);
  const launchAgeSeconds = optionalFiniteNumber(value.launch_age_seconds, 0, 1e12);
  const firstSeenAt = timestamp(value.first_seen_at);
  const firstSeenSource = boundedString(value.first_seen_source, 256);
  const firstSeenLatencyMs = optionalFiniteNumber(value.first_seen_latency_ms, 0, 1e12);
  const firstSeenQuality = optionalQuality(value.first_seen_quality);
  const earlyScore = optionalFiniteNumber(value.early_score, 0, 100);
  const earlyScoreConfidence = optionalFiniteNumber(value.early_score_confidence, 0, 1);
  const earlyState = boundedString(value.early_state, 32);
  const riskDisposition = boundedString(value.risk_disposition, 16);
  const buyVelocity = safePayload(value.buy_velocity ?? {});
  const buyAcceleration = safePayload(value.buy_acceleration ?? {});
  const uniqueBuyers = safePayload(value.unique_buyers ?? {});
  const quoteInflow = safePayload(value.quote_inflow ?? {});
  const liquidityUsd = optionalFiniteNumber(value.liquidity_usd, 0, 1e24);
  const priceImpactBps = optionalFiniteNumber(value.price_impact_bps, 0, 1e12);
  const creatorRisk = boundedString(value.creator_risk, 32);
  const bundleRisk = boundedString(value.bundle_risk, 32);
  const holderRisk = boundedString(value.holder_risk, 32);
  const smartMoneyConfluence = optionalFiniteNumber(value.smart_money_confluence, 0, 100);
  const sellability = boundedString(value.sellability, 32);
  const shadowEntryStatus = boundedString(value.shadow_entry_status, 64);
  const externalCallLeadTimeMs = optionalFiniteNumber(value.external_call_lead_time_ms, 0, 1e12);
  const hardBlockReasons = stringArray(value.hard_block_reasons, 128);
  const latencyMs = safePayload(value.latency_ms ?? {});
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  const reasonCodes = stringArray(value.reason_codes, 128);

  if (
    candidateId === null || tokenId === null || mintAddress === null || firstSeenAt === null ||
    launchAgeSeconds === undefined || firstSeenLatencyMs === undefined ||
    firstSeenSource === null || firstSeenQuality === null || firstSeenQuality === undefined ||
    earlyScore === undefined || earlyScoreConfidence === undefined || earlyState === null ||
    !EARLY_RADAR_STATES.has(earlyState as EarlyRadarState) || riskDisposition === null ||
    !RISK_DISPOSITIONS.has(riskDisposition as RiskDisposition) || buyVelocity === null ||
    buyAcceleration === null || uniqueBuyers === null || quoteInflow === null ||
    liquidityUsd === undefined || priceImpactBps === undefined || creatorRisk === null ||
    bundleRisk === null || holderRisk === null || smartMoneyConfluence === undefined ||
    sellability === null || shadowEntryStatus === null || externalCallLeadTimeMs === undefined ||
    hardBlockReasons === null || latencyMs === null || evidenceRefs === null || reasonCodes === null ||
    value.execution_eligible === true || value.auto_execution !== "LOCKED"
  ) {
    return null;
  }
  let asymmetricAlpha: AsymmetricAlphaProjectionRecord | null = null;
  if (isRecord(value.asymmetric_alpha)) {
    const rawAlpha = value.asymmetric_alpha;
    const eq = optionalFiniteNumber(rawAlpha.early_quality_score, 0, 100);
    const ue = optionalFiniteNumber(rawAlpha.upside_evidence_score, 0, 100);
    const rd = optionalFiniteNumber(rawAlpha.rug_dump_risk, 0, 100);
    const ex = optionalFiniteNumber(rawAlpha.execution_quality, 0, 100);
    const ec = optionalFiniteNumber(rawAlpha.evidence_confidence, 0, 1);
    if (eq != null && ue != null && rd != null && ex != null && ec != null) {
      asymmetricAlpha = {
        earlyQualityScore: eq,
        upsideEvidenceScore: ue,
        rugDumpRisk: rd,
        executionQuality: ex,
        evidenceConfidence: ec,
        launchAgeMs: optionalFiniteNumber(rawAlpha.launch_age_ms, 0, 1e12) ?? null,
        marketCapAtDecision: optionalFiniteNumber(rawAlpha.market_cap_at_decision, 0, 1e24) ?? null,
        reasonCodes: stringArray(rawAlpha.reason_codes, 128) ?? [],
        strategyVersion: boundedString(rawAlpha.strategy_version, 64) ?? "asymmetric-alpha-v1",
        configHash: boundedString(rawAlpha.config_hash, 64) ?? "asymmetric-alpha-hash",
      };
    }
  }

  return {
    candidateId,
    tokenId,
    mintAddress,
    symbol,
    name,
    launchAgeSeconds,
    firstSeenAt,
    firstSeenSource,
    firstSeenLatencyMs,
    firstSeenQuality,
    earlyScore,
    earlyScoreConfidence,
    earlyState: earlyState as EarlyRadarState,
    riskDisposition: riskDisposition as RiskDisposition,
    buyVelocity,
    buyAcceleration,
    uniqueBuyers,
    quoteInflow,
    liquidityUsd,
    priceImpactBps,
    creatorRisk,
    bundleRisk,
    holderRisk,
    smartMoneyConfluence,
    sellability,
    shadowEntryStatus,
    externalCallLeadTimeMs,
    hardBlockReasons,
    latencyMs,
    evidenceRefs,
    reasonCodes,
    asymmetricAlpha
  };
}

function parsePool(value: unknown): PoolRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const venue = boundedString(value.venue, 128);
  const poolAddress = boundedString(value.pool_address, 128);
  const quoteMint = boundedString(value.quote_mint, 128);
  return id && venue && poolAddress && quoteMint ? { id, venue, poolAddress, quoteMint } : null;
}

function parseToken(value: unknown): TokenRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const chain = boundedString(value.chain, 32);
  const mintAddress = boundedString(value.mint_address, 128);
  const tokenProgram = boundedString(value.token_program, 128);
  const symbol = nullableString(value.symbol, 64);
  const name = nullableString(value.name, 256);
  const decimals = optionalFiniteNumber(value.decimals, 0, 255);
  const createdOnchainAt = value.created_onchain_at === null || value.created_onchain_at === undefined
    ? null
    : timestamp(value.created_onchain_at);
  const firstSeenAt = value.first_seen_at === null || value.first_seen_at === undefined
    ? null
    : timestamp(value.first_seen_at);
  const status = boundedString(value.status, 64);
  const creatorWallet = nullableString(value.creator_wallet, 128);
  const rawPools = value.pools;
  const pools = Array.isArray(rawPools) && rawPools.length <= MAX_ARRAY_LENGTH
    ? rawPools.map(parsePool)
    : null;
  const candidate = value.candidate === null || value.candidate === undefined
    ? null
    : parseCandidate(value.candidate);

  if (
    id === null || chain === null || mintAddress === null || tokenProgram === null ||
    decimals === undefined || (decimals !== null && !Number.isInteger(decimals)) ||
    createdOnchainAt === undefined || firstSeenAt === undefined ||
    status === null || creatorWallet === undefined || pools === null ||
    pools.some((pool): pool is null => pool === null) ||
    (value.candidate !== null && value.candidate !== undefined && candidate === null)
  ) {
    return null;
  }

  return {
    id,
    chain,
    mintAddress,
    tokenProgram,
    symbol,
    name,
    decimals,
    createdOnchainAt,
    firstSeenAt,
    status,
    creatorWallet,
    pools: pools as PoolRecord[],
    candidate
  };
}

function parseProvenance(value: unknown): ProvenanceRecord | null {
  if (!isRecord(value)) return null;
  const provider = boundedString(value.provider, 128);
  const sourceId = boundedString(value.source_id, 256);
  const observedAt = timestamp(value.observed_at);
  const parserVersion = boundedString(value.parser_version, 128);
  return provider && sourceId && observedAt && parserVersion
    ? { provider, sourceId, observedAt, parserVersion }
    : null;
}

function parseTimeline(value: unknown): TimelineRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const tokenId = uuid(value.token_id);
  const kind = boundedString(value.kind, 128);
  const sourceId = boundedString(value.source_id, 256);
  const occurredAt = timestamp(value.occurred_at);
  const observedAt = timestamp(value.observed_at);
  const ingestedAt = timestamp(value.ingested_at);
  const qualityState = boundedString(value.quality_state, 16);
  const reasonCodes = stringArray(value.reason_codes, 128);
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  const payload = safePayload(value.payload ?? {});
  const rawProvenance = value.provenance ?? [];
  const provenance = Array.isArray(rawProvenance) && rawProvenance.length <= MAX_ARRAY_LENGTH
    ? rawProvenance.map(parseProvenance)
    : null;

  if (
    id === null || tokenId === null || kind === null || sourceId === null ||
    occurredAt === null || observedAt === null || ingestedAt === null ||
    qualityState === null || !QUALITY_STATES.has(qualityState as TimelineQuality) ||
    reasonCodes === null || evidenceRefs === null || payload === null || provenance === null ||
    provenance.some((item): item is null => item === null)
  ) {
    return null;
  }
  if (Date.parse(occurredAt) > Date.parse(observedAt) || Date.parse(observedAt) > Date.parse(ingestedAt)) {
    return null;
  }

  return {
    id,
    tokenId,
    kind,
    sourceId,
    occurredAt,
    observedAt,
    ingestedAt,
    qualityState: qualityState as TimelineQuality,
    reasonCodes,
    evidenceRefs,
    payload,
    provenance: provenance as ProvenanceRecord[]
  };
}

function optionalTimestamp(value: unknown): string | null | undefined {
  if (value === null || value === undefined) return null;
  const parsed = timestamp(value);
  return parsed === null ? undefined : parsed;
}

function optionalBoundedString(value: unknown, maxLength = MAX_STRING_LENGTH): string | null | undefined {
  if (value === null || value === undefined) return null;
  const parsed = boundedString(value, maxLength);
  return parsed === null ? undefined : parsed;
}

function integer(value: unknown, minimum: number, maximum: number): number | null {
  const parsed = finiteNumber(value, minimum, maximum);
  return parsed !== null && Number.isInteger(parsed) ? parsed : null;
}

function optionalInteger(value: unknown, minimum: number, maximum: number): number | null | undefined {
  if (value === null || value === undefined) return null;
  const parsed = integer(value, minimum, maximum);
  return parsed === null ? undefined : parsed;
}

function optionalQuality(value: unknown): TimelineQuality | null | undefined {
  if (value === null || value === undefined) return null;
  const parsed = boundedString(value, 16);
  return parsed !== null && QUALITY_STATES.has(parsed as TimelineQuality)
    ? parsed as TimelineQuality
    : undefined;
}

function parseWallet(value: unknown): WalletRecord | null {
  if (!isRecord(value)) return null;
  const address = boundedString(value.address, 64);
  const label = boundedString(value.label, 256);
  const registryTier = boundedString(value.registry_tier, 32);
  const recommendedTier = boundedString(value.recommended_tier, 32);
  const asOf = timestamp(value.as_of);
  const expiresAt = timestamp(value.expires_at);
  const score = optionalFiniteNumber(value.score, 0, 100);
  const confidence = optionalFiniteNumber(value.confidence, 0, 1);
  const sampleCount = integer(value.sample_count, 0, 1_000_000);
  const knownOutcomeCount = integer(value.known_outcome_count, 0, 1_000_000);
  const winRate = optionalFiniteNumber(value.win_rate, 0, 1);
  const realizedPnl = optionalFiniteNumber(value.realized_pnl, -1_000_000_000_000, 1_000_000_000_000);
  const qualityState = optionalQuality(value.quality_state);
  const reasonCodes = stringArray(value.reason_codes, 128);
  const evidenceRefs = stringArray(value.evidence_refs, 256);

  if (
    address === null || !SOLANA_ADDRESS_PATTERN.test(address) || label === null ||
    registryTier === null || !WALLET_TIERS.has(registryTier as WalletTier) ||
    recommendedTier === null || !WALLET_TIERS.has(recommendedTier as WalletTier) ||
    asOf === null || expiresAt === null || Date.parse(expiresAt) <= Date.parse(asOf) ||
    score === undefined || confidence === undefined || sampleCount === null ||
    knownOutcomeCount === null || winRate === undefined || realizedPnl === undefined ||
    qualityState === null || qualityState === undefined || reasonCodes === null ||
    evidenceRefs === null || value.execution_eligible === true
  ) {
    return null;
  }

  return {
    address,
    label,
    registryTier: registryTier as WalletTier,
    recommendedTier: recommendedTier as WalletTier,
    asOf,
    expiresAt,
    score,
    confidence,
    sampleCount,
    knownOutcomeCount,
    winRate,
    realizedPnl,
    qualityState,
    reasonCodes,
    evidenceRefs
  };
}

function parseProviderHealth(value: unknown): ProviderHealthRecord | null {
  if (!isRecord(value)) return null;
  const provider = boundedString(value.provider, 128);
  const capability = boundedString(value.capability, 128);
  const state = boundedString(value.state, 16);
  const checkedAt = timestamp(value.checked_at);
  const latencyMs = optionalFiniteNumber(value.latency_ms, 0, 300_000);
  const quota = safePayload(value.quota ?? {});
  const freshnessState = optionalQuality(value.freshness_state);
  const errorClass = optionalBoundedString(value.error_class, 128);
  const consecutiveFailures = integer(value.consecutive_failures, 0, 1_000_000);
  if (
    provider === null || capability === null || state === null ||
    !PROVIDER_HEALTH_STATES.has(state as ProviderHealthState) || checkedAt === null ||
    latencyMs === undefined || quota === null || freshnessState === undefined ||
    errorClass === undefined || consecutiveFailures === null
  ) {
    return null;
  }
  return {
    provider,
    capability,
    state: state as ProviderHealthState,
    checkedAt,
    latencyMs,
    quota,
    freshnessState,
    errorClass,
    consecutiveFailures
  };
}

function parseOperationalProvider(value: unknown): OperationalProviderRecord | null {
  if (!isRecord(value)) return null;
  const provider = boundedString(value.provider, 128);
  const capability = boundedString(value.capability, 128);
  const state = boundedString(value.state, 16);
  const sloState = boundedString(value.slo_state, 16);
  const checkedAt = timestamp(value.checked_at);
  const latencyMs = optionalFiniteNumber(value.latency_ms, 0, 300_000);
  const freshnessState = optionalQuality(value.freshness_state);
  const quotaLimit = optionalInteger(value.quota_limit, 0, 1_000_000_000);
  const quotaRemaining = optionalInteger(value.quota_remaining, 0, 1_000_000_000);
  const quotaResetAt = optionalTimestamp(value.quota_reset_at);
  const costTodayUsd = optionalFiniteNumber(value.cost_today_usd, 0, 1_000_000_000);
  const costBudgetUsd = optionalFiniteNumber(value.cost_budget_usd, 0, 1_000_000_000);
  const errorClass = optionalBoundedString(value.error_class, 128);
  const consecutiveFailures = integer(value.consecutive_failures, 0, 1_000_000);
  const reasonCodes = stringArray(value.reason_codes, 128);
  if (
    provider === null || capability === null || state === null ||
    !OPERATIONAL_STATES.has(state as OperationalState) || sloState === null ||
    !OPERATIONAL_SLO_STATES.has(sloState as OperationalSloState) || checkedAt === null ||
    latencyMs === undefined || freshnessState === undefined || quotaLimit === undefined ||
    quotaRemaining === undefined || quotaResetAt === undefined || costTodayUsd === undefined ||
    costBudgetUsd === undefined || errorClass === undefined ||
    consecutiveFailures === null || reasonCodes === null
  ) {
    return null;
  }
  if (
    quotaLimit !== null && quotaRemaining !== null && quotaRemaining > quotaLimit
  ) {
    return null;
  }
  return {
    provider,
    capability,
    state: state as OperationalState,
    sloState: sloState as OperationalSloState,
    checkedAt,
    latencyMs,
    freshnessState,
    quotaLimit,
    quotaRemaining,
    quotaResetAt,
    costTodayUsd,
    costBudgetUsd,
    errorClass,
    consecutiveFailures,
    reasonCodes
  };
}

function parseOperationalAlert(value: unknown): OperationalAlertRecord | null {
  if (!isRecord(value)) return null;
  const code = boundedString(value.code, 64);
  const severity = boundedString(value.severity, 16);
  const dedupeKey = boundedString(value.dedupe_key, 256);
  const provider = nullableString(value.provider, 128);
  const capability = nullableString(value.capability, 128);
  const message = boundedString(value.message, 256);
  const observedAt = timestamp(value.observed_at);
  const reasonCodes = stringArray(value.reason_codes, 128);
  if (
    code === null || severity === null || !OPERATIONAL_ALERT_SEVERITIES.has(severity as OperationalAlertSeverity) ||
    dedupeKey === null || provider === undefined || capability === undefined || message === null ||
    observedAt === null || reasonCodes === null
  ) {
    return null;
  }
  return {
    code,
    severity: severity as OperationalAlertSeverity,
    dedupeKey,
    provider,
    capability,
    message,
    observedAt,
    reasonCodes
  };
}

function parseOperations(value: unknown): OperationsRecord | null {
  if (!isRecord(value)) return null;
  const schemaVersion = boundedString(value.schema_version, 64);
  const asOf = timestamp(value.as_of);
  const overallState = boundedString(value.overall_state, 16);
  const sloState = boundedString(value.slo_state, 16);
  const policyVersion = boundedString(value.policy_version, 64);
  const measurementMethod = boundedString(value.measurement_method, 64);
  const rawProviders = value.providers;
  const rawAlerts = value.alerts;
  const providers = Array.isArray(rawProviders) && rawProviders.length <= MAX_ARRAY_LENGTH
    ? rawProviders.map(parseOperationalProvider)
    : null;
  const alerts = Array.isArray(rawAlerts) && rawAlerts.length <= MAX_ARRAY_LENGTH
    ? rawAlerts.map(parseOperationalAlert)
    : null;
  const metrics = safePayload(value.metrics ?? {});
  const earlyDetection = safePayload(value.early_detection ?? {});
  const modes = value.modes;
  if (!isRecord(modes)) return null;
  const normalizedModes = {
    analysisOnly: modes.analysis_only,
    paperTrading: modes.paper_trading,
    manualExecution: modes.manual_execution,
    autoExecution: modes.auto_execution
  };
  if (
    schemaVersion !== "operations-overview-v1" || asOf === null || overallState === null ||
    !OPERATIONAL_STATES.has(overallState as OperationalState) || sloState === null ||
    !OPERATIONAL_SLO_STATES.has(sloState as OperationalSloState) || policyVersion === null ||
    measurementMethod === null || providers === null || providers.some((item) => item === null) ||
    alerts === null || alerts.some((item) => item === null) || metrics === null ||
    earlyDetection === null ||
    normalizedModes.analysisOnly !== true || normalizedModes.paperTrading !== true ||
    normalizedModes.manualExecution !== false || normalizedModes.autoExecution !== false ||
    value.execution_eligible !== false
  ) {
    return null;
  }
  return {
    schemaVersion,
    asOf,
    overallState: overallState as OperationalState,
    sloState: sloState as OperationalSloState,
    policyVersion,
    measurementMethod,
    providers: providers as OperationalProviderRecord[],
    alerts: alerts as OperationalAlertRecord[],
    metrics,
    earlyDetection,
    modes: normalizedModes as OperationsModesRecord,
    executionEligible: false
  };
}

function parseAuditEvent(value: unknown): AuditEventRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const actor = boundedString(value.actor, 256);
  const action = boundedString(value.action, 256);
  const target = boundedString(value.target, 256);
  const occurredAt = timestamp(value.occurred_at);
  const correlationId = boundedString(value.correlation_id, 128);
  const before = safePayload(value.before ?? {});
  const after = safePayload(value.after ?? {});
  if (
    id === null || actor === null || action === null || target === null ||
    occurredAt === null || correlationId === null || before === null || after === null
  ) {
    return null;
  }
  return { id, actor, action, target, occurredAt, correlationId, before, after };
}

function parseConfigVersion(value: unknown): ConfigVersionRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const version = boundedString(value.version, 64);
  const createdAt = timestamp(value.created_at);
  const actor = boundedString(value.actor, 256);
  const configHash = boundedString(value.config_hash, 128);
  const decisionAffecting = value.decision_affecting;
  const config = safePayload(value.config ?? {});
  if (
    id === null || version === null || createdAt === null || actor === null ||
    configHash === null || typeof decisionAffecting !== "boolean" || config === null
  ) {
    return null;
  }
  return { id, version, createdAt, actor, configHash, decisionAffecting, config };
}

function parseOptionalPositionNumber(
  value: unknown,
  minimum: number,
  maximum: number
): number | null | undefined {
  return optionalFiniteNumber(value, minimum, maximum);
}

function parsePositionMark(value: unknown): PositionMarkRecord | null | undefined {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return undefined;
  const rawPrice = parseOptionalPositionNumber(value.price, 0, 1e24);
  if (rawPrice === undefined) return undefined;
  const price = rawPrice;
  const occurredAt = timestamp(value.occurred_at);
  const observedAt = timestamp(value.observed_at);
  const ingestedAt = timestamp(value.ingested_at);
  const provider = boundedString(value.provider, 128);
  const sourceId = boundedString(value.source_id, 256);
  const parserVersion = boundedString(value.parser_version, 128);
  const qualityState = optionalQuality(value.quality_state);
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  if (
    (price !== null && price <= 0) || occurredAt === null ||
    observedAt === null || ingestedAt === null || provider === null || sourceId === null ||
    parserVersion === null || qualityState === null || qualityState === undefined ||
    evidenceRefs === null || Date.parse(occurredAt) > Date.parse(observedAt) ||
    Date.parse(observedAt) > Date.parse(ingestedAt)
  ) {
    return undefined;
  }
  return {
    price,
    occurredAt,
    observedAt,
    ingestedAt,
    provider,
    sourceId,
    parserVersion,
    qualityState,
    evidenceRefs
  };
}

function parsePositionPerformance(value: unknown): PositionPerformanceRecord | null {
  if (!isRecord(value)) return null;
  const asOf = timestamp(value.as_of);
  const qualityState = optionalQuality(value.quality_state);
  const realizedPnl = finiteNumber(value.realized_pnl, -1e24, 1e24);
  const mfe = finiteNumber(value.mfe, -1e24, 1e24);
  const mae = finiteNumber(value.mae, -1e24, 1e24);
  const highWatermark = finiteNumber(value.high_watermark, 0, 1e24);
  const currentValue = parseOptionalPositionNumber(value.current_value, 0, 1e24);
  const unrealizedPnl = parseOptionalPositionNumber(value.unrealized_pnl, -1e24, 1e24);
  const totalPnl = parseOptionalPositionNumber(value.total_pnl, -1e24, 1e24);
  const returnRatio = parseOptionalPositionNumber(value.return_ratio, -1e12, 1e12);
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  if (
    asOf === null || qualityState === null || qualityState === undefined ||
    realizedPnl === null || mfe === null || mae === null || highWatermark === null ||
    currentValue === undefined || unrealizedPnl === undefined || totalPnl === undefined ||
    returnRatio === undefined || evidenceRefs === null
  ) {
    return null;
  }
  return {
    asOf,
    qualityState,
    realizedPnl,
    mfe,
    mae,
    highWatermark,
    currentValue,
    unrealizedPnl,
    totalPnl,
    returnRatio,
    evidenceRefs
  };
}

function parsePositionExitRisk(value: unknown): PositionExitRiskRecord | null | undefined {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return undefined;
  const evaluationId = uuid(value.evaluation_id);
  const evaluatedAt = timestamp(value.evaluated_at);
  const action = boundedString(value.action, 16);
  const exitFraction = finiteNumber(value.exit_fraction, 0, 1);
  const score = finiteNumber(value.score, 0, 100);
  const confidence = finiteNumber(value.confidence, 0, 1);
  const qualityState = optionalQuality(value.quality_state);
  const triggeredRules = stringArray(value.triggered_rules, 128);
  const reasonCodes = stringArray(value.reason_codes, 128);
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  const policyVersion = boundedString(value.policy_version, 128);
  const configHash = boundedString(value.config_hash, 128);
  if (
    evaluationId === null || evaluatedAt === null || action === null || exitFraction === null ||
    score === null || confidence === null || qualityState === null || qualityState === undefined ||
    triggeredRules === null || reasonCodes === null || evidenceRefs === null ||
    policyVersion === null || configHash === null
  ) {
    return undefined;
  }
  return {
    evaluationId,
    evaluatedAt,
    action,
    exitFraction,
    score,
    confidence,
    qualityState,
    triggeredRules,
    reasonCodes,
    evidenceRefs,
    policyVersion,
    configHash
  };
}

function parseClosedTrade(value: unknown): ClosedTradeExplanationRecord | null | undefined {
  if (value === null || value === undefined) return null;
  if (!isRecord(value)) return undefined;
  const evaluationId = value.evaluation_id === null || value.evaluation_id === undefined
    ? null
    : uuid(value.evaluation_id);
  const closedAt = timestamp(value.closed_at);
  const averageExit = finiteNumber(value.average_exit, 0, 1e24);
  const realizedPnl = finiteNumber(value.realized_pnl, -1e24, 1e24);
  const action = boundedString(value.action, 16);
  const reasonCodes = stringArray(value.reason_codes, 128);
  const evidenceRefs = stringArray(value.evidence_refs, 256);
  const beforeEvidenceRefs = stringArray(value.before_evidence_refs, 256);
  const afterEvidenceRefs = stringArray(value.after_evidence_refs, 256);
  const policyVersion = nullableString(value.policy_version, 128);
  const configHash = nullableString(value.config_hash, 128);
  if (
    (value.evaluation_id !== null && value.evaluation_id !== undefined && evaluationId === null) ||
    closedAt === null || averageExit === null || averageExit <= 0 || realizedPnl === null ||
    action === null || reasonCodes === null || reasonCodes.length === 0 || evidenceRefs === null ||
    evidenceRefs.length === 0 || beforeEvidenceRefs === null || afterEvidenceRefs === null ||
    policyVersion === undefined || configHash === undefined
  ) {
    return undefined;
  }
  return {
    evaluationId,
    closedAt,
    averageExit,
    realizedPnl,
    action,
    reasonCodes,
    evidenceRefs,
    beforeEvidenceRefs,
    afterEvidenceRefs,
    policyVersion,
    configHash
  };
}

function parsePosition(value: unknown): PositionRecord | null {
  if (!isRecord(value)) return null;
  const id = uuid(value.id);
  const portfolioId = uuid(value.portfolio_id);
  const tokenId = uuid(value.token_id);
  const mintAddress = boundedString(value.mint_address, 128);
  const symbol = nullableString(value.symbol, 64);
  const name = nullableString(value.name, 256);
  const mode = boundedString(value.mode, 16);
  const state = boundedString(value.state, 24);
  const quantity = finiteNumber(value.quantity, 0, 1e24);
  const averageEntry = finiteNumber(value.average_entry, 0, 1e24);
  const openedAt = value.opened_at === null || value.opened_at === undefined
    ? null
    : timestamp(value.opened_at);
  const closedAt = value.closed_at === null || value.closed_at === undefined
    ? null
    : timestamp(value.closed_at);
  const averageExit = parseOptionalPositionNumber(value.average_exit, 0, 1e24);
  const realizedPnl = finiteNumber(value.realized_pnl, -1e24, 1e24);
  const highWatermark = finiteNumber(value.high_watermark, 0, 1e24);
  const mfe = finiteNumber(value.mfe, -1e24, 1e24);
  const mae = finiteNumber(value.mae, -1e24, 1e24);
  const currentMark = parsePositionMark(value.current_mark);
  const performance = parsePositionPerformance(value.performance);
  const exitRisk = parsePositionExitRisk(value.exit_risk);
  const closedTrade = parseClosedTrade(value.closed_trade);
  const latestActivityAt = value.latest_activity_at === null || value.latest_activity_at === undefined
    ? null
    : timestamp(value.latest_activity_at);
  if (
    id === null || portfolioId === null || tokenId === null || mintAddress === null ||
    mode === null || !POSITION_MODES.has(mode as PositionMode) || state === null ||
    !POSITION_STATES.has(state as PositionState) || quantity === null || averageEntry === null ||
    averageEntry <= 0 || openedAt === undefined || closedAt === undefined ||
    averageExit === undefined || (averageExit !== null && averageExit <= 0) || realizedPnl === null ||
    highWatermark === null || mfe === null || mae === null || currentMark === undefined ||
    performance === null || exitRisk === undefined || closedTrade === undefined ||
    latestActivityAt === undefined || value.execution_eligible === true
  ) {
    return null;
  }
  return {
    id,
    portfolioId,
    tokenId,
    mintAddress,
    symbol,
    name,
    mode: mode as PositionMode,
    state: state as PositionState,
    quantity,
    averageEntry,
    openedAt,
    closedAt,
    averageExit,
    realizedPnl,
    highWatermark,
    mfe,
    mae,
    currentMark,
    performance,
    exitRisk,
    closedTrade,
    latestActivityAt
  };
}

function parseControlState(value: unknown): ControlStateRecord | null {
  if (!isRecord(value)) return null;
  const apiVersion = boundedString(value.api_version, 64);
  const analysisPaused = value.analysis_paused;
  const executionKillSwitch = value.execution_kill_switch;
  const version = integer(value.version, 0, 1_000_000);
  const updatedAt = timestamp(value.updated_at);
  const updatedBy = boundedString(value.updated_by, 256);
  const correlationId = boundedString(value.correlation_id, 128);
  const modes = value.protected_modes;
  if (!isRecord(modes)) return null;
  const protectedModes = {
    analysisOnly: modes.analysis_only,
    paperTrading: modes.paper_trading,
    manualExecution: modes.manual_execution,
    autoExecution: modes.auto_execution
  };
  if (
    apiVersion === null || typeof analysisPaused !== "boolean" ||
    typeof executionKillSwitch !== "boolean" || version === null || updatedAt === null ||
    updatedBy === null || correlationId === null ||
    Object.values(protectedModes).some((mode) => typeof mode !== "boolean") ||
    protectedModes.analysisOnly !== true || protectedModes.paperTrading !== true ||
    protectedModes.manualExecution !== false || protectedModes.autoExecution !== false
  ) {
    return null;
  }
  return {
    apiVersion,
    analysisPaused,
    executionKillSwitch,
    version,
    updatedAt,
    updatedBy,
    correlationId,
    protectedModes: protectedModes as ProtectedModesRecord
  };
}

function parseControlConfig(value: unknown): ControlConfigRecord | null {
  if (!isRecord(value)) return null;
  const apiVersion = boundedString(value.api_version, 64);
  const id = uuid(value.id);
  const version = boundedString(value.version, 64);
  const createdAt = timestamp(value.created_at);
  const actor = boundedString(value.actor, 256);
  const configHash = boundedString(value.config_hash, 128);
  const decisionAffecting = value.decision_affecting;
  const config = safePayload(value.config ?? {});
  if (
    apiVersion === null || id === null || version === null || createdAt === null ||
    actor === null || configHash === null || typeof decisionAffecting !== "boolean" ||
    config === null
  ) {
    return null;
  }
  return { apiVersion, id, version, createdAt, actor, configHash, decisionAffecting, config };
}

function parsePage<T>(value: unknown, parseItem: (item: unknown) => T | null): ReadPage<T> | null {
  if (!isRecord(value) || !Array.isArray(value.items) || value.items.length > MAX_PAGE_LIMIT) {
    return null;
  }
  const limit = finiteNumber(value.limit, 1, MAX_PAGE_LIMIT);
  const hasMore = value.has_more;
  const nextCursor = value.next_cursor;
  const items = value.items.map(parseItem);
  if (
    limit === null || !Number.isInteger(limit) || typeof hasMore !== "boolean" ||
    !(nextCursor === null || nextCursor === undefined || boundedString(nextCursor, 1024)) ||
    items.some((item): item is null => item === null)
  ) {
    return null;
  }
  const cursor = nextCursor === undefined ? null : (nextCursor as string | null);
  if (hasMore !== (cursor !== null)) return null;
  return { items: items as T[], limit, hasMore, nextCursor: cursor };
}

function parseBaseUrl(): URL | null {
  const configured = process.env.MEMERADAR_API_BASE_URL?.trim() || process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configured) return null;
  try {
    const base = new URL(configured);
    if ((base.protocol !== "http:" && base.protocol !== "https:") || base.username || base.password) {
      return null;
    }
    return base;
  } catch {
    return null;
  }
}

function endpoint(path: string, query?: URLSearchParams): string | null {
  const base = parseBaseUrl();
  if (!base) return null;
  const url = new URL(path, base);
  if (query) url.search = query.toString();
  return url.toString();
}

function failureForStatus(status: number): ReadFailureReason {
  if (status === 401 || status === 403) return "UNAUTHORIZED";
  if (status >= 500 || status === 408 || status === 429) return "UNAVAILABLE";
  return "INVALID_RESPONSE";
}

async function request<T>(url: string, parse: (value: unknown) => T | null): Promise<ReadResult<T>> {
  const viewerToken = process.env.MEMERADAR_VIEWER_API_TOKEN?.trim();
  const headers = viewerToken ? { Authorization: `Bearer ${viewerToken}` } : undefined;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, { cache: "no-store", headers, signal: controller.signal });
    if (!response.ok) {
      const reason = failureForStatus(response.status);
      return { ok: false, reason, status: response.status };
    }
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      return { ok: false, reason: "INVALID_RESPONSE" };
    }
    const parsed = parse(body);
    return parsed === null ? { ok: false, reason: "INVALID_RESPONSE" } : { ok: true, data: parsed };
  } catch {
    return { ok: false, reason: "UNAVAILABLE" };
  } finally {
    clearTimeout(timeout);
  }
}

function configuredFailure<T>(): ReadResult<T> {
  return { ok: false, reason: "NOT_CONFIGURED" };
}

function singleQuery(): URLSearchParams {
  const query = new URLSearchParams();
  query.set("limit", String(DEFAULT_LIMIT));
  return query;
}

export function parseRadarFilters(
  input: Record<string, string | string[] | undefined>
): RadarFilters {
  const result: RadarFilters = {};
  const state = input.state;
  if (typeof state === "string" && CANDIDATE_STATES.has(state)) result.state = state;
  const risk = input.risk_disposition;
  if (typeof risk === "string" && RISK_DISPOSITIONS.has(risk as RiskDisposition)) {
    result.riskDisposition = risk as RiskDisposition;
  }
  const minScore = input.min_score;
  if (typeof minScore === "string") {
    const parsed = finiteNumber(minScore, 0, 100);
    if (parsed !== null) result.minScore = parsed;
  }
  return result;
}

export async function fetchCandidates(
  filters: RadarFilters
): Promise<ReadResult<ReadPage<CandidateRecord>>> {
  const query = singleQuery();
  if (filters.state && CANDIDATE_STATES.has(filters.state)) query.set("state", filters.state);
  if (filters.minScore !== undefined && finiteNumber(filters.minScore, 0, 100) !== null) {
    query.set("min_score", String(filters.minScore));
  }
  if (filters.riskDisposition && RISK_DISPOSITIONS.has(filters.riskDisposition)) {
    query.set("risk_disposition", filters.riskDisposition);
  }
  const url = endpoint("/v1/candidates", query);
  return url === null ? configuredFailure() : request(url, (value) => parsePage(value, parseCandidate));
}

export async function fetchEarlyRadar(): Promise<ReadResult<ReadPage<EarlyRadarRecord>>> {
  const url = endpoint("/v1/early-radar", singleQuery());
  return url === null ? configuredFailure() : request(url, (value) => parsePage(value, parseEarlyRadar));
}

export function isValidTokenId(tokenId: string): boolean {
  return UUID_PATTERN.test(tokenId);
}

export async function fetchToken(tokenId: string): Promise<ReadResult<TokenRecord>> {
  if (!isValidTokenId(tokenId)) return { ok: false, reason: "INVALID_RESPONSE" };
  const url = endpoint(`/v1/tokens/${tokenId}`);
  return url === null ? configuredFailure() : request(url, parseToken);
}

export async function fetchTimeline(
  tokenId: string
): Promise<ReadResult<ReadPage<TimelineRecord>>> {
  if (!isValidTokenId(tokenId)) return { ok: false, reason: "INVALID_RESPONSE" };
  const url = endpoint(`/v1/tokens/${tokenId}/timeline`, singleQuery());
  return url === null ? configuredFailure() : request(url, (value) => parsePage(value, parseTimeline));
}

export async function fetchPositions(
  filters: PositionFilters = {}
): Promise<ReadResult<ReadPage<PositionRecord>>> {
  const query = singleQuery();
  if (filters.portfolioId && UUID_PATTERN.test(filters.portfolioId)) {
    query.set("portfolio_id", filters.portfolioId);
  }
  if (filters.mode && POSITION_MODES.has(filters.mode)) query.set("mode", filters.mode);
  if (filters.state && POSITION_STATES.has(filters.state)) query.set("state", filters.state);
  if (filters.asOf && timestamp(filters.asOf) !== null) query.set("as_of", filters.asOf);
  const url = endpoint("/v1/positions", query);
  return url === null ? configuredFailure() : request(url, (value) => parsePage(value, parsePosition));
}

export async function fetchPosition(
  positionId: string
): Promise<ReadResult<PositionRecord>> {
  if (!isValidTokenId(positionId)) return { ok: false, reason: "INVALID_RESPONSE" };
  const url = endpoint(`/v1/positions/${positionId}`);
  return url === null ? configuredFailure() : request(url, parsePosition);
}

function setBoundedNumber(
  query: URLSearchParams,
  name: string,
  value: number | undefined,
  minimum: number,
  maximum: number
): void {
  if (value === undefined) return;
  const parsed = finiteNumber(value, minimum, maximum);
  if (parsed !== null) query.set(name, String(value));
}

function setBoundedText(query: URLSearchParams, name: string, value: string | undefined): void {
  if (value === undefined) return;
  const parsed = boundedString(value, 256);
  if (parsed !== null) query.set(name, parsed);
}

export function isValidWalletAddress(address: string): boolean {
  return typeof address === "string" && SOLANA_ADDRESS_PATTERN.test(address);
}

export async function fetchWallets(
  filters: WalletFilters = {}
): Promise<ReadResult<ReadPage<WalletRecord>>> {
  const query = singleQuery();
  if (filters.tier && WALLET_TIERS.has(filters.tier)) {
    query.set("tier", filters.tier);
  }
  setBoundedNumber(query, "min_score", filters.minScore, 0, 100);
  setBoundedNumber(query, "min_confidence", filters.minConfidence, 0, 1);
  if (filters.qualityState && QUALITY_STATES.has(filters.qualityState)) {
    query.set("quality_state", filters.qualityState);
  }
  const url = endpoint("/v1/wallets", query);
  return url === null ? configuredFailure() : request(url, (value) => parsePage(value, parseWallet));
}

export async function fetchWallet(address: string): Promise<ReadResult<WalletRecord | null>> {
  if (!isValidWalletAddress(address)) return { ok: false, reason: "INVALID_RESPONSE" };
  const url = endpoint(`/v1/wallets/${address}`);
  return url === null ? configuredFailure() : request(url, parseWalletNullable);
}

function parseWalletNullable(value: unknown): WalletRecord | null {
  if (value === null) return null;
  return parseWallet(value);
}

export async function fetchProviderHealth(
  filters: ProviderHealthFilters = {}
): Promise<ReadResult<ReadPage<ProviderHealthRecord>>> {
  const query = singleQuery();
  setBoundedText(query, "provider", filters.provider);
  setBoundedText(query, "capability", filters.capability);
  if (filters.state && PROVIDER_HEALTH_STATES.has(filters.state)) query.set("state", filters.state);
  const url = endpoint("/v1/providers/health", query);
  return url === null
    ? configuredFailure()
    : request(url, (value) => parsePage(value, parseProviderHealth));
}

export async function fetchOperations(): Promise<ReadResult<OperationsRecord>> {
  const url = endpoint("/v1/operations/overview");
  return url === null ? configuredFailure() : request(url, parseOperations);
}

export async function fetchAuditEvents(
  filters: AuditFilters = {}
): Promise<ReadResult<ReadPage<AuditEventRecord>>> {
  const query = singleQuery();
  setBoundedText(query, "actor", filters.actor);
  setBoundedText(query, "action", filters.action);
  setBoundedText(query, "target", filters.target);
  const url = endpoint("/v1/audit/events", query);
  return url === null
    ? configuredFailure()
    : request(url, (value) => parsePage(value, parseAuditEvent));
}

export async function fetchConfigVersions(
  filters: ConfigFilters = {}
): Promise<ReadResult<ReadPage<ConfigVersionRecord>>> {
  const query = singleQuery();
  if (filters.decisionAffecting !== undefined) {
    query.set("decision_affecting", String(filters.decisionAffecting));
  }
  const url = endpoint("/v1/config/versions", query);
  return url === null
    ? configuredFailure()
    : request(url, (value) => parsePage(value, parseConfigVersion));
}

export async function fetchControlState(): Promise<ReadResult<ControlStateRecord>> {
  const url = endpoint("/v1/control/state");
  return url === null ? configuredFailure() : request(url, parseControlState);
}

export async function fetchControlConfig(): Promise<ReadResult<ControlConfigRecord>> {
  const url = endpoint("/v1/control/config");
  return url === null ? configuredFailure() : request(url, parseControlConfig);
}

export interface CreatorReputationRecord {
  address: string;
  asOf?: string;
  launchesTotal: number;
  winnerRate: number;
  severeFailureRate: number;
  rugRate: number;
  score: number;
  confidence: number;
  reputationClass: string;
  reasonCodes: string[];
  sufficientOutcomeSamples?: boolean;
  strongWinnerRate?: number;
  medianMfe?: number | null;
  medianMae?: number | null;
  creatorRealizedPnl?: number | null;
  creatorDumpRate?: number | null;
  creatorExitBeforeMajorDrawdownRate?: number | null;
  bundleSniperAssociation?: boolean | null;
  sharedFunderRecurrence?: boolean | null;
  sideWalletRecurrence?: boolean | null;
  liquiditySurvivalRate?: number | null;
  creatorProfitPublicLossRate?: number | null;
  creatorProfitRugRate?: number | null;
  clusterReputationScore?: number | null;
  configHash?: string;
}

export async function fetchCreatorReputation(
  address: string,
  asOf?: string
): Promise<ReadResult<CreatorReputationRecord>> {
  if (!isValidWalletAddress(address)) {
    return { ok: false, reason: "INVALID_RESPONSE" };
  }
  const query = singleQuery();
  if (asOf) setBoundedText(query, "as_of", asOf);
  const url = endpoint(`/v1/creator-reputation/${encodeURIComponent(address)}`, query);
  return url === null
    ? configuredFailure()
    : request(url, (val) => {
        if (typeof val !== "object" || val === null) throw new Error("invalid payload");
        const obj = val as Record<string, unknown>;
        return {
          address: String(obj.address ?? address),
          asOf: obj.as_of ? String(obj.as_of) : undefined,
          launchesTotal: Number(obj.launches_total ?? 0),
          winnerRate: Number(obj.winner_rate ?? 0),
          severeFailureRate: Number(obj.severe_failure_rate ?? 0),
          rugRate: Number(obj.rug_rate ?? 0),
          score: Number(obj.score ?? 50),
          confidence: Number(obj.confidence ?? 0),
          reputationClass: String(obj.reputation_class ?? "UNPROVEN"),
          reasonCodes: Array.isArray(obj.reason_codes) ? obj.reason_codes.map(String) : [],
          sufficientOutcomeSamples: Boolean(obj.sufficient_outcome_samples ?? false),
          strongWinnerRate: Number(obj.strong_winner_rate ?? 0),
          medianMfe: obj.median_mfe != null ? Number(obj.median_mfe) : null,
          medianMae: obj.median_mae != null ? Number(obj.median_mae) : null,
          creatorRealizedPnl: obj.creator_realized_pnl != null ? Number(obj.creator_realized_pnl) : null,
          creatorDumpRate: obj.creator_dump_rate != null ? Number(obj.creator_dump_rate) : null,
          creatorExitBeforeMajorDrawdownRate: obj.creator_exit_before_major_drawdown_rate != null ? Number(obj.creator_exit_before_major_drawdown_rate) : null,
          bundleSniperAssociation: obj.bundle_sniper_association != null ? Boolean(obj.bundle_sniper_association) : null,
          sharedFunderRecurrence: obj.shared_funder_recurrence != null ? Boolean(obj.shared_funder_recurrence) : null,
          sideWalletRecurrence: obj.side_wallet_recurrence != null ? Boolean(obj.side_wallet_recurrence) : null,
          liquiditySurvivalRate: obj.liquidity_survival_rate != null ? Number(obj.liquidity_survival_rate) : null,
          creatorProfitPublicLossRate: obj.creator_profit_public_loss_rate != null ? Number(obj.creator_profit_public_loss_rate) : null,
          creatorProfitRugRate: obj.creator_profit_rug_rate != null ? Number(obj.creator_profit_rug_rate) : null,
          clusterReputationScore: obj.cluster_reputation_score != null ? Number(obj.cluster_reputation_score) : null,
          configHash: obj.config_hash ? String(obj.config_hash) : "creator-rep-v1-hash",
        };
      });
}

export interface GraphNodeRecord {
  id: string;
  kind: string;
  label: string;
  properties: Record<string, unknown>;
  qualityState: string;
  createdAt: string;
}

export interface GraphEdgeRecord {
  id: string;
  fromId: string;
  toId: string;
  kind: string;
  occurredAt: string;
  observedAt: string;
  ingestedAt: string;
  tokenMint: string | null;
  properties: Record<string, unknown>;
  qualityState: string;
  reasonCodes: string[];
}

export interface WalletGraphRecord {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
  maxDepth: number;
  maxNodes: number;
  maxEdges: number;
  hasMore: boolean;
  asOf: string;
}

export interface ShortestPathRecord {
  nodes: string[];
  edges: Record<string, unknown>[];
}

function parseGraphNode(val: unknown): GraphNodeRecord | null {
  if (typeof val !== "object" || val === null) return null;
  const obj = val as Record<string, unknown>;
  return {
    id: String(obj.id ?? ""),
    kind: String(obj.kind ?? ""),
    label: String(obj.label ?? obj.id ?? ""),
    properties: (typeof obj.properties === "object" && obj.properties !== null) ? (obj.properties as Record<string, unknown>) : {},
    qualityState: String(obj.quality_state ?? "FRESH"),
    createdAt: String(obj.created_at ?? ""),
  };
}

function parseGraphEdge(val: unknown): GraphEdgeRecord | null {
  if (typeof val !== "object" || val === null) return null;
  const obj = val as Record<string, unknown>;
  return {
    id: String(obj.id ?? ""),
    fromId: String(obj.from_id ?? ""),
    toId: String(obj.to_id ?? ""),
    kind: String(obj.kind ?? ""),
    occurredAt: String(obj.occurred_at ?? ""),
    observedAt: String(obj.observed_at ?? ""),
    ingestedAt: String(obj.ingested_at ?? ""),
    tokenMint: obj.token_mint !== null && obj.token_mint !== undefined ? String(obj.token_mint) : null,
    properties: (typeof obj.properties === "object" && obj.properties !== null) ? (obj.properties as Record<string, unknown>) : {},
    qualityState: String(obj.quality_state ?? "FRESH"),
    reasonCodes: Array.isArray(obj.reason_codes) ? obj.reason_codes.map(String) : [],
  };
}

function parseWalletGraph(val: unknown): WalletGraphRecord {
  if (typeof val !== "object" || val === null) throw new Error("invalid graph payload");
  const obj = val as Record<string, unknown>;
  const nodes = Array.isArray(obj.nodes) ? obj.nodes.map(parseGraphNode).filter((n): n is GraphNodeRecord => n !== null) : [];
  const edges = Array.isArray(obj.edges) ? obj.edges.map(parseGraphEdge).filter((e): e is GraphEdgeRecord => e !== null) : [];
  return {
    nodes,
    edges,
    maxDepth: Number(obj.max_depth ?? 2),
    maxNodes: Number(obj.max_nodes ?? 50),
    maxEdges: Number(obj.max_edges ?? 100),
    hasMore: Boolean(obj.has_more ?? false),
    asOf: String(obj.as_of ?? ""),
  };
}

export interface GraphFilters {
  maxDepth?: number;
  maxNodes?: number;
  maxEdges?: number;
  outcomeFilter?: string;
  dateFrom?: string;
  dateTo?: string;
  venue?: string;
  walletRole?: string;
  riskOutcomeClass?: string;
  evidenceQuality?: string;
}

export async function fetchWalletGraph(
  address: string,
  filters: GraphFilters = {}
): Promise<ReadResult<WalletGraphRecord>> {
  if (!isValidWalletAddress(address)) return { ok: false, reason: "INVALID_RESPONSE" };
  const query = singleQuery();
  if (filters.maxDepth) setBoundedNumber(query, "max_depth", filters.maxDepth, 1, 5);
  if (filters.maxNodes) setBoundedNumber(query, "max_nodes", filters.maxNodes, 1, 200);
  if (filters.maxEdges) setBoundedNumber(query, "max_edges", filters.maxEdges, 1, 500);
  if (filters.outcomeFilter) setBoundedText(query, "outcome_filter", filters.outcomeFilter);
  if (filters.dateFrom) setBoundedText(query, "date_from", filters.dateFrom);
  if (filters.dateTo) setBoundedText(query, "date_to", filters.dateTo);
  if (filters.venue) setBoundedText(query, "venue", filters.venue);
  if (filters.walletRole) setBoundedText(query, "wallet_role", filters.walletRole);
  if (filters.riskOutcomeClass) setBoundedText(query, "risk_outcome_class", filters.riskOutcomeClass);
  if (filters.evidenceQuality) setBoundedText(query, "evidence_quality", filters.evidenceQuality);
  const url = endpoint(`/v1/wallet-graph/wallets/${encodeURIComponent(address)}`, query);
  return url === null ? configuredFailure() : request(url, parseWalletGraph);
}

export async function fetchTokenGraph(
  mint: string,
  filters: GraphFilters = {}
): Promise<ReadResult<WalletGraphRecord>> {
  if (!isValidWalletAddress(mint)) return { ok: false, reason: "INVALID_RESPONSE" };
  const query = singleQuery();
  if (filters.maxDepth) setBoundedNumber(query, "max_depth", filters.maxDepth, 1, 5);
  if (filters.maxNodes) setBoundedNumber(query, "max_nodes", filters.maxNodes, 1, 200);
  if (filters.maxEdges) setBoundedNumber(query, "max_edges", filters.maxEdges, 1, 500);
  if (filters.outcomeFilter) setBoundedText(query, "outcome_filter", filters.outcomeFilter);
  if (filters.dateFrom) setBoundedText(query, "date_from", filters.dateFrom);
  if (filters.dateTo) setBoundedText(query, "date_to", filters.dateTo);
  if (filters.venue) setBoundedText(query, "venue", filters.venue);
  if (filters.walletRole) setBoundedText(query, "wallet_role", filters.walletRole);
  if (filters.riskOutcomeClass) setBoundedText(query, "risk_outcome_class", filters.riskOutcomeClass);
  if (filters.evidenceQuality) setBoundedText(query, "evidence_quality", filters.evidenceQuality);
  const url = endpoint(`/v1/wallet-graph/tokens/${encodeURIComponent(mint)}`, query);
  return url === null ? configuredFailure() : request(url, parseWalletGraph);
}

export async function fetchClusterGraph(
  clusterId: string,
  filters: GraphFilters = {}
): Promise<ReadResult<WalletGraphRecord>> {
  const query = singleQuery();
  if (filters.maxDepth) setBoundedNumber(query, "max_depth", filters.maxDepth, 1, 5);
  if (filters.maxNodes) setBoundedNumber(query, "max_nodes", filters.maxNodes, 1, 200);
  if (filters.maxEdges) setBoundedNumber(query, "max_edges", filters.maxEdges, 1, 500);
  if (filters.dateFrom) setBoundedText(query, "date_from", filters.dateFrom);
  if (filters.dateTo) setBoundedText(query, "date_to", filters.dateTo);
  if (filters.venue) setBoundedText(query, "venue", filters.venue);
  if (filters.walletRole) setBoundedText(query, "wallet_role", filters.walletRole);
  if (filters.riskOutcomeClass) setBoundedText(query, "risk_outcome_class", filters.riskOutcomeClass);
  if (filters.evidenceQuality) setBoundedText(query, "evidence_quality", filters.evidenceQuality);
  const url = endpoint(`/v1/wallet-graph/clusters/${encodeURIComponent(clusterId)}`, query);
  return url === null ? configuredFailure() : request(url, parseWalletGraph);
}

export async function fetchShortestPath(
  startId: string,
  targetId: string,
  maxDepth = 5
): Promise<ReadResult<ShortestPathRecord>> {
  const query = singleQuery();
  setBoundedText(query, "start_id", startId);
  setBoundedText(query, "target_id", targetId);
  setBoundedNumber(query, "max_depth", maxDepth, 1, 10);
  const url = endpoint("/v1/wallet-graph/shortest-path", query);
  return url === null
    ? configuredFailure()
    : request(url, (val) => {
        if (typeof val !== "object" || val === null) throw new Error("invalid payload");
        const obj = val as Record<string, unknown>;
        return {
          nodes: Array.isArray(obj.nodes) ? obj.nodes.map(String) : [],
          edges: Array.isArray(obj.edges) ? (obj.edges as Record<string, unknown>[]) : [],
        };
      });
}
