import { Badge } from "@/components/ui/badge";

export function MockBanner({ generatedAt }: { generatedAt?: string }) {
  return (
    <div className="border-b border-warning/20 bg-warning-soft px-4 py-2 text-center text-xs text-warning md:text-left">
      <Badge tone="warning" className="mr-2">
        mock
      </Badge>
      Données de démonstration fictives. Aucune compétition, cote ou performance réelle n’est
      représentée.
      {generatedAt ? ` Horloge mock : ${generatedAt}.` : ""}
    </div>
  );
}
