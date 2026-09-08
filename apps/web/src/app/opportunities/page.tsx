import { ChainOpportunitiesDashboard } from "../components/chain-opportunities";
import { fetchChainOpportunities } from "../lib/read-api";

export default async function OpportunitiesPage() {
  return <ChainOpportunitiesDashboard result={await fetchChainOpportunities()} />;
}
