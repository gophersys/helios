/**
 * `@eden/visualization` — the codeinsight `Report` types barrel (the consumer half of the contract
 * seam). One concept, one home (10 §9): the wire shape is owned by the Go `codeinsight.Report`;
 * these are the cited TypeScript projection (see ./report.ts). Pure re-export, no logic.
 */
export type {
  Report,
  RepositoryRef,
  Window,
  Entity,
  Coupling,
  Ownership,
  DoraKeys,
  Summary,
  TrendPoint,
  TrendSeries,
  View,
} from './report.js';
