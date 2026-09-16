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

function statusForApi(status: number): number {
  if (status === 401 || status === 403 || status === 409 || status === 422) return status;
  return status >= 500 ? 503 : 502;
}

async function proxyRead() {
  const base = apiBase();
  const token = runtimeEnv("MEMERADAR_VIEWER_API_TOKEN");
  if (!base || !token) {
    return NextResponse.json({ detail: "server control gateway is not configured" }, { status: 503 });
  }

  const url = new URL("/v1/control/runtime-settings", base);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4_000);
  try {
    const response = await fetch(url.toString(), {
      method: "GET",
      cache: "no-store",
      headers: {
        Authorization: "Bearer " + token
      },
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
  void request;
  return proxyRead();
}

export async function POST(_request: NextRequest) {
  return NextResponse.json(
    { detail: "web control mutations are disabled; use the authenticated API operator boundary" },
    { status: 403 }
  );
}
