import { KeyFactors } from "@/components/domain/key-factors";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import type { FootballAnalystExplanation } from "@/types/api";

export function AiExplanation({ explanation }: { explanation: FootballAnalystExplanation }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Explanation</CardTitle>
      </CardHeader>
      <CardBody className="space-y-5">
        <p className="text-sm leading-7 text-muted-strong">{explanation.summary}</p>
        <KeyFactors factors={explanation.key_factors} />
      </CardBody>
    </Card>
  );
}
