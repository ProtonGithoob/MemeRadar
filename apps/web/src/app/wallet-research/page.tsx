import { WalletResearchDashboard } from "../components/wallet-research";
import { fetchWallets, fetchWinnerRegistry } from "../lib/read-api";

export default async function WalletResearchPage() {
  const [registry, wallets] = await Promise.all([fetchWinnerRegistry(), fetchWallets()]);
  return <WalletResearchDashboard registry={registry} wallets={wallets} />;
}
