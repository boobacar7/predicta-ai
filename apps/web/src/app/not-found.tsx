import { EmptyState } from "@/components/domain/empty-state";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function NotFound() {
  return (
    <EmptyState
      title="Page introuvable"
      description="Cette route n'existe pas dans le prototype PREDICTA AI."
      action={
        <Button asChild variant="primary">
          <Link href="/football">Retour au dashboard</Link>
        </Button>
      }
    />
  );
}
