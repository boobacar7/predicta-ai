import { isCataloguePrototypeModel } from "@/lib/football/catalogue";
import { describe, expect, it } from "vitest";

describe("isCataloguePrototypeModel", () => {
  it("recognises the fictional ensemble series", () => {
    expect(isCataloguePrototypeModel("fb-ens-2026.08.1")).toBe(true);
  });

  it("does not treat the candidate football model as catalogue fiction", () => {
    expect(isCataloguePrototypeModel("football-elo-v1-candidate")).toBe(false);
  });
});
