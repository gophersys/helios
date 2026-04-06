// CI / Build pipeline types

export type BuildJobStatus = 'QUEUED' | 'BLOCKED' | 'CLONING' | 'BUILDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'CACHED';
export type PipelineStage = 'BUILD' | 'FLASH' | 'VALIDATE';
export type BuildRunStageStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

export interface BuildArtifact {
  id: string;
  buildJobId?: string;
  name: string;
  storageKey: string;
  sizeBytes: number;
  checksum: string | null;
  contentType?: string | null;
  downloadUrl?: string;
  createdAt: string;
}

export interface BuildJob {
  id: string;
  product: string;
  board: string;
  target: string;
  variant: string;
  branch: string;
  commitSha: string;
  status: BuildJobStatus;
  versionString: string | null;
  buildLog: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  durationSeconds: number | null;
  createdAt: string;
  triggerTypes: string;  // "worker" | "manual" | "webhook"
  notes?: string | null;
  artifacts: BuildArtifact[];
  // Stage matrix fields
  matrixLabel?: MatrixLabel | string | null;
  matrixIndex?: number | null;
  buildNum?: number | null;
  // Build cache fields
  buildFingerprint?: string | null;
  configFlags?: Record<string, unknown> | null;
  reusedFromId?: string | null;
  // Error detail from failed builds
  errorMessage?: string | null;
  // Worker assignment
  workerId?: string | null;
}

export interface BuildRunStageInfo {
  stage: PipelineStage;
  status: BuildRunStageStatus;
  startedAt: string | null;
  finishedAt: string | null;
  detail: string | null;
}

// Build matrix labels — FUOTA pipeline uses 6 builds, all release variant.
// "Verbose" builds have CONFIG_LOG=y forced on (UART output for version detection).
// "Quiet" builds are standard release (no UART logs, production-like).
// All CFW flags are -B or -BM — no -D flag, avoiding CoreCloud D-flag stripping.
export type MatrixLabel =
  // Current labels (from stage_defs.py)
  | 'MFG_BASE' | 'MFG_BUMP'
  | 'FUT_VERBOSE_A' | 'FUT_VERBOSE_B'
  | 'FUT_QUIET_A' | 'FUT_QUIET_B'
  | 'MAIN_BASELINE' | 'MAIN_MERGED'
  // Nightly labels
  | 'MFG_FLASH'
  | 'PROD_VERBOSE' | 'PROD_VERBOSE_BUMP'
  | 'PROD_QUIET' | 'PROD_QUIET_BUMP'
  // Legacy labels
  | 'FLASH_BASE_DEBUG' | 'FLASH_BASE_RELEASE'
  | 'FUOTA_TARGET_DEBUG' | 'FUOTA_TARGET_RELEASE'
  | 'FUT_DEBUG_A' | 'FUT_DEBUG_B'
  | 'FUT_RELEASE_A' | 'FUT_RELEASE_B';

export interface BuildRunBuildSummary {
  id: string;
  product: string;
  status: BuildJobStatus;
  variant: string;
  buildNum: number;
  versionString: string | null;
  commitSha?: string | null;
  durationSeconds: number | null;
  artifactCount: number;
  // Stage 4 matrix fields
  matrixLabel?: MatrixLabel | null;
  matrixIndex?: number | null;
  versionBump?: boolean;
  baseJobId?: string | null;
  // Build cache fields
  reusedFromId?: string | null;
}

