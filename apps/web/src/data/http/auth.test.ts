import { readCookie, assertNoAuthTokenStorage } from "@/data/http/cookies";
import { safeNextPath } from "@/data/http/auth";
import { describe, expect, it } from "vitest";

describe("readCookie", () => {
  it("decodes a CSRF cookie from a cookie header", () => {
    expect(readCookie("predicta_csrf", "predicta_csrf=abc%2Fdef; other=1")).toBe("abc/def");
  });
});

describe("safeNextPath", () => {
  it("rejects open redirects", () => {
    expect(safeNextPath("https://evil.test")).toBe("/");
    expect(safeNextPath("//evil.test")).toBe("/");
    expect(safeNextPath("/login")).toBe("/");
    expect(safeNextPath("/matches")).toBe("/matches");
  });
});

describe("localStorage", () => {
  it("does not treat theme storage as an auth token", () => {
    const storage = window.localStorage;
    storage.clear();
    storage.setItem("predicta-theme", "dark");
    expect(assertNoAuthTokenStorage(storage)).toEqual([]);
  });
});
