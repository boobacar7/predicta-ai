import {
  DataSourceError,
  isDataSourceError,
  kindFromStatus,
  toDataSourceError,
} from "@/lib/api/errors";
import { describe, expect, it } from "vitest";

describe("kindFromStatus", () => {
  it("maps documented statuses onto transport-agnostic kinds", () => {
    expect(kindFromStatus(404)).toBe("not_found");
    expect(kindFromStatus(501)).toBe("not_implemented");
    expect(kindFromStatus(500)).toBe("server");
    expect(kindFromStatus(422)).toBe("server");
  });
});

describe("retryability", () => {
  it("allows a retry for failures that could resolve on their own", () => {
    for (const kind of ["network", "server", "mock_scenario"] as const) {
      expect(new DataSourceError({ kind }).retryable).toBe(true);
    }
  });

  it("refuses a retry for failures that would repeat identically", () => {
    for (const kind of ["not_found", "invalid_response", "not_implemented"] as const) {
      expect(new DataSourceError({ kind }).retryable).toBe(false);
    }
  });

  it("refuses a retry for a 4xx problem even when the kind is server", () => {
    expect(new DataSourceError({ kind: "server", status: 422 }).retryable).toBe(false);
    expect(new DataSourceError({ kind: "server", status: 409 }).retryable).toBe(false);
    expect(new DataSourceError({ kind: "server", status: 503 }).retryable).toBe(true);
  });
});

describe("default messages", () => {
  it("provides French operator copy for every kind", () => {
    expect(new DataSourceError({ kind: "not_found" }).message).toMatch(/introuvable/);
    expect(new DataSourceError({ kind: "network" }).message).toMatch(/connexion/i);
  });

  it("prefers an explicit message over the default", () => {
    expect(new DataSourceError({ kind: "server", message: "Détail précis." }).message).toBe(
      "Détail précis.",
    );
  });
});

describe("toDataSourceError", () => {
  it("passes an already-typed error through unchanged", () => {
    const original = new DataSourceError({ kind: "not_found" });

    expect(toDataSourceError(original)).toBe(original);
  });

  it("labels an aborted request as a timeout", () => {
    const error = toDataSourceError(new DOMException("Aborted", "AbortError"));

    expect(error.kind).toBe("network");
    expect(error.message).toMatch(/délai/);
  });

  it("wraps an unexpected throw rather than letting it reach the UI raw", () => {
    const error = toDataSourceError(new TypeError("x is not a function"));

    expect(isDataSourceError(error)).toBe(true);
    expect(error.kind).toBe("network");
    expect(error.cause).toBeInstanceOf(TypeError);
  });

  it("handles a thrown non-error value", () => {
    expect(isDataSourceError(toDataSourceError("boom"))).toBe(true);
  });
});
