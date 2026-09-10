"use client";

import { Badge } from "@/components/ui/badge";
import { groupExclusions } from "@/features/picks/selectors";
import { exclusionReasonLabels, football1x2Labels } from "@/lib/format/labels";
import type { AiPickExclusion } from "@/types/api";

/**
 * Selections the engine rejected, grouped by rule.
 *
 * This is not a debugging aid. When the list of picks is short or empty, the
 * exclusions are the only honest explanation of why, and they prevent the page
 * from reading as "nothing was found" when the real answer is "the thresholds
 * rejected everything". Rejections are never silent.
 */
export function ExclusionsPanel({ exclusions }: { exclusions: readonly AiPickExclusion[] }) {
  if (exclusions.length === 0) {
    return null;
  }

  const groups = groupExclusions(exclusions);

  return (
    <details className="rounded-2xl border border-border bg-surface">
      <summary className="cursor-pointer list-none px-4 py-3 text-sm text-muted-strong marker:content-none">
        <span className="font-medium text-foreground">
          {exclusions.length} sélection{exclusions.length > 1 ? "s" : ""} écartée
          {exclusions.length > 1 ? "s" : ""}
        </span>{" "}
        · voir les motifs
      </summary>

      <ul className="space-y-3 border-t border-border px-4 py-3">
        {groups.map((group) => (
          <li key={group.reason} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="muted">{exclusionReasonLabels[group.reason]}</Badge>
              <span className="text-xs text-faint">{group.count}</span>
            </div>
            <ul className="space-y-1">
              {group.items.map((item) => (
                <li
                  key={`${item.match_id}-${item.selection ?? "market"}`}
                  className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted"
                >
                  <span className="font-mono break-all text-faint">{item.match_id}</span>
                  <span>
                    {item.selection ? football1x2Labels[item.selection] : "Marché entier"}
                  </span>
                  <span className="text-faint">{item.detail}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </details>
  );
}
