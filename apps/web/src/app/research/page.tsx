import { Metadata } from "next";
import { ResearchDashboard } from "../components/research";

export const metadata: Metadata = {
  title: "Research & Strategy Calibration — MemeRadar",
  description: "Read-only product research gate, evidence taxonomy and exit strategy calibration.",
};

export default function ResearchPage() {
  return <ResearchDashboard />;
}
