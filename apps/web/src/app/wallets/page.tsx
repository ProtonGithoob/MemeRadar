import { WalletsDashboard } from "../components/wallets";
import { fetchWallets } from "../lib/read-api";

export default async function WalletsPage() {
  return <WalletsDashboard result={await fetchWallets()} />;
}

