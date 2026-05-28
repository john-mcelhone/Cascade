/**
 * Barrel export for the Cascade web API surface. Keeps page-level imports
 * tidy and gives us a single place to swap implementations.
 */

export { ApiError, getApiBaseUrl, getApiClient, getMockApiClient } from "./client";
export type * from "./types";
export {
  jobEventsPath,
  jobEventsUrl,
  useEventStream,
  useJobPolling,
  useJobStream,
} from "./sse";
export * from "./hooks";
