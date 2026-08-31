import { PositionsDashboard } from "../components/positions";
import { fetchPositions } from "../lib/read-api";

export default async function PositionsPage() {
  return <PositionsDashboard result={await fetchPositions({ mode: "PAPER" })} />;
}
