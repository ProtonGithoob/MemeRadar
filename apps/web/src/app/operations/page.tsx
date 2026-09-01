import { OperationsDashboard } from "../components/operations";
import { fetchOperations } from "../lib/read-api";

export default async function OperationsPage() {
  return <OperationsDashboard result={await fetchOperations()} />;
}
