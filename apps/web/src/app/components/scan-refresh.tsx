"use client";

import { useRouter } from "next/navigation";

export function ScanRefresh() {
  const router = useRouter();
  return <button type="button" onClick={() => router.refresh()}>Refresh now</button>;
}
