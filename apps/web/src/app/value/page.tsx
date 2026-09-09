import { ValueFinderView } from "@/features/value";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Value Finder" };

export default function ValuePage() {
  return <ValueFinderView />;
}
