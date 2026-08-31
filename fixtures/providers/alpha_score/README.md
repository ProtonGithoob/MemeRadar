# AlphaScore replay fixture

This directory contains the credential-free, synthetic golden replay for core
Phase 6 Sprint 6.2. It exercises a fully populated score, sparse evidence,
penalty clamping, blocked risk and unknown risk through the recomputation
service and its stable score identity.

The values are normalized `FeatureSnapshot`/`RiskAssessment` inputs, not raw
provider payloads. Reversing component or penalty mapping delivery order must
produce the same score, explanations and persistence identity. The fixture
never authorizes a real or paper order and contains no credentials.
