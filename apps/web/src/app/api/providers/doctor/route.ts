import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { runtimeEnv } from "../../../lib/runtime-env";

export const dynamic = "force-dynamic";

function apiBase(): URL | null {
    const raw = runtimeEnv("MEMERADAR_API_BASE_URL");
    if (!raw) return null;
    try {
      const base = new URL(raw);
      return (base.protocol === "http:" || base.protocol === "https:") && !base.username && !base.password
        ? base
        : null;
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  const base = apiBase();
  const token = runtimeEnv("MEMERADAR_VIEWER_API_TOKEN");
  const provider = request.nextUrl.searchParams.get("provider")?.trim() ?? "";
  if (!base || !token) return NextResponse.json({ detail: "provider doctor is not configured" }, { status: 503 });
  if (!provider || provider.length > 128 || !/^[a-zA-Z0-9_.:-]+$/.test(provider)) {
    return NextResponse.json({ detail: "provider is invalid" }, { status: 422 });
  }
  const url = new URL("/v1/providers/health", base);
  url.searchParams.set("provider", provider);
  url.searchParams.set("limit", "20");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4_000);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      headers: { Authorization: "Bearer " + token },
      signal: controller.signal
    });
    if (!response.ok) return NextResponse.json({ detail: "provider doctor unavailable" }, { status: response.status === 401 || response.status === 403 ? response.status : 503 });
    const body = await response.json() as { items?: unknown };
    const items = Array.isArray(body.items) ? body.items.slice(0, 20).flatMap((item) => {
      if (typeof item !== "object" || item === null || Array.isArray(item)) return [];
      const value = item as Record<string, unknown>;
      return [{
        capability: typeof value.capability === "string" ? value.capability : "UNKNOWN",
        state: typeof value.state === "string" ? value.state : "UNKNOWN",
        freshness_state: typeof value.freshness_state === "string" ? value.freshness_state : null,
        error_class: typeof value.error_class === "string" ? value.error_class : null
      }];
    }) : [];
    return NextResponse.json({ provider, items });
  } catch {
    return NextResponse.json({ detail: "provider doctor unavailable" }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}
