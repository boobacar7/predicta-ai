import { cn } from "@/lib/cn";
import type { InputHTMLAttributes } from "react";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground placeholder:text-faint",
        className,
      )}
      {...props}
    />
  );
}
