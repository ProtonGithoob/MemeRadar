import { RadarExplorer } from "../components/radar";
import { fetchCandidates, fetchEarlyRadar, parseRadarFilters } from "../lib/read-api";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function RadarPage({
  searchParams
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = parseRadarFilters(await searchParams);
  const [result, earlyResult] = await Promise.all([
    fetchCandidates(filters),
    fetchEarlyRadar()
  ]);
  return <RadarExplorer earlyResult={earlyResult} filters={filters} result={result} />;
}
