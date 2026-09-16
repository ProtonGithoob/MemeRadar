import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

const VIEWER = "viewer-route-secret";
const ADMIN = "admin-route-secret";

function request(method: "GET" | "POST", body?: unknown): NextRequest {
  return new NextRequest("http://web.example/api/control/runtime-settings", {
    method,
    ...(body === undefined ? {} : {
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" }
    })
  });
}

describe("runtime settings web gateway", () => {
  beforeEach(() => {
    vi.stubEnv("MEMERADAR_API_BASE_URL", "http://api.internal:8000");
    vi.stubEnv("MEMERADAR_VIEWER_API_TOKEN", VIEWER);
    vi.stubEnv("MEMERADAR_ADMIN_API_TOKEN", ADMIN);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    ));
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses only the least-privilege viewer credential for GET", async () => {
    const response = await GET(request("GET"));
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(
      "http://api.internal:8000/v1/control/runtime-settings",
      expect.objectContaining({
        headers: { Authorization: `Bearer ${VIEWER}` }
      })
    );
    expect(JSON.stringify(vi.mocked(fetch).mock.calls)).not.toContain(ADMIN);
  });

  it("denies unauthenticated browser mutation even when server admin exists", async () => {
    const response = await POST(request("POST", {
      changes: { website_name: "attacker" },
      clear: [],
      reason: "unauthenticated mutation"
    }));

    expect(response.status).toBe(403);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("keeps production web mutations disabled without a trusted operator boundary", async () => {
    vi.stubEnv("APP_ENV", "production");
    vi.stubEnv("MEMERADAR_WEB_CONTROL_MUTATIONS_ENABLED", "true");

    const response = await POST(request("POST", {
      changes: { website_name: "attacker" },
      clear: [],
      reason: "missing trusted operator"
    }));

    expect(response.status).toBe(403);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
