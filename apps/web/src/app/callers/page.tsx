import { CallersDashboard } from "../components/callers";
import { fetchCallerConvergence, fetchCallerProfiles, fetchSocialCalls } from "../lib/read-api";

export default async function CallersPage() {
  const [profiles, calls, convergence] = await Promise.all([
    fetchCallerProfiles(),
    fetchSocialCalls(),
    fetchCallerConvergence()
  ]);
  return <CallersDashboard calls={calls} convergence={convergence} profiles={profiles} />;
}
