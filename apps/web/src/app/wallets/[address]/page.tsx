import Link from "next/link";

import { OperatorHeader } from "../../components/operator-header";
import { ProtectedShell } from "../../components/radar";
import { WalletDetailView } from "../../components/wallet-detail";
import { fetchWallet } from "../../lib/read-api";

export default async function WalletDetailPage({
  params
}: {
  params: Promise<{ address: string }>;
}) {
  const { address } = await params;
  const result = await fetchWallet(address);
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <Link className="back-link" href="/wallets">← BACK TO WALLETS</Link>
      <section className="section-block detail-section" aria-label="Wallet detail">
        <WalletDetailView result={result} />
      </section>
    </main>
  );
}

