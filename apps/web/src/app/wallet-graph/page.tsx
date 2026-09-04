import { Metadata } from "next";
import { OperatorHeader } from "../components/operator-header";
import { ProtectedShell } from "../components/radar";
import { WalletGraphExplorer } from "../components/wallet-graph";

export const metadata: Metadata = {
  title: "Wallet & Creator Outcome Graph — MemeRadar",
  description: "Read-only wallet, funder, deployer and token outcome graph explorer.",
};

export default function WalletGraphPage() {
  return (
    <main className="shell">
      <OperatorHeader />
      <ProtectedShell />
      <section className="section-block intelligence-section" aria-labelledby="graph-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">READ-ONLY OUTCOME GRAPH / E8.6</p>
            <h3 id="graph-title">Wallet & Creator Outcome Graph</h3>
          </div>
          <p className="section-note">Relationships are advisory evidence, not execution authority.</p>
        </div>
        <WalletGraphExplorer />
      </section>
    </main>
  );
}
