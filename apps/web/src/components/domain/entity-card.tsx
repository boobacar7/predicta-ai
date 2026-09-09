import { Card, CardBody } from "@/components/ui/card";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Clickable catalogue entry.
 *
 * The whole card is a single link, so keyboard and pointer users share one
 * target and screen readers announce one destination rather than several.
 */
export function EntityCard({
  href,
  title,
  subtitle,
  leading,
  trailing,
}: {
  href: string;
  title: string;
  subtitle?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
}) {
  return (
    <Link href={href} className="block h-full rounded-2xl">
      <Card className="h-full transition-colors hover:border-border-strong hover:bg-surface-elevated">
        <CardBody className="flex items-center gap-3">
          {leading}
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{title}</p>
            {subtitle ? <p className="truncate text-xs text-muted">{subtitle}</p> : null}
          </div>
          {trailing}
        </CardBody>
      </Card>
    </Link>
  );
}
