// CI / Build pipeline types

export type BuildJobStatus = 'QUEUED' | 'BLOCKED' | 'BUILDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';
export type PipelineStage = 'BUILD' | 'FLASH' | 'VALIDATE';
export type PipelineStageStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

export interface BuildJobArtifact {
  id: string;
  name: string;
  storageKey: string;
  sizeBytes: number;
  checksum: string | null;
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
}

export interface PipelineStageInfo {
  stage: PipelineStage;
  status: PipelineStageStatus;
  startedAt: string | null;
  finishedAt: string | null;
  detail: string | null;
}

// Stage 4 build matrix labels
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

// Human-readable labels for Stage 4 matrix (FUOTA flow order)
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
  // Stage 4 matrix mode
  matrixMode?: 'legacy' | 'stage4' | 'quick' | null;
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
