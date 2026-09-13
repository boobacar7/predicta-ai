import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";

export function StrengthsList({ items }: { items: string[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Forces</CardTitle>
      </CardHeader>
      <CardBody>
        {items.length === 0 ? (
          <p className="text-sm text-muted">Information indisponible</p>
        ) : (
          <ul className="space-y-2 text-sm leading-6 text-muted-strong">
            {items.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-value" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
