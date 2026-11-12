import { UltraEarlyWorkspace } from "../components/ultra-early";
import { fetchEarlyRadar } from "../lib/read-api";

export default async function UltraEarlyPage() {
  // All tracked launches, plus the subset the backend passes through the
  // Telegram alert gate; the browser never decides alert readiness itself.
  const [result, qualified] = await Promise.all([fetchEarlyRadar(false), fetchEarlyRadar(true)]);
  return <UltraEarlyWorkspace qualified={qualified} result={result} />;
}
