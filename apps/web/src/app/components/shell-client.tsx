"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

const noHydrationSubscription = () => () => undefined;
const clientHydrated = () => true;
const serverHydrated = () => false;

const NAV_SECTIONS: Array<{
  label: string;
  items: Array<{ href: string; label: string; glyph: string }>;
}> = [
  {
    label: "Intelligence",
    items: [
      { href: "/", label: "Overview", glyph: "OV" },
      { href: "/radar", label: "Radar", glyph: "RD" },
      { href: "/ultra-early", label: "Ultra Early", glyph: "UE" }
    ]
  },
  {
    label: "Research",
    items: [
      { href: "/positions", label: "Positions", glyph: "PS" },
      { href: "/opportunities", label: "Opportunities", glyph: "CH" },
      { href: "/wallets", label: "Wallets", glyph: "WL" },
      { href: "/callers", label: "Callers", glyph: "CL" },
      { href: "/wallet-graph", label: "Graph", glyph: "GR" }
    ]
  },
  {
    label: "System",
    items: [
      { href: "/providers", label: "Providers", glyph: "PV" },
      { href: "/operations", label: "Operations", glyph: "OP" },
      { href: "/readiness", label: "Readiness", glyph: "RS" },
      { href: "/audit", label: "Audit", glyph: "AU" },
      { href: "/settings", label: "Settings", glyph: "ST" }
    ]
  }
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const hydrated = useSyncExternalStore(
    noHydrationSubscription,
    clientHydrated,
    serverHydrated
  );

  return (
    <>
      <button
        aria-expanded={open}
        aria-label={open ? "Close navigation" : "Open navigation"}
        className="ws-nav__toggle"
        data-nav-hydrated={hydrated ? "true" : "false"}
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {open ? "✕" : "☰"}
      </button>
      {open ? (
        <div
          aria-hidden="true"
          className="ws-nav__scrim"
          onClick={() => setOpen(false)}
        />
      ) : null}
      <nav aria-label="Operator sections" className={open ? "ws-nav ws-nav--open" : "ws-nav"}>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="ws-nav__section">{section.label}</p>
            <ul className="ws-nav__list">
              {section.items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      aria-current={active ? "page" : undefined}
                      aria-label={item.label}
                      className={active ? "ws-nav__link ws-nav__link--active" : "ws-nav__link"}
                      href={item.href}
                      onClick={() => setOpen(false)}
                    >
                      <span aria-hidden="true" className="ws-nav__glyph">{item.glyph}</span>
                      <span className="ws-nav__label">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </>
  );
}

export function SearchForm() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(): Promise<void> {
    const value = query.trim();
    if (!value) {
      setError("Enter a token, wallet, caller, or chain-qualified address");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/search/resolve?q=${encodeURIComponent(value)}`, {
        cache: "no-store"
      });
      const body = await response.json().catch(() => null) as {
        kind?: string;
        route?: string | null;
        reason_codes?: unknown;
      } | null;
      const route = body?.route;
      if (response.ok && body?.kind && typeof route === "string" && route.startsWith("/") && !route.startsWith("//")) {
        router.push(route);
        return;
      }
      const reasons = Array.isArray(body?.reason_codes)
        ? body.reason_codes.filter((item): item is string => typeof item === "string").join(", ")
        : "";
      setError(body?.kind === "AMBIGUOUS"
        ? "Search is ambiguous — use a chain-qualified address"
        : body?.kind === "NOT_FOUND"
          ? "No matching token, wallet, or caller was found"
          : reasons || "Search service unavailable");
    } catch {
      setError("Search service unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div aria-label="Operator search" className="ws-search" role="search">
      <input
        aria-label="Search token, wallet, caller, or chain-qualified address"
        aria-invalid={error !== null}
        onChange={(event) => {
          setQuery(event.target.value);
          if (error !== null) setError(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void submit();
          }
        }}
        placeholder="Token / wallet / caller / chain:address…"
        title={error ?? "Resolve a token, wallet, caller, or chain-qualified address"}
        type="search"
        value={query}
      />
      <button disabled={loading} onClick={() => void submit()} type="button">{loading ? "…" : "GO"}</button>
      {error ? (
        <p className="ws-search__error" role="alert">{error}</p>
      ) : null}
    </div>
  );
}
