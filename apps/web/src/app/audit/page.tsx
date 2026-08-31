import { AuditDashboard } from "../components/audit";
import { fetchAuditEvents, fetchConfigVersions } from "../lib/read-api";

export default async function AuditPage() {
  const [auditResult, configResult] = await Promise.all([
    fetchAuditEvents(),
    fetchConfigVersions()
  ]);
  return <AuditDashboard auditResult={auditResult} configResult={configResult} />;
}

