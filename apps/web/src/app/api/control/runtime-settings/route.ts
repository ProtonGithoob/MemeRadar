import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function apiBase(): URL | null {
  const raw = process.env.MEMERADAR_API_BASE_URL?.trim();
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

function statusForApi(status: number): number {
  if (status === 401 || status === 403 || status === 409 || status === 422) return status;
  return status >= 500 ? 503 : 502;
}

async function proxy(request: NextRequest, method: "GET" | "POST") {
  const base = apiBase();
  const token = (method === "POST"
    ? process.env.MEMERADAR_ADMIN_API_TOKEN
    : process.env.MEMERADAR_ADMIN_API_TOKEN || process.env.MEMERADAR_VIEWER_API_TOKEN)?.trim();
  if (!base || !token) {
    return NextResponse.json({ detail: "server control gateway is not configured" }, { status: 503 });
  }

  let body: string | undefined;
  if (method === "POST") {
    let raw: unknown;
    try {
      raw = await request.json();
    } catch {
      return NextResponse.json({ detail: "invalid control request" }, { status: 422 });
    }
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
      return NextResponse.json({ detail: "invalid control request" }, { status: 422 });
    }
    const value = raw as Record<string, unknown>;
    const changes = value.changes;
    const clear = value.clear;
    const reason = value.reason;
    const version = value.version;
    if (
      typeof changes !== "object" || changes === null || Array.isArray(changes) ||
      Object.keys(changes as object).length > 64 ||
      !Array.isArray(clear) || clear.length > 64 ||
      !clear.every((item) => typeof item === "string") ||
      typeof reason !== "string" || reason.trim().length === 0 || reason.length > 512 ||
      (version !== undefined && version !== null && (typeof version !== "string" || version.length > 64))
    ) {
      return NextResponse.json({ detail: "invalid control request" }, { status: 422 });
    }
    body = JSON.stringify({ changes, clear, reason, version: version ?? null });
  }

  const url = new URL("/v1/control/runtime-settings", base);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4_000);
  try {
    const response = await fetch(url, {
      method,
      cache: "no-store",
      headers: {
        Authorization: "Bearer " + token,
        ...(body ? { "Content-Type": "application/json" } : {})
      },
      body,
      signal: controller.signal
    });
    const status = response.ok ? 200 : statusForApi(response.status);
    let responseBody: unknown = { detail: "control gateway request failed" };
    try {
      responseBody = await response.json();
    } catch {
      // Keep the generic body; provider/API response text is not forwarded.
    }
    const detail = typeof responseBody === "object" && responseBody !== null &&
        "detail" in responseBody && typeof (responseBody as { detail?: unknown }).detail === "string"
      ? (responseBody as { detail: string }).detail
      : "control gateway request failed";
    return NextResponse.json(response.ok ? responseBody : { detail }, { status });
  } catch {
    return NextResponse.json({ detail: "control service unavailable" }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(request: NextRequest) {
  return proxy(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxy(request, "POST");
}
