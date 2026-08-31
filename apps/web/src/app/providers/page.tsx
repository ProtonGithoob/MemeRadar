import { ProvidersDashboard } from "../components/providers";
import { fetchProviderHealth } from "../lib/read-api";

export default async function ProvidersPage() {
  return <ProvidersDashboard result={await fetchProviderHealth()} />;
}

