import { HttpDataSource } from "@/data/http/source";
import { MockDataSource } from "@/data/mock/source";
import { getConfig, type DataResource, type DataSourceMode } from "@/lib/config";
import type { MockScenario } from "@/types/api";
import type { DataSource, DataSourceKind } from "@/types/datasource";

/**
 * Chooses the data source backing each resource.
 *
 * Views and hooks never test the environment themselves; they always read through
 * `getDataSource()`. Because routing is per resource, an endpoint can be moved from
 * fixtures to the live API through configuration alone.
 */

export interface CreateDataSourceOptions {
  /** Mock scenario to bind. Ignored by resources routed to HTTP. */
  scenario?: MockScenario;
  /** Overrides the resolved configuration. Used by tests. */
  resourceModes?: Readonly<Record<DataResource, DataSourceMode>>;
}

export function createDataSource({
  scenario = "success",
  resourceModes,
}: CreateDataSourceOptions = {}): DataSource {
  const config = getConfig();
  const modes = resourceModes ?? config.resourceModes;

  let mockSource: DataSource | undefined;
  let httpSource: DataSource | undefined;

  const from = (resource: DataResource): DataSource => {
    if (modes[resource] === "http") {
      httpSource ??= new HttpDataSource({
        baseUrl: config.apiBaseUrl,
        requestTimeoutMs: config.requestTimeoutMs,
      });
      return httpSource;
    }

    mockSource ??= new MockDataSource({ scenario });
    return mockSource;
  };

  return {
    kind: resolveKind(modes),
    getDashboard: () => from("dashboard").getDashboard(),
    getSports: () => from("sports").getSports(),
    getLeagues: (filters) => from("leagues").getLeagues(filters),
    getLeague: (id) => from("leagues").getLeague(id),
    getMatches: (filters) => from("matches").getMatches(filters),
    getMatch: (id) => from("matches").getMatch(id),
    getPicks: (filters) => from("picks").getPicks(filters),
    getFootballAiPicks: (filters) => from("football_ai_picks").getFootballAiPicks(filters),
    getValue: (filters) => from("value").getValue(filters),
    getPerformance: () => from("performance").getPerformance(),
    getTeams: (filters) => from("teams").getTeams(filters),
    getTeam: (id) => from("teams").getTeam(id),
    getPlayers: (filters) => from("players").getPlayers(filters),
    getPlayer: (id) => from("players").getPlayer(id),
    getAnalystSession: (matchId, question) =>
      from("analyst").getAnalystSession(matchId, question),
    getFootballAiAnalyst: (matchId, cutoffAt) =>
      from("football_ai_analyst").getFootballAiAnalyst(matchId, cutoffAt),
  };
}

export function resolveKind(
  modes: Readonly<Record<DataResource, DataSourceMode>>,
): DataSourceKind {
  const values = Object.values(modes);
  if (values.every((mode) => mode === "http")) return "http";
  if (values.every((mode) => mode === "mock")) return "mock";
  return "hybrid";
}

/**
 * One source per scenario. Instances are cached so React Query keeps a stable
 * `queryFn` identity across renders.
 */
const instances = new Map<MockScenario, DataSource>();

export function getDataSource(scenario: MockScenario = "success"): DataSource {
  let instance = instances.get(scenario);

  if (!instance) {
    instance = createDataSource({ scenario });
    instances.set(scenario, instance);
  }

  return instance;
}

/** Test seam: drops cached sources so a new configuration takes effect. */
export function resetDataSourceCache(): void {
  instances.clear();
}
