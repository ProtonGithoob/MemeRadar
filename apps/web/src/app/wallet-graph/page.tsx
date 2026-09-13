import { Metadata } from "next";
import { WalletGraphExplorer } from "../components/wallet-graph";
import { PageHeader } from "../components/ui";

export const metadata: Metadata = {
  title: "Wallet & Creator Outcome Graph — MemeRadar",
  description: "Read-only wallet, funder, deployer and token outcome graph explorer.",
};

export default function WalletGraphPage() {
  return (
    <>
      <PageHeader
        eyebrow="Read-only outcome graph / E8.6"
        note="Relationships are advisory evidence, not execution authority."
        title="Wallet & Creator Outcome Graph"
      />
      <WalletGraphExplorer />
    </>
  );
}
