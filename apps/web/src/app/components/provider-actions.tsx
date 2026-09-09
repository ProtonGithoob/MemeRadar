"use client";

import Link from "next/link";
import { useState } from "react";

export function ProviderActions({ provider }: { provider: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function doctor(): Promise<void> {
    setLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/providers/doctor?provider=${encodeURIComponent(provider)}`, { cache: "no-store" });
      const body = await response.json().catch(() => null) as { items?: Array<{ capability?: string; state?: string }> } | null;
      if (!response.ok) {
        setMessage("DOCTOR UNAVAILABLE");
      } else if (!body?.items?.length) {
        setMessage("NO HEALTH EVIDENCE");
      } else {
        setMessage(body.items.map((item) => `${item.capability ?? "UNKNOWN"}: ${item.state ?? "UNKNOWN"}`).join(" · "));
      }
    } catch {
      setMessage("DOCTOR UNAVAILABLE");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="provider-card__actions">
      <Link href="/settings">OPEN SETTINGS</Link>
      <button disabled={loading} onClick={() => void doctor()} type="button">{loading ? "CHECKING…" : "TEST HEALTH"}</button>
      {message ? <small role="status">{message}</small> : null}
    </div>
  );
}
