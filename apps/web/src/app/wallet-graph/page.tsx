import { Metadata } from "next";
import { WalletGraphExplorer } from "../components/wallet-graph";

export const metadata: Metadata = {
  title: "Wallet & Creator Outcome Graph — MemeRadar",
  description: "Read-only wallet, funder, deployer and token outcome graph explorer.",
};

export default function WalletGraphPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Read-only outcome graph / E8.6</p>
          <h2>Wallet &amp; Creator Outcome Graph</h2>
        </div>
        <small>Relationships are advisory evidence, not execution authority.</small>
      </div>
      <WalletGraphExplorer />
    </>
  );
}
