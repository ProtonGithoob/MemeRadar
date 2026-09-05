"use client";

import { useState } from "react";

export function Inspector({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <aside className={open ? "tw-inspector" : "tw-inspector tw-inspector--collapsed"}>
      <button
        aria-expanded={open}
        className="inspector-toggle"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {open ? "COLLAPSE CONTEXT PANEL ▸" : "◂ CONTEXT PANEL"}
      </button>
      {open ? children : null}
    </aside>
  );
}
