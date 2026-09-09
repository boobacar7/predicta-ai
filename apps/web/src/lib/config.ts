export type DataSourceMode = "mock" | "http";

function readMode(): DataSourceMode {
  const value = process.env.NEXT_PUBLIC_PREDICTA_DATA_SOURCE ?? "mock";

  if (value === "mock" || value === "http") {
    return value;
  }

  throw new Error(
    `Invalid NEXT_PUBLIC_PREDICTA_DATA_SOURCE "${value}". Expected "mock" or "http".`,
  );
}

export function getDataSourceMode(): DataSourceMode {
  const mode = readMode();
  const allowMockInProd =
    process.env.NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD === "true";

  if (process.env.NODE_ENV === "production" && mode === "mock" && !allowMockInProd) {
    throw new Error(
      "Mock data source is blocked in production. Set NEXT_PUBLIC_PREDICTA_DATA_SOURCE=http or explicitly allow mocks.",
    );
  }

  return mode;
}
