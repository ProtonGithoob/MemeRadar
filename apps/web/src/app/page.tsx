import { RadarDashboard } from "./components/radar";
import { fetchCandidates, parseRadarFilters } from "./lib/read-api";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function Home({
  searchParams
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = parseRadarFilters(await searchParams);
  const result = await fetchCandidates(filters);
  return <RadarDashboard filters={filters} result={result} />;
}