// Human-readable labels for FUOTA matrix (FUOTA flow order)
export const MATRIX_LABEL_DISPLAY: Record<MatrixLabel, {
  name: string;
  description: string;
  group: string;
  groupTitle: string;
  fuotaStep: number;
  priority: number;  // Lower = higher priority (build first)
}> = {
  // ── MFG firmware — two versions for MFG-to-MFG FUOTA test ──
  MFG_FLASH: {
    name: 'MFG Flash',
    description: 'Manufacturing firmware flashed via J-Link (FUOTA base)',
    group: 'mfg',
    groupTitle: 'Manufacturing',
    fuotaStep: 1,
    priority: 0,
  },
  MFG_BUMP: {
    name: 'MFG Bump',
    description: 'MFG firmware with bumped version (MFG→MFG FUOTA target)',
    group: 'mfg',
    groupTitle: 'Manufacturing',
    fuotaStep: 1,
    priority: 1,
  },
  // ── Prod Verbose — release + CONFIG_LOG=y for UART version detection ──
  PROD_VERBOSE: {
    name: 'Prod Verbose',
    description: 'Production firmware with UART logging (release flags, no D-flag)',
    group: 'prod_verbose',
    groupTitle: 'Prod (Verbose)',
    fuotaStep: 2,
    priority: 2,
  },
  PROD_VERBOSE_BUMP: {
    name: 'Prod Verbose Bump',
    description: 'Verbose prod with bumped version (Prod→Prod logged FUOTA target)',
    group: 'prod_verbose',
    groupTitle: 'Prod (Verbose)',
    fuotaStep: 2,
    priority: 3,
  },
  // ── Prod Quiet — standard release, no UART logs ──
  PROD_QUIET: {
    name: 'Prod Quiet',
    description: 'Production firmware without UART logging (standard release)',
    group: 'prod_quiet',
    groupTitle: 'Prod (Quiet)',
    fuotaStep: 3,
    priority: 4,
  },
  PROD_QUIET_BUMP: {
    name: 'Prod Quiet Bump',
    description: 'Quiet prod with bumped version (Prod→Prod silent FUOTA target)',
    group: 'prod_quiet',
    groupTitle: 'Prod (Quiet)',
    fuotaStep: 3,
    priority: 5,
  },
  // ── Current FUOTA labels (from stage_defs.py) ──
  MFG_BASE: {
    name: 'MFG Flash',
    description: 'Manufacturing firmware — J-Link flash base for FUOTA',
    group: 'mfg', groupTitle: '1. Manufacturing', fuotaStep: 1, priority: 0,
  },
  FUT_VERBOSE_A: {
    name: 'Verbose A',
    description: 'App firmware with UART logging — FUOTA source',
    group: 'verbose', groupTitle: '2. App Verbose (UART Logging)', fuotaStep: 2, priority: 6,
  },
  FUT_VERBOSE_B: {
    name: 'Verbose B',
    description: 'App firmware with UART logging — FUOTA target (version bumped)',
    group: 'verbose', groupTitle: '2. App Verbose (UART Logging)', fuotaStep: 2, priority: 7,
  },
  FUT_QUIET_A: {
    name: 'Quiet A',
    description: 'App firmware without UART — FUOTA source',
    group: 'quiet', groupTitle: '3. App Quiet (No Logging)', fuotaStep: 3, priority: 8,
  },
  FUT_QUIET_B: {
    name: 'Quiet B',
    description: 'App firmware without UART — FUOTA target (version bumped)',
    group: 'quiet', groupTitle: '3. App Quiet (No Logging)', fuotaStep: 3, priority: 9,
  },
  MAIN_BASELINE: {
    name: 'Mainline Base',
    description: 'Mainline debug build — regression baseline (boot check)',
    group: 'mainline', groupTitle: '4. Mainline Regression', fuotaStep: 4, priority: 10,
  },
  MAIN_MERGED: {
    name: 'Mainline Merged',
    description: 'Post-merge build — verify merged code compiles and boots',
    group: 'mainline', groupTitle: '4. Mainline Regression', fuotaStep: 4, priority: 11,
  },
  // ── Legacy labels (backwards compat with old pipelines) ──
  FLASH_BASE_DEBUG: {
    name: 'Baseline Debug', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FLASH_BASE_RELEASE: {
    name: 'Baseline Release', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUOTA_TARGET_DEBUG: {
    name: 'FUOTA Debug', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUOTA_TARGET_RELEASE: {
    name: 'FUOTA Release', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUT_DEBUG_A: {
    name: 'Debug v1', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUT_DEBUG_B: {
    name: 'Debug v2', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUT_RELEASE_A: {
    name: 'Release v1', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
  FUT_RELEASE_B: {
    name: 'Release v2', description: 'Legacy', group: 'legacy',
    groupTitle: 'Legacy', fuotaStep: 99, priority: 99,
  },
};

// FUOTA validation order: which firmware transitions to which
// All transitions use release-flagged firmware (-B or -BM). No D-flag.
export const FUOTA_TRANSITIONS: Array<{ from: MatrixLabel; to: MatrixLabel; purpose: string }> = [
  { from: 'MFG_BASE', to: 'MFG_BUMP', purpose: 'MFG→MFG FUOTA (version bump sanity)' },
  { from: 'MFG_BASE', to: 'FUT_VERBOSE_A', purpose: 'MFG→App FUOTA (with UART logs)' },
  { from: 'FUT_VERBOSE_A', to: 'FUT_VERBOSE_B', purpose: 'App→App verbose FUOTA (version bump)' },
  { from: 'MFG_BASE', to: 'FUT_QUIET_A', purpose: 'MFG→App FUOTA (no logs, cloud-only check)' },
  { from: 'FUT_QUIET_A', to: 'FUT_QUIET_B', purpose: 'App→App quiet FUOTA (version bump)' },
];

export interface BuildRunDetail {
  id: string;
  name: string;
  product: string;
  productId?: string;
  board: string;
  branch: string;
  commitSha: string | null;
  status: string;
  triggerType: string;
  stage?: number | null;
  expectedBuilds: number;
  completedBuilds: number;
  validationRunId: string | null;
  autoValidate: boolean;
  // PR context (first-class fields for filtering/grouping)
  prNumber?: number | null;
  prTitle?: string | null;
  prAuthor?: string | null;
  sourceBranch?: string | null;
  targetBranch?: string | null;
  prUrl?: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  updatedAt: string;
  builds?: BuildRunBuildSummary[];
  // Build matrix mode (validation stage)
  matrixMode?: 'smoke' | 'silicon' | 'integration' | 'nightly' | 'fuota' | null;
  buildMatrix?: {
    mode: string;
    product: string;
    mainFw?: string;
    mfgFw?: string;
    prBranch?: string;
    prCommit?: string;
    mainCommit?: string;
  } | null;
  // Computed for UI compatibility
  buildJob?: BuildJob | null;
  validationRun?: { id: string; name: string; status: string } | null;
  stages?: BuildRunStageInfo[];
  // Trigger-specific data (modem firmware, etc.)
  triggerData?: {
    modemFirmware?: {
      name: string;
      version: string;
      storageKey: string;
    };
  } | null;
}

// PR Pipeline — shows a PR's validation status across all stages
export interface PrStageStatus {
  status: string;
  buildRunId: string;
  commitSha: string | null;
  completedBuilds: number;
  expectedBuilds: number;
  duration: number | null;
  createdAt: string;
}

export interface PrPipelineSummary {
  prNumber: number;
  prTitle: string | null;
  prAuthor: string | null;
  prUrl: string | null;
  product: string;
  productId: string;
  sourceBranch: string | null;
  targetBranch: string | null;
  latestCommit: string | null;
  updatedAt: string;
  stages: Record<number, PrStageStatus | null>;
}

// Build system summary stats
export interface BuildSummary {
  activeRuns: number;
  queuedJobs: number;
  buildingJobs: number;
  successRate24h: number | null;
  avgDurationSeconds: number | null;
  byStage: Array<{
    stage: number;
    name: string;
    active: number;
    success24h: number;
    failed24h: number;
  }>;
}

// Validation stage display info
export type ValidationStage = 'smoke' | 'silicon' | 'integration' | 'nightly' | 'fuota';

export const STAGE_DISPLAY: Record<ValidationStage, { name: string; description: string; buildCount: number; color: string }> = {
  smoke: {
    name: 'Smoke',
    description: 'Quick native sim tests',
    buildCount: 1,
    color: 'bg-surface-2 text-text-secondary',
  },
  silicon: {
    name: 'Silicon',
    description: 'Driver tests on real hardware',
    buildCount: 1,
    color: 'bg-surface-2 text-text-secondary',
  },
  integration: {
    name: 'Integration',
    description: 'System integration tests',
    buildCount: 1,
    color: 'bg-surface-2 text-text-secondary',
  },
  nightly: {
    name: 'Nightly',
    description: 'Long-running validation tests',
    buildCount: 2,
    color: 'bg-warning-muted text-warning',
  },
  fuota: {
    name: 'FUOTA',
    description: 'Full firmware update chain testing',
    buildCount: 8,
    color: 'bg-info-muted text-info',
  },
};

export interface TriggerBuildConfig {
  product: string;
  board: string;
  target: string;
  variant: string;
  branch: string;
  commitSha?: string;
}

export interface TriggerBuildRunConfig {
  product: string;
  board: string;
  target: string;
  variant: string;
  branch: string;
  commitSha?: string;
  validate?: boolean;
  nodeId?: string;
  serialNumber?: string;
}
