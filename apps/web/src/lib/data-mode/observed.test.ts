import { readObservedDataMode } from "@/lib/data-mode/observed";
import { describe, expect, it } from "vitest";

describe("readObservedDataMode", () => {
  it("returns null when no envelope is on screen", () => {
    expect(readObservedDataMode([undefined, { foo: 1 }])).toBeNull();
  });

  it("surfaces mock even when a live envelope is also cached", () => {
    expect(
      readObservedDataMode([
        { data_mode: "live", generated_at: "t", request_id: "a", data: {} },
        { data_mode: "mock", generated_at: "t", request_id: "b", data: {} },
      ]),
    ).toBe("mock");
  });

  it("reports live when every envelope is live", () => {
    expect(
      readObservedDataMode([{ data_mode: "live", generated_at: "t", request_id: "a", data: {} }]),
    ).toBe("live");
  });
});
