import { normalizeMatchFilters, queryKeys } from "@/lib/query/keys";
import { hashKey } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

describe("filter normalisation", () => {
  it("maps an absent filter to the same shape as an explicit 'all'", () => {
    expect(normalizeMatchFilters({})).toEqual(normalizeMatchFilters({ sport: "all" }));
  });

  it("trims a search term so trailing whitespace does not split the cache", () => {
    expect(hashKey(queryKeys.teams.list("success", { query: "harbor " }))).toBe(
      hashKey(queryKeys.teams.list("success", { query: "harbor" })),
    );
  });
});

describe("cache separation", () => {
  it("keeps scenarios apart, so an error scenario cannot reuse a success payload", () => {
    expect(hashKey(queryKeys.matches.list("success"))).not.toBe(
      hashKey(queryKeys.matches.list("error")),
    );
  });

  it("keeps different filters apart", () => {
    expect(hashKey(queryKeys.matches.list("success", { sport: "football" }))).not.toBe(
      hashKey(queryKeys.matches.list("success", { sport: "tennis" })),
    );
  });

  it("keeps a list and a detail of the same resource apart", () => {
    expect(hashKey(queryKeys.matches.list("success"))).not.toBe(
      hashKey(queryKeys.matches.detail("success", "mth_1")),
    );
  });

  it("produces a stable key regardless of how the filter object was built", () => {
    expect(hashKey(queryKeys.matches.list("success", { sport: "football", date: "2026-09-09" }))).toBe(
      hashKey(queryKeys.matches.list("success", { date: "2026-09-09", sport: "football" })),
    );
  });
});

describe("hierarchy", () => {
  it("prefixes every resource key with the root, enabling prefix invalidation", () => {
    const root = queryKeys.root("success");

    for (const key of [
      queryKeys.matches.list("success"),
      queryKeys.matches.detail("success", "mth_1"),
      queryKeys.picks.list("success"),
      queryKeys.performance("success"),
    ]) {
      expect(key.slice(0, root.length)).toEqual([...root]);
    }
  });

  it("nests detail keys under the resource prefix", () => {
    const all = queryKeys.teams.all("success");
    const detail = queryKeys.teams.detail("success", "tm_1");

    expect(detail.slice(0, all.length)).toEqual([...all]);
  });
});
