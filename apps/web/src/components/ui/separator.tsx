import { cn } from "@/lib/cn";
import type { HTMLAttributes } from "react";

export function Separator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div role="separator" className={cn("h-px w-full bg-border", className)} {...props} />;
}
