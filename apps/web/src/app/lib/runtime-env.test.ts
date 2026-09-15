import { afterEach, describe, expect, it, vi } from "vitest";
import { runtimeEnv } from "./runtime-env";

describe("runtimeEnv", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("reads server configuration at request time and trims empty values", () => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", " http://api.internal:8000 ");
    expect(runtimeEnv("MEMERADAR_API_BASE_URL")).toBe("http://api.internal:8000");

    vi.stubEnv("MEMERADAR_API_BASE_URL", "   ");
    expect(runtimeEnv("MEMERADAR_API_BASE_URL")).toBeUndefined();
  });
});
