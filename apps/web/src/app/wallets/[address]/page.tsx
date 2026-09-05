import Link from "next/link";

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
    <>
      <Link className="back-link" href="/wallets">← BACK TO WALLETS</Link>
      <section aria-label="Wallet detail" className="section-block" style={{ marginTop: 12 }}>
        <WalletDetailView result={result} />
      </section>
    </>
  );
}
