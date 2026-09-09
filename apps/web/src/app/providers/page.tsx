import { ProvidersDashboard } from "../components/providers";
import { fetchProviderHealth, fetchRuntimeSettings } from "../lib/read-api";

export default async function ProvidersPage() {
  const [health, settings] = await Promise.all([fetchProviderHealth(), fetchRuntimeSettings()]);
  return <ProvidersDashboard result={health} settings={settings} />;
}
