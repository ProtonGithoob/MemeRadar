"use client";

import { useEffect, useState } from "react";

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
  const status = useRealtimeStatus(process.env.NEXT_PUBLIC_REALTIME_URL || undefined);
  return <ConnectionBadge {...status} />;
}
