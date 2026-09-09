import { ReadinessDashboard } from "../components/readiness";
import { fetchReadiness } from "../lib/read-api";

export default async function ReadinessPage() {
  return <ReadinessDashboard result={await fetchReadiness()} />;
}
