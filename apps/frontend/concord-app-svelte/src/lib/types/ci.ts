// CI / Build pipeline types

export type BuildJobStatus = 'QUEUED' | 'BLOCKED' | 'BUILDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';
export type PipelineStage = 'BUILD' | 'FLASH' | 'VALIDATE';
export type PipelineStageStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

export interface BuildJobArtifact {
  id: string;
  buildJobId?: string;
  name: string;
  storageKey: string;
  sizeBytes: number;
  checksum: string | null;
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
  artifacts: BuildJobArtifact[];
  // Stage matrix fields
  matrixLabel?: MatrixLabel | string | null;
  matrixIndex?: number | null;
  buildNum?: number | null;
  // Build cache fields
  buildFingerprint?: string | null;
  configFlags?: Record<string, unknown> | null;
  reusedFromId?: string | null;
}

export interface PipelineStageInfo {
  stage: PipelineStage;
  status: PipelineStageStatus;
  startedAt: string | null;
  finishedAt: string | null;
  detail: string | null;
}

// Build matrix labels (FUOTA mode uses all, nightly uses subset)
export type MatrixLabel =
  | 'MFG_BASE' | 'MFG_BUMP'
  | 'FUT_DEBUG_A' | 'FUT_DEBUG_B'
  | 'FUT_RELEASE_A' | 'FUT_RELEASE_B'
  | 'MAIN_BASELINE' | 'MAIN_MERGED';

export interface PipelineBuildSummary {
  id: string;
  product: string;
  status: BuildJobStatus;
  variant: string;
  buildNum: number;
  versionString: string | null;
  durationSeconds: number | null;
  artifactCount: number;
  // Stage 4 matrix fields
  matrixLabel?: MatrixLabel | null;
  matrixIndex?: number | null;
  versionBump?: boolean;
  baseJobId?: string | null;
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
  // Step 1: Factory flash (J-Link, highest priority)
  MFG_BASE: {
    name: 'Mfg v1',
    description: 'Manufacturing firmware for J-Link flash',
    group: 'factory',
    groupTitle: 'Step 1: Factory Flash',
    fuotaStep: 1,
    priority: 0,
  },
  MFG_BUMP: {
    name: 'Mfg v2',
    description: 'Mfg firmware +1 for FUOTA sanity test',
    group: 'factory',
    groupTitle: 'Step 1: Factory Flash',
    fuotaStep: 1,
    priority: 1,
  },
  // Step 2: Debug FUOTA (can start validation early)
  FUT_DEBUG_A: {
    name: 'Debug v1',
    description: 'Debug firmware under test',
    group: 'debug',
    groupTitle: 'Step 2: Debug FUOTA',
    fuotaStep: 2,
    priority: 2,
  },
  FUT_DEBUG_B: {
    name: 'Debug v2',
    description: 'Debug firmware +1 for FUOTA test',
    group: 'debug',
    groupTitle: 'Step 2: Debug FUOTA',
    fuotaStep: 2,
    priority: 3,
  },
  // Step 3: Release FUOTA
  FUT_RELEASE_A: {
    name: 'Release v1',
    description: 'Release firmware under test (shipping binary)',
    group: 'release',
    groupTitle: 'Step 3: Release FUOTA',
    fuotaStep: 3,
    priority: 4,
  },
  FUT_RELEASE_B: {
    name: 'Release v2',
    description: 'Release firmware +1 for FUOTA test',
    group: 'release',
    groupTitle: 'Step 3: Release FUOTA',
    fuotaStep: 3,
    priority: 5,
  },
  // Step 4: Field upgrade path (can potentially reuse existing baseline)
  MAIN_BASELINE: {
    name: 'Baseline',
    description: 'Current main branch release (may reuse existing)',
    group: 'baseline',
    groupTitle: 'Step 4: Field Upgrade',
    fuotaStep: 4,
    priority: 6,
  },
  MAIN_MERGED: {
    name: 'Merged',
    description: 'Simulated PR merge for field upgrade test',
    group: 'baseline',
    groupTitle: 'Step 4: Field Upgrade',
    fuotaStep: 4,
    priority: 7,
  },
};

// FUOTA validation order: which firmware transitions to which
export const FUOTA_TRANSITIONS: Array<{ from: MatrixLabel; to: MatrixLabel; purpose: string }> = [
  { from: 'MFG_BASE', to: 'MFG_BUMP', purpose: 'FUOTA sanity (same code, version bump)' },
  { from: 'MFG_BUMP', to: 'FUT_DEBUG_A', purpose: 'Factory → production transition' },
  { from: 'FUT_DEBUG_A', to: 'FUT_DEBUG_B', purpose: 'Debug FUOTA test' },
  { from: 'FUT_DEBUG_B', to: 'FUT_RELEASE_A', purpose: 'Debug → release transition' },
  { from: 'FUT_RELEASE_A', to: 'FUT_RELEASE_B', purpose: 'Release FUOTA test' },
  { from: 'MAIN_BASELINE', to: 'MAIN_MERGED', purpose: 'Field upgrade path' },
];

export interface Pipeline {
  id: string;
  name: string;
  product: string;
  board: string;
  branch: string;
  commitSha: string | null;
  status: string;
  triggerType: string;
  expectedBuilds: number;
  completedBuilds: number;
  validationRunId: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  updatedAt: string;
  builds?: PipelineBuildSummary[];
  // Build matrix mode (validation stage)
  matrixMode?: 'smoke' | 'silicon' | 'integration' | 'nightly' | 'fuota' | null;
  buildMatrix?: {
    mode: string;
    product: string;
    prBranch?: string;
    prCommit?: string;
    mainCommit?: string;
  } | null;
  // Computed for UI compatibility
  buildJob?: BuildJob | null;
  validationRun?: { id: string; name: string; status: string } | null;
  stages?: PipelineStageInfo[];
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

export interface TriggerPipelineConfig {
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
