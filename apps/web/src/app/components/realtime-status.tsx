"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  RealtimeTransport,
  type RealtimeStatus as RealtimeStatusValue
} from "../lib/realtime";
import { ConnectionBadge } from "./status-badges";

function initialStatus(url: string | undefined): RealtimeStatusValue {
  return url
    ? { state: "CONNECTING", attempt: 0 }
    : { state: "DISABLED", attempt: 0, reason: "realtime endpoint not configured" };
}

export function useRealtimeStatus(url?: string): RealtimeStatusValue {
  const [status, setStatus] = useState<RealtimeStatusValue>(() => initialStatus(url));

  useEffect(() => {
    const transport = new RealtimeTransport({ url, onStatus: setStatus });
    transport.start();
    return () => transport.stop();
  }, [url]);

  return status;
}

export function RealtimeStatus() {
  const url = process.env.NEXT_PUBLIC_REALTIME_URL || undefined;
  const status = useRealtimeStatus(url);
  const router = useRouter();
  useEffect(() => {
    if (url) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [router, url]);
  if (!url) return <span className="chip chip--info" role="status">AUTO REFRESH · 30s</span>;
  return <ConnectionBadge {...status} />;
}
