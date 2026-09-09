import assert from "node:assert/strict";
import test from "node:test";
import { formatPoints, formatProbability } from "./numbers.ts";

test("formatProbability uses French percent formatting", () => {
  assert.equal(formatProbability(0.68), "68 %");
  assert.equal(formatProbability(null), "Indisponible");
});

test("formatPoints never treats missing as zero", () => {
  assert.equal(formatPoints(null), "Indisponible");
  assert.equal(formatPoints(0.072), "+7,2 pts");
});
