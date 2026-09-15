import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { runtimeEnv } from "../../../lib/runtime-env";

export const dynamic = "force-dynamic";

function apiBase(): URL | null {
  const raw = runtimeEnv("MEMERADAR_API_BASE_URL");
  if (!raw) return null;
  try {
    const base = new URL(raw);
    if ((base.protocol !== "http:" && base.protocol !== "https:") || base.username || base.password) {
      return null;
    }
    return base;
  } catch {
    return null;
  }
}

function safeResult(body: unknown): Record<string, unknown> | null {
  if (typeof body !== "object" || body === null || Array.isArray(body)) return null;
  const value = body as Record<string, unknown>;
  const kind = value.kind;
  const query = value.query;
  if (
    typeof kind !== "string" ||
    !["TOKEN", "WALLET", "CALLER", "AMBIGUOUS", "NOT_FOUND"].includes(kind) ||
    typeof query !== "string" ||
    query.length > 256
  ) {
    return null;
  }
  return {
    kind,
    query,
    chain: typeof value.chain === "string" ? value.chain : null,
    identifier: typeof value.identifier === "string" ? value.identifier : null,
    route: typeof value.route === "string" ? value.route : null,
    reason_codes: Array.isArray(value.reason_codes)
      ? value.reason_codes.filter((item): item is string => typeof item === "string").slice(0, 64)
      : []
  };
}

export async function GET(request: NextRequest) {
  const base = apiBase();
  const token = runtimeEnv("MEMERADAR_VIEWER_API_TOKEN");
  const query = request.nextUrl.searchParams.get("q")?.trim() ?? "";
  if (!base || !token) {
    return NextResponse.json({ detail: "server search gateway is not configured" }, { status: 503 });
  }
  if (!query || query.length > 256) {
    return NextResponse.json({ detail: "search query is invalid" }, { status: 422 });
  }
  const url = new URL("/v1/search/resolve", base);
  url.searchParams.set("q", query);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4_000);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      headers: { Authorization: "Bearer " + token },
      signal: controller.signal
    });
    if (!response.ok) {
      const status = response.status === 401 || response.status === 403
        ? response.status
        : response.status >= 500 ? 503 : response.status;
      return NextResponse.json(
        { detail: status === 503 ? "search service unavailable" : "search request rejected" },
        { status }
      );
    }
    const parsed = safeResult(await response.json());
    return parsed === null
      ? NextResponse.json({ detail: "invalid search response" }, { status: 502 })
      : NextResponse.json(parsed);
  } catch {
    return NextResponse.json({ detail: "search service unavailable" }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}
