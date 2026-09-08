import { SettingsDashboard } from "../components/settings";
import { fetchControlConfig, fetchControlState, fetchRuntimeSettings } from "../lib/read-api";

export default async function SettingsPage() {
  const [stateResult, configResult, runtimeSettingsResult] = await Promise.all([
    fetchControlState(),
    fetchControlConfig(),
    fetchRuntimeSettings()
  ]);
  return <SettingsDashboard stateResult={stateResult} configResult={configResult} runtimeSettingsResult={runtimeSettingsResult} />;
}
