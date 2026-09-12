import { describe, expect, it } from "vitest";

import { PARITY_MANIFEST } from "./parity-manifest";

const ROUTES = [
  "/", "/radar", "/ultra-early", "/opportunities", "/positions", "/wallets",
  "/wallets/[address]", "/wallet-graph", "/callers", "/tokens/[tokenId]", "/providers",
  "/operations", "/audit", "/settings", "/readiness"
];

describe("route parity manifest", () => {
  it("covers every operator route and explains every omission", () => {
    for (const route of ROUTES) {
      const entry = PARITY_MANIFEST[route];
      expect(entry, route).toBeDefined();
      expect(entry.apiFields.length, route).toBeGreaterThan(0);
      expect(entry.frontendFields.length, route).toBeGreaterThan(0);
      expect(entry.omissions.every((item) => item.field.length > 0 && item.reason.length > 0), route).toBe(true);
    }
  });

  it("tracks lifecycle, relationship, and Robinhood reconciliation contracts", () => {
    expect(PARITY_MANIFEST["/tokens/[tokenId]"].apiFields).toContain("launch_lifecycle.route_state");
    expect(PARITY_MANIFEST["/tokens/[tokenId]"].frontendFields).toContain("launchLifecycle.routeState");
    expect(PARITY_MANIFEST["/tokens/[tokenId]"].apiFields).toContain("insider_evidence.reason_codes");
    expect(PARITY_MANIFEST["/tokens/[tokenId]"].frontendFields).toContain("insiderEvidence.reasonCodes");
    expect(PARITY_MANIFEST["/wallet-graph"].apiFields).toContain("relationship_evidence");
    expect(PARITY_MANIFEST["/wallet-graph"].frontendFields).toContain("ownership_asserted");
    expect(PARITY_MANIFEST["/providers"].omissions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "robinhood_sequencer_rpc_launchpad_state" })
      ])
    );
    expect(PARITY_MANIFEST["Telegram/EarlyAlpha"]?.telegramFields).toContain("state");
    expect(PARITY_MANIFEST["/readiness"].apiFields).toContain("alpha_validation.real_observation_count");
    expect(PARITY_MANIFEST["/providers"].apiFields).toContain("capability_status");
    expect(PARITY_MANIFEST["/settings"].frontendFields).toContain("madeonsol_api_key_configured_state");
  });
});
