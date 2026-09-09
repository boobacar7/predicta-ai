import { createHttpDataSource } from "@/data/mock/source";
import type { DataSource } from "@/types/datasource";

/**
 * HTTP datasource stub.
 * The Frontend agent should replace this module with the generated OpenAPI client.
 */
export function httpDataSource(): DataSource {
  return createHttpDataSource();
}
