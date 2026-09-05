import type { Metadata } from "next";

import { WorkstationShell } from "./components/shell";
import { fetchOperations } from "./lib/read-api";

import "./globals.css";

export const metadata: Metadata = {
  title: "MemeRadar Operator",
  description: "Evidence-first Solana memecoin intelligence operator console"
};

export default async function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const operations = await fetchOperations();
  return (
    <html lang="en" data-theme="dark">
      <body>
        <WorkstationShell operations={operations}>{children}</WorkstationShell>
      </body>
    </html>
  );
}
