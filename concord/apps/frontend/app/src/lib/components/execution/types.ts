/**
 * Shared types for the test execution UI (validation + manufacturing).
 *
 * Re-exports from validation modules for backward compat, plus any
 * execution-specific types needed by the shared widget.
 */

// ── Telemetry sample types ───────────────────────────────────
export type {
  PowerSample,
  JoulescopeSample,
  AccelSample,
} from '$lib/components/validation/types';

// ── Time / telemetry manifest types ──────────────────────────
export type {
  TimeRange,
  StepInfo,
  ChannelInfo,
  TelemetryManifest,
} from '$lib/components/validation/time-context';

// ── Live test / stage types ──────────────────────────────────
export type {
  LiveTest,
  Stage,
  Artifact,
  BuildJob,
  TimestampedLine,
} from '$lib/components/validation/run-context.svelte';
