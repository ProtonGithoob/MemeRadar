"use client";

import { useRouter } from "next/navigation";

export function ScanRefresh() {
  const router = useRouter();
  return <button className="preset-chip" type="button" onClick={() => router.refresh()}>Refresh now</button>;
}
