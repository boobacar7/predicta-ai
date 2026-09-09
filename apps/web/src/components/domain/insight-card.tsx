import { Card, CardBody } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { Insight } from "@/types/api";
import Link from "next/link";

const tones: Record<Insight["kind"], string> = {
  model: "border-ai/20",
  value: "border-value/20",
  data: "border-border",
  caution: "border-warning/30",
};

export function InsightCard({ insight }: { insight: Insight }) {
  const inner = (
    <Card className={cn(tones[insight.kind])}>
      <CardBody>
        <p className="text-xs uppercase tracking-[0.16em] text-faint">{insight.kind}</p>
        <h3 className="mt-2 text-base font-medium">{insight.title}</h3>
        <p className="mt-2 text-sm leading-6 text-muted">{insight.body}</p>
      </CardBody>
    </Card>
  );

  if (!insight.href) return inner;
  return <Link href={insight.href}>{inner}</Link>;
}
