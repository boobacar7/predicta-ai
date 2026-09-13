import { QueryBoundary } from "@/components/domain/query-boundary";
import { DataSourceError } from "@/lib/api/errors";
import type { Envelope } from "@/types/api";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

interface Payload {
  items: string[];
}

function envelope(items: string[]): Envelope<Payload> {
  return {
    data_mode: "mock",
    generated_at: "2026-09-09T18:00:00.000Z",
    request_id: "req_test",
    data: { items },
  };
}

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function Subject({
  queryFn,
  enabled = true,
  withEmpty = true,
}: {
  queryFn: () => Promise<Envelope<Payload>>;
  enabled?: boolean;
  withEmpty?: boolean;
}) {
  const query = useQuery({ queryKey: ["subject", queryFn, enabled], queryFn, enabled });

  return (
    <QueryBoundary
      query={query}
      skeleton={<p>Chargement</p>}
      idle={<p>En attente</p>}
      isEmpty={withEmpty ? (data) => data.items.length === 0 : undefined}
      empty={
        withEmpty
          ? { title: "Aucun résultat", description: "Rien ne correspond à ce filtre." }
          : undefined
      }
      quality={(data) =>
        data.items.includes("stale")
          ? {
              availability: "stale",
              source: "test",
              observed_at: "2026-09-09T10:00:00.000Z",
              freshness: "stale",
              note: null,
            }
          : null
      }
    >
      {(data) => <p>{data.items.join(", ")}</p>}
    </QueryBoundary>
  );
}

function renderSubject(props: Parameters<typeof Subject>[0]) {
  return render(
    <Wrapper>
      <Subject {...props} />
    </Wrapper>,
  );
}

describe("loading", () => {
  it("shows the skeleton before the first response", () => {
    renderSubject({ queryFn: () => new Promise(() => {}) });

    expect(screen.getByText("Chargement")).toBeInTheDocument();
  });

  it("shows the idle slot instead of a skeleton when the query is disabled", () => {
    renderSubject({ queryFn: async () => envelope(["a"]), enabled: false });

    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.queryByText("Chargement")).not.toBeInTheDocument();
  });
});

describe("success", () => {
  it("renders the payload", async () => {
    renderSubject({ queryFn: async () => envelope(["Northgate", "Harbor"]) });

    expect(await screen.findByText("Northgate, Harbor")).toBeInTheDocument();
  });

  it("keeps a stale payload visible and states that its freshness is not guaranteed", async () => {
    renderSubject({ queryFn: async () => envelope(["stale"]) });

    expect(await screen.findByText("stale")).toBeInTheDocument();
    expect(screen.getByText(/fraîcheur n'est plus garantie/)).toBeInTheDocument();
  });
});

describe("empty", () => {
  it("distinguishes no results from an error", async () => {
    renderSubject({ queryFn: async () => envelope([]) });

    expect(await screen.findByText("Aucun résultat")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders the payload when no emptiness rule is declared", async () => {
    renderSubject({ queryFn: async () => envelope([]), withEmpty: false });

    await waitFor(() => expect(screen.queryByText("Chargement")).not.toBeInTheDocument());
    expect(screen.queryByText("Aucun résultat")).not.toBeInTheDocument();
  });
});

describe("error", () => {
  it("surfaces the message of a typed data-layer error", async () => {
    renderSubject({
      queryFn: async () => {
        throw new DataSourceError({ kind: "server", message: "Le service a renvoyé une erreur." });
      },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Le service a renvoyé une erreur.");
  });

  it("offers a retry for a transport failure and refetches when used", async () => {
    const queryFn = vi
      .fn<() => Promise<Envelope<Payload>>>()
      .mockRejectedValueOnce(new DataSourceError({ kind: "network" }))
      .mockResolvedValue(envelope(["Recovered"]));

    renderSubject({ queryFn });

    await userEvent.click(await screen.findByRole("button", { name: "Réessayer" }));

    expect(await screen.findByText("Recovered")).toBeInTheDocument();
  });

  /**
   * Retrying a 404 or a contract violation would fail identically, so offering
   * the button would only invite a pointless second failure.
   */
  it("offers a login link instead of retry for an expired session", async () => {
    renderSubject({
      queryFn: async () => {
        throw new DataSourceError({ kind: "unauthorized" });
      },
    });

    expect(await screen.findByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("offers no retry for an error that cannot succeed on a second attempt", async () => {
    renderSubject({
      queryFn: async () => {
        throw new DataSourceError({ kind: "not_found" });
      },
    });

    await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("shows the request id when the API provided one", async () => {
    renderSubject({
      queryFn: async () => {
        throw new DataSourceError({ kind: "server", requestId: "req_abc123" });
      },
    });

    expect(await screen.findByText(/req_abc123/)).toBeInTheDocument();
  });
});
