# Correlation replay fixture

replay.json is a credential-free, deterministic E6.0 fixture. It contains
synthetic normalized inputs for organic acceleration, bot/wash activity,
smart-wallet-only activity, social-only activity and creator/related-wallet
selling. The contract test constructs the existing application records from
these rows, replays them in reverse delivery order and verifies event-time
windowing, source diversity, actor-cluster dedupe, missing-evidence handling
and the permanent no-execution boundary.

The fixture is not a provider capture and does not authorize a trade.
