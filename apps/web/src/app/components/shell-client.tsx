"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

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

  return (
    <>
      <button
        aria-expanded={open}
        aria-label={open ? "Close navigation" : "Open navigation"}
        className="ws-nav__toggle"
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

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SOLANA_ADDRESS_PATTERN = /^[1-9A-HJ-NP-Za-km-z]{32,64}$/;

export function SearchForm() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(): void {
    const value = query.trim();
    if (UUID_PATTERN.test(value)) {
      setError(null);
      router.push(`/tokens/${value}`);
      return;
    }
    if (SOLANA_ADDRESS_PATTERN.test(value)) {
      setError(null);
      router.push(`/wallets/${value}`);
      return;
    }
    setError("Enter a token UUID or a base58 wallet address");
  }

  return (
    <div aria-label="Operator search" className="ws-search" role="search">
      <input
        aria-label="Search by token UUID or wallet address"
        aria-invalid={error !== null}
        onChange={(event) => {
          setQuery(event.target.value);
          if (error !== null) setError(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="Token UUID / wallet address…"
        title={error ?? "Deep-link to a token UUID or wallet address"}
        type="search"
        value={query}
      />
      <button onClick={submit} type="button">GO</button>
      {error ? (
        <span className="sr-only" role="alert">{error}</span>
      ) : null}
    </div>
  );
}
