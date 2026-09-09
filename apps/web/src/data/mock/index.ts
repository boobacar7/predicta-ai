/**
 * Public entry point of the mock data layer.
 *
 * Everything exported here is fictional and marked `data_mode: "mock"`. Nothing
 * outside this folder should import a fixture module directly.
 */
export { MockDataSource, type MockDataSourceOptions } from "@/data/mock/source";
export { MOCK_NOW_ISO, mockNow } from "@/data/mock/clock";
export {
  MOCK_SCENARIOS,
  MockScenarioProvider,
  useMockScenario,
  useMockScenarioControl,
} from "@/data/mock/scenario-context";
