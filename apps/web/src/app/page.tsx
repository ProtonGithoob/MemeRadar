import { RadarDashboard } from "./components/radar";
import {
  fetchCandidates,
  fetchEarlyRadar,
  fetchOperations,
  fetchProviderHealth,
  fetchPositions,
  parseRadarFilters,
} from "./lib/read-api";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = parseRadarFilters(await searchParams);
  const [result, earlyResult, opsResult, providerHealthResult, positionsResult] = await Promise.all([
    fetchCandidates(filters),
    fetchEarlyRadar(),
    fetchOperations(),
    fetchProviderHealth(),
    fetchPositions(),
  ]);

  return (
    <RadarDashboard
      filters={filters}
      result={result}
      earlyResult={earlyResult}
      opsResult={opsResult}
      providerHealthResult={providerHealthResult}
      positionsResult={positionsResult}
    />
  );
}
