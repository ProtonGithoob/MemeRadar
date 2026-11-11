"""Opt-in, durable paper-entry and exit workers; no live execution exists here."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncEngine

from memeradar_application.config import PaperAutoPolicy, Settings
from memeradar_application.event_processing import EventDispatcher, OutboxProcessor, OutboxWorker
from memeradar_application.exit_engine import (
    ExitAction,
    ExitEngine,
    ExitEvaluation,
    ExitEvaluationStore,
    ExitEvidenceSnapshot,
    ExitRulePolicy,
    ExitTakeProfitLevel,
)
from memeradar_application.paper_execution import (
    ChainFeeReservePolicy,
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperExecutionResult,
    PaperLedgerStore,
    PaperOrderRequest,
    PaperSizingPolicy,
)
from memeradar_application.provider_contracts import (
    ProviderRequestContext,
    QuoteAmountUnit,
    QuotePort,
    QuoteRequest,
    QuoteSnapshot,
    decimal_to_base_units,
)
from memeradar_application.shadow_entry import (
    ShadowEntryPolicy,
    ShadowEntryResult,
    ShadowEntryService,
)
from memeradar_domain import (
    Candidate,
    Chain,
    EventEnvelope,
    Observation,
    PaperOrderSide,
    PaperOrderState,
    Position,
    PositionMode,
    PositionState,
    PriceSemantics,
    Provenance,
    QualityState,
    normalize_chain,
)
from memeradar_domain.common import ensure_utc, to_decimal
from memeradar_persistence import (
    SqlAlchemyExitEvaluationStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyPaperLedgerStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.composition import ProviderBundle, build_provider_bundle

LOGGER = logging.getLogger(__name__)
SOLANA_WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"


def build_paper_execution_policy(policy: PaperAutoPolicy) -> PaperExecutionPolicy:
    """Map validated operator policy onto existing ledger controls."""

    return PaperExecutionPolicy(
        sizing=PaperSizingPolicy(
            max_risk_per_trade=policy.max_risk_fraction,
            max_position_fraction=policy.max_position_fraction,
            max_portfolio_exposure_fraction=policy.max_portfolio_exposure_fraction,
            min_cash_reserve=policy.fee_reserve_sol,
            max_concurrent_positions=policy.max_concurrent_positions,
            min_confidence=Decimal("0"),
            version=policy.version,
        ),
        fee_reserve_policy=ChainFeeReservePolicy(solana=policy.fee_reserve_sol),
        fee_bps=policy.fee_bps,
        slippage_bps=Decimal(policy.max_slippage_bps),
        version=policy.version,
        config_hash=policy.config_hash,
    )


def paper_entry_decision(
    event: EventEnvelope,
    candidate: Candidate,
    policy: PaperAutoPolicy,
) -> Mapping[str, object]:
    """Adapt a persisted lifecycle event to the existing shadow-entry contract."""

    if not isinstance(event, EventEnvelope) or not isinstance(candidate, Candidate):
        raise TypeError("event and candidate must use canonical domain contracts")
    if normalize_chain(candidate.token.chain).value != "solana":
        raise ValueError("PAPER_AUTO worker currently accepts Solana candidates only")
    payload = event.payload
    risk = payload.get("risk_snapshot")
    risk_snapshot = dict(risk) if isinstance(risk, Mapping) else {}
    raw_as_of = risk_snapshot.get("as_of")
    evaluated_at = event.occurred_at
    if isinstance(raw_as_of, str):
        try:
            parsed = datetime.fromisoformat(raw_as_of)
        except ValueError:
            parsed = event.occurred_at
        else:
            evaluated_at = ensure_utc(parsed, "risk_snapshot.as_of")
    return {
        "candidate_id": candidate.id,
        "token_id": candidate.token.id,
        "decision_ref": event.id,
        "chain": "solana",
        "entry_ready": payload.get("to_state") == "ENTRY_READY"
        and payload.get("entry_ready") is True,
        "sellability": payload.get("sellable"),
        "liquidity_ok": payload.get("liquidity_ok"),
        "liquidity_usd": payload.get("liquidity"),
        "confidence": payload.get("confidence"),
        "input_mint": SOLANA_WRAPPED_SOL_MINT,
        "output_mint": candidate.token.mint_address,
        "input_decimals": 9,
        "output_decimals": payload.get("token_decimals"),
        "paper_size_quote": policy.entry_size_sol,
        "portfolio_id": policy.portfolio_id,
        "risk_snapshot": risk_snapshot,
        "evidence_refs": payload.get("evidence_refs", ()),
        "evaluated_at": evaluated_at,
        "analysis_only": True,
        "paper_trading": True,
        "manual_execution": False,
        "auto_execution": False,
    }


def paper_entry_observation(
    event: EventEnvelope,
    candidate: Candidate,
    result: ShadowEntryResult,
    policy: PaperAutoPolicy,
    *,
    observed_at: datetime,
) -> Observation:
    """Persist a restart-stable, queryable account of each material entry result."""

    checked_at = ensure_utc(observed_at, "observed_at")
    paper_result = result.paper_result
    order = None if paper_result is None else paper_result.order
    quote_snapshot = {} if order is None else order.quote_snapshot
    raw_quote_source = quote_snapshot.get("provenance")
    quote_provenance = (
        raw_quote_source if isinstance(raw_quote_source, Mapping) else {}
    )
    quote_source_id = (
        quote_provenance.get("source_id")
        if isinstance(quote_provenance.get("source_id"), str)
        else None
    )
    quote_state = quote_snapshot.get("freshness")
    freshness = quote_state if isinstance(quote_state, Mapping) else {}
    quote_observed_at: str | None = (
        raw_quote_source.get("observed_at")
        if isinstance(raw_quote_source, Mapping)
        and isinstance(raw_quote_source.get("observed_at"), str)
        else None
    )
    if result.quote is not None:
        quote_source_id = result.quote.provenance.source_id
        quote_observed_at = result.quote.provenance.observed_at.isoformat()
        quality = result.quote.freshness.state_at(checked_at)
        source_observed_at = min(result.quote.provenance.observed_at, checked_at)
    elif quote_source_id is not None:
        quality = QualityState(str(freshness.get("quality_state", "UNKNOWN")))
        raw_observed = quote_provenance.get("observed_at")
        source_observed_at = (
            ensure_utc(datetime.fromisoformat(raw_observed), "quote.observed_at")
            if isinstance(raw_observed, str)
            else checked_at
        )
    else:
        quality = QualityState.UNKNOWN
        source_observed_at = checked_at
    state = order.state.value if order is not None else result.status.value
    reasons = (
        tuple(reason.code for reason in order.reason_codes)
        if order is not None
        else result.reason_code_values
    )
    raw_event_refs = event.payload.get("evidence_refs", ())
    event_refs = (
        tuple(value for value in raw_event_refs if isinstance(value, str))
        if isinstance(raw_event_refs, tuple | list)
        else ()
    )
    raw_risk_snapshot = event.payload.get("risk_snapshot")
    raw_risk_refs = (
        raw_risk_snapshot.get("evidence_refs", ())
        if isinstance(raw_risk_snapshot, Mapping)
        else ()
    )
    risk_refs = (
        tuple(value for value in raw_risk_refs if isinstance(value, str))
        if isinstance(raw_risk_refs, tuple | list)
        else ()
    )
    stable_refs = tuple(
        dict.fromkeys(
            (
                *event_refs,
                *risk_refs,
                *((f"quote:{quote_source_id}",) if quote_source_id else ()),
            )
        )
    )
    material = "\0".join(
        (
            str(event.id),
            state,
            ",".join(reasons),
            quote_source_id or "no-quote",
            quote_observed_at or "",
        )
    )
    material_key = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return Observation(
        kind="paper.entry_evaluation",
        provenance=Provenance(
            provider="memeradar-paper-worker",
            source_id=f"paper-entry:{event.id}",
            observed_at=source_observed_at,
            parser_version=policy.version,
        ),
        occurred_at=event.occurred_at,
        observed_at=checked_at,
        ingested_at=checked_at,
        quality_state=quality,
        normalized_payload={
            "decision_id": str(event.id),
            "candidate_id": str(candidate.id),
            "token_id": str(candidate.token.id),
            "status": state,
            "reason_codes": reasons,
            "evidence_refs": stable_refs,
            "quote_source_id": quote_source_id,
            "quote_observed_at": quote_observed_at,
            "paper_order_id": None if order is None else str(order.id),
            "position_id": (
                None
                if paper_result is None or paper_result.position is None
                else str(paper_result.position.id)
            ),
            "policy_version": policy.version,
            "policy_config_hash": policy.config_hash,
            "execution_touched": False,
        },
        id=uuid5(NAMESPACE_URL, "memeradar:paper-entry-evaluation:" + material_key),
        candidate_id=candidate.id,
        token_id=candidate.token.id,
    )


async def process_paper_entry(
    event: EventEnvelope,
    candidate: Candidate,
    policy: PaperAutoPolicy,
    *,
    quote_port: QuotePort,
    shadow_entry: ShadowEntryService,
    paper_engine: PaperExecutionEngine,
    save_observation: Callable[[Observation], Awaitable[object]],
    observed_at: datetime | None = None,
) -> ShadowEntryResult:
    """Run one durable decision using the existing quote, shadow and ledger owners."""

    decision = paper_entry_decision(event, candidate, policy)
    result = await shadow_entry.on_entry_ready(decision, quote_port, paper_engine)
    await save_observation(
        paper_entry_observation(
            event,
            candidate,
            result,
            policy,
            observed_at=observed_at or datetime.now(UTC),
        )
    )
    return result


def build_paper_exit_policy(policy: PaperAutoPolicy) -> ExitRulePolicy:
    """Use the existing deterministic exit rules with the configured paper limits."""

    return ExitRulePolicy(
        stop_loss_bps=policy.stop_loss_bps,
        take_profit_levels=(
            ExitTakeProfitLevel(
                "take-profit",
                policy.take_profit_bps,
                policy.take_profit_fraction,
            ),
        ),
        time_stop=timedelta(seconds=policy.holding_horizon_seconds),
        version=policy.version,
        config_hash=policy.config_hash,
    )


def _exit_quote_is_valid(
    quote: object,
    *,
    input_mint: str,
    output_mint: str,
    input_amount: Decimal,
    raw_input_amount: Decimal,
    input_decimals: int,
    policy: PaperAutoPolicy,
    now: datetime,
) -> bool:
    if not isinstance(quote, QuoteSnapshot):
        return False
    output = quote.human_output_amount
    if quote.minimum_output_amount is None or quote.slippage_bps is None:
        return False
    try:
        quote_output = to_decimal(quote.output_amount, "quote.output_amount")
        minimum_output = to_decimal(quote.minimum_output_amount, "quote.minimum_output_amount")
        slippage = to_decimal(quote.slippage_bps, "quote.slippage_bps")
        price_impact = to_decimal(quote.price_impact_bps, "quote.price_impact_bps")
    except (TypeError, ValueError):
        return False
    age = now - quote.provenance.observed_at
    return not (
        quote.chain is not Chain.SOLANA
        or quote.input_mint != input_mint
        or quote.output_mint != output_mint
        or quote.amount_unit is not QuoteAmountUnit.RAW_BASE_UNITS
        or quote.input_decimals != input_decimals
        or quote.output_decimals != 9
        or quote.input_amount != raw_input_amount
        or quote.human_input_amount != input_amount
        or output is None
        or output <= 0
        or quote.price_semantics is not PriceSemantics.EXECUTION_QUOTE
        or not quote.route
        or minimum_output <= 0
        or minimum_output > quote_output
        or slippage > policy.max_slippage_bps
        or price_impact > policy.max_price_impact_bps
        or not quote.is_fresh_at(now)
        or age < timedelta(0)
        or age > timedelta(seconds=policy.quote_ttl_seconds)
        or quote.freshness.expires_at <= quote.provenance.observed_at
    )


def _paper_exit_quantity(quantity: Decimal, decimals: int) -> Decimal:
    quantum = Decimal(1).scaleb(-decimals)
    with localcontext() as context:
        context.prec = max(context.prec, len(quantity.as_tuple().digits) + decimals + 4)
        return quantity.quantize(quantum, rounding=ROUND_DOWN)


def _evaluate_paper_exit(
    exit_engine: ExitEngine,
    position: Position,
    quote: QuoteSnapshot,
    *,
    now: datetime,
    consumed_take_profit: set[str],
    before_evidence_refs: tuple[str, ...],
) -> ExitEvaluation:
    quote_input = quote.human_input_amount
    quote_output = quote.human_output_amount
    assert quote_input is not None and quote_output is not None
    evidence = ExitEvidenceSnapshot(
        occurred_at=quote.provenance.observed_at,
        observed_at=quote.provenance.observed_at,
        ingested_at=now,
        expires_at=quote.freshness.expires_at,
        current_price=quote_output / quote_input,
        provenance=(quote.provenance,),
        evidence_refs=(f"quote:{quote.provenance.source_id}",),
        quality_state=quote.freshness.state_at(now),
    )
    return exit_engine.evaluate(
        position,
        evidence,
        now=now,
        consumed_take_profit_levels=consumed_take_profit,
        before_evidence_refs=before_evidence_refs,
    )


async def _write_off_if_unexecutable(
    policy: PaperAutoPolicy,
    ledger: PaperLedgerStore,
    position: Position,
    *,
    now: datetime,
) -> Position | None:
    """Book a total loss once the time stop is due and no executable exit exists.

    Without this, a rugged token whose sell route vanished stays OPEN at cost
    basis forever and paper PnL silently excludes the loss.
    """

    if position.opened_at is None:
        return None
    deadline = position.opened_at + timedelta(
        seconds=policy.holding_horizon_seconds + policy.unexecutable_grace_seconds
    )
    if now < deadline:
        return None
    written_off = await ledger.save_position_write_off(position.id, now)
    if written_off is not None:
        LOGGER.warning(
            "paper_position_written_off_unexecutable",
            extra={
                "position_id": str(position.id),
                "token_id": str(position.token_id),
                "realized_pnl": str(written_off.realized_pnl),
                "reason_code": "UNEXECUTABLE_EXIT_WRITE_OFF",
            },
        )
    return written_off


async def process_paper_exits_once(
    policy: PaperAutoPolicy,
    *,
    quote_port: QuotePort,
    paper_engine: PaperExecutionEngine,
    ledger: PaperLedgerStore,
    exit_engine: ExitEngine,
    exit_store: ExitEvaluationStore,
    candidate_lookup: Callable[[UUID], Awaitable[Candidate | None]],
    now: datetime,
) -> tuple[PaperExecutionResult, ...]:
    """Evaluate open positions and sell only against a fresh, exact execution quote."""

    checked_at = ensure_utc(now, "now")
    positions = await ledger.list_positions(policy.portfolio_id)
    orders = await ledger.list_orders(policy.portfolio_id)
    executions: list[PaperExecutionResult] = []
    for position in positions:
        if position.mode is not PositionMode.PAPER or position.state not in {
            PositionState.OPEN,
            PositionState.EXIT_SIGNALLED,
        }:
            continue
        entry_order = next(
            (
                order
                for order in orders
                if order.side is PaperOrderSide.BUY
                and order.decision_ref == position.entry_decision_ref
                and order.state in {PaperOrderState.FILLED, PaperOrderState.PARTIALLY_FILLED}
            ),
            None,
        )
        if entry_order is None or entry_order.candidate_id is None:
            continue
        candidate = await candidate_lookup(entry_order.candidate_id)
        if (
            candidate is None
            or candidate.token.id != position.token_id
            or normalize_chain(candidate.token.chain) is not Chain.SOLANA
        ):
            continue
        entry_quote = entry_order.quote_snapshot
        token_decimals = entry_quote.get("output_decimals")
        if (
            type(token_decimals) is not int
            or not 0 <= token_decimals <= 18
            or entry_quote.get("output_mint") != candidate.token.mint_address
            or entry_quote.get("input_mint") != SOLANA_WRAPPED_SOL_MINT
        ):
            continue

        try:
            amount = position.quantity
            raw_amount = decimal_to_base_units(amount, token_decimals)
            quote_request = QuoteRequest(
                context=ProviderRequestContext(
                    correlation_id=f"paper-exit:{position.id}:{checked_at.isoformat()}",
                    requested_at=checked_at,
                ),
                input_mint=candidate.token.mint_address,
                output_mint=SOLANA_WRAPPED_SOL_MINT,
                amount=raw_amount,
                slippage_bps=policy.max_slippage_bps,
                chain=Chain.SOLANA,
                input_decimals=token_decimals,
                output_decimals=9,
            )
            quote = await quote_port.quote(quote_request)
        except Exception as exc:
            LOGGER.warning(
                "paper_exit_quote_unavailable",
                extra={"position_id": str(position.id), "error_class": type(exc).__name__},
            )
            await _write_off_if_unexecutable(policy, ledger, position, now=checked_at)
            continue

        if not _exit_quote_is_valid(
            quote,
            input_mint=candidate.token.mint_address,
            output_mint=SOLANA_WRAPPED_SOL_MINT,
            input_amount=amount,
            raw_input_amount=raw_amount,
            input_decimals=token_decimals,
            policy=policy,
            now=checked_at,
        ):
            await _write_off_if_unexecutable(policy, ledger, position, now=checked_at)
            continue
        assert isinstance(quote, QuoteSnapshot)

        # Mark the position with the executable exit-quote price so the
        # trailing stop, break-even and MFE/MAE see the running peak rather
        # than the entry price.
        if position.state is PositionState.OPEN:
            quote_input = quote.human_input_amount
            quote_output = quote.human_output_amount
            if quote_input and quote_output and quote_input > 0 and quote_output > 0:
                marked = await ledger.save_position_mark(
                    position.id, quote_output / quote_input
                )
                if marked is not None:
                    position = marked

        evaluations = await exit_store.list(position.id)
        filled_exit_refs = {
            order.decision_ref
            for order in orders
            if order.side is PaperOrderSide.SELL
            and order.state in {PaperOrderState.FILLED, PaperOrderState.PARTIALLY_FILLED}
        }
        consumed_take_profit = {
            rule.removeprefix("TAKE_PROFIT:")
            for evaluation in evaluations
            if evaluation.signal is not None and evaluation.signal.id in filled_exit_refs
            for rule in evaluation.triggered_rules
            if rule.startswith("TAKE_PROFIT:")
        }
        before_evidence_refs = (
            evaluations[-1].after_evidence_refs if evaluations else ()
        )
        evaluation = _evaluate_paper_exit(
            exit_engine,
            position,
            quote,
            now=checked_at,
            consumed_take_profit=consumed_take_profit,
            before_evidence_refs=before_evidence_refs,
        )
        if evaluation.action not in {ExitAction.REDUCE, ExitAction.CLOSE}:
            continue
        assert evaluation.signal is not None
        intent = evaluation.to_paper_exit_intent(position)
        desired_quantity = intent.to_quantity(position.quantity)
        sell_quantity = _paper_exit_quantity(desired_quantity, token_decimals)
        if (
            sell_quantity <= 0
            or sell_quantity > desired_quantity
            or (evaluation.action is ExitAction.CLOSE and sell_quantity != position.quantity)
        ):
            continue
        sell_raw_amount = decimal_to_base_units(sell_quantity, token_decimals)
        if sell_raw_amount != quote_request.amount:
            try:
                quote = await quote_port.quote(
                    QuoteRequest(
                        context=ProviderRequestContext(
                            correlation_id=f"paper-exit:{position.id}:{evaluation.signal.id}",
                            requested_at=checked_at,
                        ),
                        input_mint=candidate.token.mint_address,
                        output_mint=SOLANA_WRAPPED_SOL_MINT,
                        amount=sell_raw_amount,
                        slippage_bps=policy.max_slippage_bps,
                        chain=Chain.SOLANA,
                        input_decimals=token_decimals,
                        output_decimals=9,
                    )
                )
            except Exception as exc:
                LOGGER.warning(
                    "paper_exit_partial_quote_unavailable",
                    extra={"position_id": str(position.id), "error_class": type(exc).__name__},
                )
                continue
            if not _exit_quote_is_valid(
                quote,
                input_mint=candidate.token.mint_address,
                output_mint=SOLANA_WRAPPED_SOL_MINT,
                input_amount=sell_quantity,
                raw_input_amount=sell_raw_amount,
                input_decimals=token_decimals,
                policy=policy,
                now=checked_at,
            ):
                continue
            assert isinstance(quote, QuoteSnapshot)
            evaluation = _evaluate_paper_exit(
                exit_engine,
                position,
                quote,
                now=checked_at,
                consumed_take_profit=consumed_take_profit,
                before_evidence_refs=before_evidence_refs,
            )
            if evaluation.action not in {ExitAction.REDUCE, ExitAction.CLOSE}:
                continue
            assert evaluation.signal is not None
            final_quantity = _paper_exit_quantity(
                evaluation.to_paper_exit_intent(position).to_quantity(position.quantity),
                token_decimals,
            )
            if final_quantity != sell_quantity:
                await exit_store.append(evaluation)
                continue
        assert evaluation.signal is not None
        await exit_store.append(evaluation)
        executions.append(
            await paper_engine.execute(
                PaperOrderRequest(
                    portfolio_id=position.portfolio_id,
                    token_id=position.token_id,
                    side=PaperOrderSide.SELL,
                    amount=sell_quantity,
                    requested_at=checked_at,
                    idempotency_key=f"paper-exit:{position.id}:{evaluation.signal.id}",
                    quote=quote,
                    decision_ref=evaluation.signal.id,
                    risk_snapshot={},
                    candidate_id=entry_order.candidate_id,
                )
            )
        )
        orders = (*orders, executions[-1].order)
    return tuple(executions)


async def _load_candidate(engine: AsyncEngine, candidate_id: UUID) -> Candidate | None:
    async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
        return await unit_of_work.candidates.get(candidate_id)


async def _save_entry_observation(engine: AsyncEngine, observation: Observation) -> None:
    async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
        await unit_of_work.observations.add(observation)
        await unit_of_work.commit()


async def _run_paper_exit_monitor(
    stop_event: asyncio.Event,
    settings: Settings,
    policy: PaperAutoPolicy,
    *,
    quote_port: QuotePort,
    paper_engine: PaperExecutionEngine,
    ledger: SqlAlchemyPaperLedgerStore,
    exit_store: SqlAlchemyExitEvaluationStore,
    database_engine: AsyncEngine,
    sleeper: Callable[[float], Awaitable[None]],
) -> None:
    exit_engine = ExitEngine(build_paper_exit_policy(policy))
    poll_interval = max(30.0, settings.worker_poll_interval_seconds)
    while not stop_event.is_set():
        try:
            await process_paper_exits_once(
                policy,
                quote_port=quote_port,
                paper_engine=paper_engine,
                ledger=ledger,
                exit_engine=exit_engine,
                exit_store=exit_store,
                candidate_lookup=lambda candidate_id: _load_candidate(
                    database_engine,
                    candidate_id,
                ),
                now=datetime.now(UTC),
            )
        except Exception:
            LOGGER.exception("paper_exit_cycle_failed")
        await sleeper(poll_interval)


async def _run_paper_auto(
    stop_event: asyncio.Event,
    settings: Settings,
    *,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Consume only explicitly enabled durable paper decisions."""

    policy = settings.paper_auto_policy
    if policy is None:
        return
    if settings.database_url is None:
        raise RuntimeError("PAPER_AUTO requires a durable database")
    if not settings.analysis_only or not settings.paper_trading:
        raise RuntimeError("PAPER_AUTO requires protected analysis/paper modes")
    if settings.manual_execution or settings.auto_execution:
        raise RuntimeError("PAPER_AUTO cannot start with execution permissions enabled")

    engine = create_database_engine(settings.database_url)
    bundle: ProviderBundle | None = None
    try:
        bundle = build_provider_bundle(settings)
        if bundle.jupiter is None:
            raise RuntimeError("PAPER_AUTO requires the configured Jupiter quote adapter")
        provider_bundle = bundle
        ledger = SqlAlchemyPaperLedgerStore(engine)
        portfolio = await ledger.get_portfolio(policy.portfolio_id)
        if portfolio is None:
            raise RuntimeError("configured PAPER_AUTO portfolio has not been provisioned")
        if (
            portfolio.mode is not PositionMode.PAPER
            or portfolio.currency != "SOL"
            or portfolio.initial_balance != policy.initial_balance_sol
        ):
            raise RuntimeError("configured PAPER_AUTO portfolio does not match its policy")

        paper_engine = PaperExecutionEngine(ledger, build_paper_execution_policy(policy))
        exit_store = SqlAlchemyExitEvaluationStore(engine)
        shadow_entry = ShadowEntryService(
            policy=ShadowEntryPolicy(
                default_paper_size_quote=policy.entry_size_sol,
                slippage_bps=policy.max_slippage_bps,
                max_price_impact_bps=policy.max_price_impact_bps,
                min_liquidity_usd=policy.min_liquidity_usd,
                quote_ttl=timedelta(seconds=policy.quote_ttl_seconds),
                version=policy.version,
                config_hash=policy.config_hash,
            )
        )

        async def handle(event: EventEnvelope) -> None:
            raw_candidate_id = event.payload.get("candidate_id")
            try:
                candidate_id = UUID(str(raw_candidate_id))
            except (TypeError, ValueError) as exc:
                raise ValueError("paper decision has no valid candidate identity") from exc
            candidate = await _load_candidate(engine, candidate_id)
            if candidate is None:
                raise ValueError("paper decision candidate is missing")
            async def save_observation(observation: Observation) -> None:
                await _save_entry_observation(engine, observation)

            result = await process_paper_entry(
                event,
                candidate,
                policy,
                quote_port=provider_bundle.quote,
                shadow_entry=shadow_entry,
                paper_engine=paper_engine,
                save_observation=save_observation,
            )
            LOGGER.info(
                "paper_entry_evaluated",
                extra={
                    "decision_id": str(event.id),
                    "status": result.status.value,
                    "reason_codes": result.reason_code_values,
                },
            )

        processor = OutboxProcessor(
            SqlAlchemyOutboxStore(engine),
            EventDispatcher({"CandidateStateChanged": handle}),
            side_effect_kind="paper_execution",
        )
        await asyncio.gather(
            OutboxWorker(
                processor,
                poll_interval_seconds=settings.worker_poll_interval_seconds,
            ).run(stop_event, sleeper=sleeper),
            _run_paper_exit_monitor(
                stop_event,
                settings,
                policy,
                quote_port=provider_bundle.quote,
                paper_engine=paper_engine,
                ledger=ledger,
                exit_store=exit_store,
                database_engine=engine,
                sleeper=sleeper,
            ),
        )
    finally:
        if bundle is not None:
            await bundle.aclose()
        await engine.dispose()


__all__ = [
    "SOLANA_WRAPPED_SOL_MINT",
    "build_paper_execution_policy",
    "paper_entry_decision",
    "paper_entry_observation",
    "process_paper_entry",
    "build_paper_exit_policy",
    "process_paper_exits_once",
    "_run_paper_exit_monitor",
    "_run_paper_auto",
]
