import { createDataSource } from "@/data/mock/source";
import type { DataSource } from "@/types/datasource";

let instance: DataSource | undefined;

export function getDataSource(): DataSource {
  instance ??= createDataSource();
  return instance;
}
