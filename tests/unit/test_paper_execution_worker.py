"""Composition and event-contract tests for the opt-in PAPER_AUTO worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

import pytest

from memeradar_application.config import PaperAutoPolicy, Settings
from memeradar_application.exit_engine import ExitAction, ExitEngine, InMemoryExitEvaluationStore
from memeradar_application.paper_execution import (
    InMemoryPaperLedgerStore,
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperOrderState,
)
from memeradar_application.provider_contracts import QuoteAmountUnit, QuoteSnapshot
from memeradar_application.shadow_entry import (
    ShadowEntryPolicy,
    ShadowEntryService,
    ShadowEntryStatus,
)
from memeradar_domain import (
    Candidate,
    EventEnvelope,
    Freshness,
    Position,
    PriceSemantics,
    Provenance,
    TokenIdentity,
)
from memeradar_worker import main as worker_main
from memeradar_worker.paper_execution import (
    build_paper_execution_policy,
    build_paper_exit_policy,
    paper_entry_decision,
    process_paper_entry,
    process_paper_exits_once,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def paper_values() -> dict[str, str]:
    return {
        "DATABASE_URL": "sqlite+aiosqlite:///./paper-worker-fixture.db",
        "ENABLED_CHAINS": "solana",
        "PAPER_QUOTE_PROVIDER": "jupiter",
        "MEMERADAR_PAPER_QUOTE_URL": "https://api.jup.ag/swap/v2",
        "MEMERADAR_PAPER_QUOTE_API_KEY": "fixture-key",
        "PAPER_AUTO_ENABLED": "true",
        "PAPER_AUTO_PORTFOLIO_ID": "11111111-1111-4111-8111-111111111111",
        "PAPER_AUTO_INITIAL_BALANCE_SOL": "100",
        "PAPER_AUTO_ENTRY_SIZE_SOL": "0.1",
        "PAPER_AUTO_MAX_RISK_FRACTION": "0.02",
        "PAPER_AUTO_MAX_POSITION_FRACTION": "0.02",
        "PAPER_AUTO_MAX_EXPOSURE_FRACTION": "0.1",
        "PAPER_AUTO_MAX_POSITIONS": "1",
        "PAPER_AUTO_MIN_LIQUIDITY_USD": "5000",
        "PAPER_AUTO_MAX_PRICE_IMPACT_BPS": "100",
        "PAPER_AUTO_MAX_SLIPPAGE_BPS": "100",
        "PAPER_AUTO_QUOTE_TTL_SECONDS": "30",
        "PAPER_AUTO_FEE_BPS": "30",
        "PAPER_AUTO_FEE_RESERVE_SOL": "0.01",
        "PAPER_AUTO_STOP_LOSS_BPS": "1000",
        "PAPER_AUTO_TAKE_PROFIT_BPS": "2000",
        "PAPER_AUTO_TAKE_PROFIT_FRACTION": "1",
        "PAPER_AUTO_HOLDING_HORIZON_SECONDS": "3600",
        "PAPER_AUTO_POLICY_VERSION": "paper-research-fixture-v1",
    }


def candidate() -> Candidate:
    return Candidate(
        TokenIdentity(mint_address=MINT, chain="solana"),
        NOW,
        "fixture-launch",
        id=UUID("22222222-2222-4222-8222-222222222222"),
    )


def entry_event(candidate_id: UUID) -> EventEnvelope:
    return EventEnvelope(
        kind="CandidateStateChanged",
        aggregate_type="candidate",
        aggregate_id=candidate_id,
        occurred_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        correlation_id="paper-worker-fixture",
        producer="fixture",
        id=UUID("33333333-3333-4333-8333-333333333333"),
        payload={
            "candidate_id": str(candidate_id),
            "to_state": "ENTRY_READY",
            "entry_ready": True,
            "sellable": True,
            "liquidity_ok": True,
            "liquidity": "25000",
            "confidence": "0.9",
            "token_decimals": 6,
            "risk_snapshot": {
                "risk_disposition": "PASS",
                "quality_state": "FRESH",
                "as_of": NOW.isoformat(),
                "expires_at": "2026-11-10T12:05:00+00:00",
            },
        },
    )


def test_paper_policy_uses_transactional_caps_and_a_configuration_fingerprint() -> None:
    policy = Settings.from_env(paper_values()).paper_auto_policy
    assert isinstance(policy, PaperAutoPolicy)

    execution = build_paper_execution_policy(policy)

    assert isinstance(execution, PaperExecutionPolicy)
    assert execution.sizing.max_risk_per_trade == Decimal("0.02")
    assert execution.sizing.max_position_fraction == Decimal("0.02")
    assert execution.sizing.max_portfolio_exposure_fraction == Decimal("0.1")
    assert execution.sizing.max_concurrent_positions == 1
    assert execution.sizing.min_cash_reserve == Decimal("0.01")
    assert execution.fee_bps == Decimal("30")
    assert execution.config_hash == policy.config_hash
    assert policy.config_hash.startswith("sha256:")


def test_entry_event_is_adapted_to_point_in_time_shadow_contract() -> None:
    configured = Settings.from_env(paper_values()).paper_auto_policy
    assert isinstance(configured, PaperAutoPolicy)
    token_candidate = candidate()

    decision = paper_entry_decision(
        entry_event(token_candidate.id),
        token_candidate,
        configured,
    )

    assert decision["entry_ready"] is True
    assert decision["sellability"] is True
    assert decision["liquidity_ok"] is True
    assert decision["input_decimals"] == 9
    assert decision["output_decimals"] == 6
    assert decision["paper_size_quote"] == Decimal("0.1")
    assert decision["risk_snapshot"]["risk_disposition"] == "PASS"
    assert decision["evaluated_at"] == NOW
    assert decision["manual_execution"] is False
    assert decision["auto_execution"] is False


def test_entry_adapter_rejects_non_solana_candidate() -> None:
    configured = Settings.from_env(paper_values()).paper_auto_policy
    assert isinstance(configured, PaperAutoPolicy)
    other_chain = Candidate(
        TokenIdentity(
            mint_address="0x2222222222222222222222222222222222222222",
            chain="base",
        ),
        NOW,
        "fixture-launch",
    )

    with pytest.raises(ValueError, match="Solana candidates only"):
        paper_entry_decision(entry_event(other_chain.id), other_chain, configured)


def test_paper_decision_fills_once_and_restart_recovers_without_requoting() -> None:
    async def scenario() -> None:
        configured = Settings.from_env(paper_values()).paper_auto_policy
        assert isinstance(configured, PaperAutoPolicy)
        token_candidate = candidate()
        event = entry_event(token_candidate.id)
        ledger = InMemoryPaperLedgerStore()
        await ledger.create_portfolio(
            initial_balance=configured.initial_balance_sol,
            currency="SOL",
            portfolio_id=configured.portfolio_id,
        )
        execution = PaperExecutionEngine(ledger, build_paper_execution_policy(configured))
        now = [NOW + timedelta(seconds=1)]

        class Quotes:
            calls = 0

            async def quote(self, request):
                self.calls += 1
                return QuoteSnapshot(
                    provenance=Provenance(
                        provider="fixture.jupiter",
                        source_id="paper-entry-quote-1",
                        observed_at=now[0],
                        parser_version="fixture-v1",
                    ),
                    input_mint=request.input_mint,
                    output_mint=request.output_mint,
                    input_amount=request.amount,
                    output_amount=2_000_000,
                    price_impact_bps=25,
                    route=("jupiter-fixture-route",),
                    freshness=Freshness(now[0], now[0] + timedelta(seconds=30)),
                    minimum_output_amount=1_980_000,
                    slippage_bps=request.slippage_bps,
                    amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
                    input_decimals=request.input_decimals,
                    output_decimals=request.output_decimals,
                )

        quotes = Quotes()

        class Observations:
            def __init__(self) -> None:
                self.rows = {}

            async def add(self, observation):
                existing = self.rows.get(observation.id)
                if existing is not None:
                    assert existing.normalized_payload == observation.normalized_payload
                    assert existing.quality_state is observation.quality_state
                    return existing
                self.rows[observation.id] = observation
                return observation

        observations = Observations()
        save_observation = observations.add

        def service() -> ShadowEntryService:
            return ShadowEntryService(
                policy=ShadowEntryPolicy(
                    default_paper_size_quote=configured.entry_size_sol,
                    slippage_bps=configured.max_slippage_bps,
                    max_price_impact_bps=configured.max_price_impact_bps,
                    min_liquidity_usd=configured.min_liquidity_usd,
                    quote_ttl=timedelta(seconds=configured.quote_ttl_seconds),
                    version=configured.version,
                    config_hash=configured.config_hash,
                ),
                clock=lambda: now[0],
            )

        first = await process_paper_entry(
            event,
            token_candidate,
            configured,
            quote_port=quotes,
            shadow_entry=service(),
            paper_engine=execution,
            save_observation=save_observation,
            observed_at=now[0],
        )
        now[0] += timedelta(seconds=1)
        after_restart = await process_paper_entry(
            event,
            token_candidate,
            configured,
            quote_port=quotes,
            shadow_entry=service(),
            paper_engine=execution,
            save_observation=save_observation,
            observed_at=now[0],
        )

        assert first.status is ShadowEntryStatus.SHADOW_FILLED
        assert after_restart.status is ShadowEntryStatus.DUPLICATE
        assert after_restart.paper_result.order.state is PaperOrderState.FILLED
        assert quotes.calls == 1
        assert len(await ledger.list_orders(configured.portfolio_id)) == 1
        assert len(await ledger.list_fills(configured.portfolio_id)) == 1
        assert len(observations.rows) == 1

    asyncio.run(scenario())


async def _open_paper_fixture(
    configured: PaperAutoPolicy,
    token_candidate: Candidate,
) -> tuple[InMemoryPaperLedgerStore, PaperExecutionEngine, Position]:
    ledger = InMemoryPaperLedgerStore()
    await ledger.create_portfolio(
        initial_balance=configured.initial_balance_sol,
        currency="SOL",
        portfolio_id=configured.portfolio_id,
    )
    execution = PaperExecutionEngine(ledger, build_paper_execution_policy(configured))
    quote_time = NOW + timedelta(seconds=1)

    class EntryQuote:
        async def quote(self, request):
            return QuoteSnapshot(
                provenance=Provenance(
                    provider="fixture.jupiter",
                    source_id="paper-entry-before-exit",
                    observed_at=quote_time,
                    parser_version="fixture-v1",
                ),
                input_mint=request.input_mint,
                output_mint=request.output_mint,
                input_amount=request.amount,
                output_amount=2_000_000,
                price_impact_bps=25,
                route=("jupiter-fixture-route",),
                freshness=Freshness(quote_time, quote_time + timedelta(seconds=30)),
                minimum_output_amount=1_980_000,
                slippage_bps=request.slippage_bps,
                amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
                input_decimals=request.input_decimals,
                output_decimals=request.output_decimals,
            )

    async def save_observation(_observation):
        return None

    entry_policy = ShadowEntryPolicy(
        default_paper_size_quote=configured.entry_size_sol,
        slippage_bps=configured.max_slippage_bps,
        max_price_impact_bps=configured.max_price_impact_bps,
        min_liquidity_usd=configured.min_liquidity_usd,
        quote_ttl=timedelta(seconds=configured.quote_ttl_seconds),
        version=configured.version,
        config_hash=configured.config_hash,
    )
    result = await process_paper_entry(
        entry_event(token_candidate.id),
        token_candidate,
        configured,
        quote_port=EntryQuote(),
        shadow_entry=ShadowEntryService(policy=entry_policy, clock=lambda: quote_time),
        paper_engine=execution,
        save_observation=save_observation,
        observed_at=quote_time,
    )
    assert result.status is ShadowEntryStatus.SHADOW_FILLED
    assert result.paper_result is not None and result.paper_result.position is not None
    return ledger, execution, result.paper_result.position


class _ExitQuotes:
    def __init__(
        self,
        position,
        *,
        semantics: PriceSemantics = PriceSemantics.EXECUTION_QUOTE,
        stale: bool = False,
        fail: bool = False,
    ) -> None:
        self.position = position
        self.semantics = semantics
        self.stale = stale
        self.fail = fail
        self.calls = 0
        self.multiplier = Decimal("1.3")

    async def quote(self, request):
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture provider unavailable")
        quote_time = NOW - timedelta(seconds=60) if self.stale else NOW + timedelta(seconds=2)
        expiry = NOW - timedelta(seconds=30) if self.stale else quote_time + timedelta(seconds=30)
        token_quantity = Decimal(request.amount) / (Decimal(10) ** request.input_decimals)
        sol_output = token_quantity * self.position.average_entry * self.multiplier
        raw_output = (sol_output * Decimal(10**9)).to_integral_value(rounding=ROUND_DOWN)
        return QuoteSnapshot(
            provenance=Provenance(
                provider="fixture.jupiter",
                source_id=f"paper-exit-{self.calls}",
                observed_at=quote_time,
                parser_version="fixture-v1",
            ),
            input_mint=request.input_mint,
            output_mint=request.output_mint,
            input_amount=request.amount,
            output_amount=raw_output,
            price_impact_bps=25,
            route=("jupiter-fixture-route",),
            freshness=Freshness(quote_time, expiry),
            minimum_output_amount=(raw_output * Decimal("0.99")).to_integral_value(
                rounding=ROUND_DOWN
            ),
            slippage_bps=request.slippage_bps,
            amount_unit=QuoteAmountUnit.RAW_BASE_UNITS,
            input_decimals=request.input_decimals,
            output_decimals=request.output_decimals,
            price_semantics=self.semantics,
        )


def test_paper_exit_cycle_fills_from_fresh_sell_quote_and_closes_position() -> None:
    async def scenario() -> None:
        configured = Settings.from_env(paper_values()).paper_auto_policy
        assert isinstance(configured, PaperAutoPolicy)
        token_candidate = candidate()
        ledger, execution, position = await _open_paper_fixture(configured, token_candidate)
        quotes = _ExitQuotes(position)
        evaluations = InMemoryExitEvaluationStore()

        async def candidate_lookup(candidate_id):
            return token_candidate if candidate_id == token_candidate.id else None

        result = await process_paper_exits_once(
            configured,
            quote_port=quotes,
            paper_engine=execution,
            ledger=ledger,
            exit_engine=ExitEngine(build_paper_exit_policy(configured)),
            exit_store=evaluations,
            candidate_lookup=candidate_lookup,
            now=NOW + timedelta(seconds=2),
        )

        assert len(result) == 1
        assert result[0].order.side.value == "SELL"
        assert result[0].order.state is PaperOrderState.FILLED
        assert result[0].position is not None and result[0].position.state.value == "CLOSED"
        assert len(await evaluations.list(position.id)) == 1
        assert quotes.calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("semantics", "stale", "fail"),
    (
        (PriceSemantics.MARKET_REFERENCE, False, False),
        (PriceSemantics.EXECUTION_QUOTE, True, False),
        (PriceSemantics.EXECUTION_QUOTE, False, True),
    ),
)
def test_paper_exit_cycle_does_not_fill_without_a_fresh_execution_quote(
    semantics: PriceSemantics,
    stale: bool,
    fail: bool,
) -> None:
    async def scenario() -> None:
        configured = Settings.from_env(paper_values()).paper_auto_policy
        assert isinstance(configured, PaperAutoPolicy)
        token_candidate = candidate()
        ledger, execution, position = await _open_paper_fixture(configured, token_candidate)
        quotes = _ExitQuotes(position, semantics=semantics, stale=stale, fail=fail)
        evaluations = InMemoryExitEvaluationStore()

        async def candidate_lookup(candidate_id):
            return token_candidate if candidate_id == token_candidate.id else None

        result = await process_paper_exits_once(
            configured,
            quote_port=quotes,
            paper_engine=execution,
            ledger=ledger,
            exit_engine=ExitEngine(build_paper_exit_policy(configured)),
            exit_store=evaluations,
            candidate_lookup=candidate_lookup,
            now=NOW + timedelta(seconds=2),
        )

        assert result == ()
        assert len(await ledger.list_orders(configured.portfolio_id)) == 1
        assert (await ledger.list_positions(configured.portfolio_id))[0].state.value == "OPEN"
        assert await evaluations.list(position.id) == ()

    asyncio.run(scenario())


def test_paper_exit_monitor_marks_peak_so_trailing_stop_can_fire() -> None:
    async def scenario() -> None:
        values = paper_values()
        values["PAPER_AUTO_TAKE_PROFIT_BPS"] = "9000"
        configured = Settings.from_env(values).paper_auto_policy
        assert isinstance(configured, PaperAutoPolicy)
        token_candidate = candidate()
        ledger, execution, position = await _open_paper_fixture(configured, token_candidate)
        quotes = _ExitQuotes(position)
        evaluations = InMemoryExitEvaluationStore()
        exit_engine = ExitEngine(build_paper_exit_policy(configured))

        async def candidate_lookup(candidate_id):
            return token_candidate if candidate_id == token_candidate.id else None

        async def cycle(at):
            return await process_paper_exits_once(
                configured,
                quote_port=quotes,
                paper_engine=execution,
                ledger=ledger,
                exit_engine=exit_engine,
                exit_store=evaluations,
                candidate_lookup=candidate_lookup,
                now=at,
            )

        quotes.multiplier = Decimal("1.15")
        assert await cycle(NOW + timedelta(seconds=2)) == ()
        marked = await ledger.get_position(position.portfolio_id, position.token_id)
        assert marked is not None
        assert marked.high_watermark is not None
        assert marked.high_watermark > position.average_entry * Decimal("1.14")
        assert marked.mfe > 0

        quotes.multiplier = Decimal("1.05")
        result = await cycle(NOW + timedelta(seconds=3))
        assert len(result) == 1
        assert result[0].order.side.value == "SELL"
        exit_evaluations = await evaluations.list(position.id)
        assert any("TRAILING" in rule for rule in exit_evaluations[-1].triggered_rules)

    asyncio.run(scenario())


def test_partial_take_profit_exit_rounds_down_and_is_recovered_as_consumed() -> None:
    async def scenario() -> None:
        values = paper_values()
        values["PAPER_AUTO_TAKE_PROFIT_FRACTION"] = "0.3333333"
        configured = Settings.from_env(values).paper_auto_policy
        assert isinstance(configured, PaperAutoPolicy)
        token_candidate = candidate()
        ledger, execution, position = await _open_paper_fixture(configured, token_candidate)
        quotes = _ExitQuotes(position)
        evaluations = InMemoryExitEvaluationStore()

        async def candidate_lookup(candidate_id):
            return token_candidate if candidate_id == token_candidate.id else None

        result = await process_paper_exits_once(
            configured,
            quote_port=quotes,
            paper_engine=execution,
            ledger=ledger,
            exit_engine=ExitEngine(build_paper_exit_policy(configured)),
            exit_store=evaluations,
            candidate_lookup=candidate_lookup,
            now=NOW + timedelta(seconds=2),
        )
        assert len(result) == 1
        assert result[0].order.state is PaperOrderState.FILLED
        assert result[0].order.requested_amount == Decimal("0.660065")
        assert quotes.calls == 2
        exit_evaluations = await evaluations.list(position.id)
        assert exit_evaluations[0].action is ExitAction.REDUCE
        assert exit_evaluations[0].triggered_rules == ("TAKE_PROFIT:take-profit",)

        retry = await process_paper_exits_once(
            configured,
            quote_port=quotes,
            paper_engine=execution,
            ledger=ledger,
            exit_engine=ExitEngine(build_paper_exit_policy(configured)),
            exit_store=evaluations,
            candidate_lookup=candidate_lookup,
            now=NOW + timedelta(seconds=3),
        )
        assert retry == ()
        assert quotes.calls == 3

    asyncio.run(scenario())


def test_worker_starts_paper_consumer_only_for_explicit_policy(monkeypatch) -> None:
    started: list[bool] = []

    async def consume(_stop_event, settings, *, sleeper) -> None:
        del sleeper
        started.append(settings.paper_auto_policy is not None)
        _stop_event.set()

    monkeypatch.setattr(worker_main, "_run_paper_auto", consume)
    monkeypatch.setattr(worker_main, "_early_alpha_shadow_is_configured", lambda _: False)
    monkeypatch.setattr(worker_main, "_pumpfun_forward_is_configured", lambda _: False)

    async def stop_idle_worker(_: float) -> None:
        idle_stop.set()

    disabled = Settings.from_env({})
    idle_stop = asyncio.Event()
    asyncio.run(worker_main.run_worker(idle_stop, disabled, sleeper=stop_idle_worker))
    assert started == []

    enabled = Settings.from_env(paper_values())
    asyncio.run(worker_main.run_worker(asyncio.Event(), enabled))
    assert started == [True]
