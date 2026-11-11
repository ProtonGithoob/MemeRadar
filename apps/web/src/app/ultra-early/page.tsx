import { UltraEarlyWorkspace } from "../components/ultra-early";
import { fetchEarlyRadar } from "../lib/read-api";

export default async function UltraEarlyPage() {
  const result = await fetchEarlyRadar(true);
  return <UltraEarlyWorkspace result={result} />;
}
