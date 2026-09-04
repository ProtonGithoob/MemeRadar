import { RadarDashboard } from "./components/radar";
import { fetchCandidates, fetchEarlyRadar, parseRadarFilters } from "./lib/read-api";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function Home({
  searchParams
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = parseRadarFilters(await searchParams);
  const [result, earlyResult] = await Promise.all([
    fetchCandidates(filters),
    fetchEarlyRadar()
  ]);
  return <RadarDashboard filters={filters} result={result} earlyResult={earlyResult} />;
}
