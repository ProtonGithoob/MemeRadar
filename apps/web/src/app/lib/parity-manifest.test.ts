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
});
