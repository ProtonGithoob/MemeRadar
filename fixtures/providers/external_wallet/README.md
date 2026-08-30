# External wallet intelligence fixtures

These synthetic, redacted records exercise the E6.2 application seam for
external wallet labels and token-level signals. They cover fresh agreement,
stale evidence, disagreement with an internal `SmartWalletScore`, tracked
supply/bundle/side-wallet features and corroborating security flags.

The fixture adapter is network-free. It is not evidence that GMGN, CabalSpy or
any other external provider is configured or reachable. No credential-shaped
values belong in this directory.

Ratio fields use `0..1`, so `tracked_supply_pct: 0.25` means 25 percent.
