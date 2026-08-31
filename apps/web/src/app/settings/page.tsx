import { SettingsDashboard } from "../components/settings";
import { fetchControlConfig, fetchControlState } from "../lib/read-api";

export default async function SettingsPage() {
  const [stateResult, configResult] = await Promise.all([
    fetchControlState(),
    fetchControlConfig()
  ]);
  return <SettingsDashboard stateResult={stateResult} configResult={configResult} />;
}

