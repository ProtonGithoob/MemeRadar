import { CommandCenter } from "./components/command-center";
import { fetchCandidates, fetchEarlyRadar, fetchOperations } from "./lib/read-api";

export default async function Home() {
  const [result, earlyResult, operations] = await Promise.all([
    fetchCandidates({}),
    fetchEarlyRadar(),
    fetchOperations()
  ]);
  return <CommandCenter earlyResult={earlyResult} operations={operations} result={result} />;
}
