import { AiAnalystView } from "@/features/ai-analyst";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = { title: "AI Analyst" };

export default function AiAnalystPage() {
  return (
    <Suspense>
      <AiAnalystView />
    </Suspense>
  );
}
