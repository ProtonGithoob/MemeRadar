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
