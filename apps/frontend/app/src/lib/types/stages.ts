export type StageType = 'VALIDATION' | 'MANUFACTURING';

export interface ProductStageConfig {
  id: string;
  productId: string;
  type: StageType;
  stage: number;
  name: string;
  enabled: boolean;
  boardRevisionId: string | null;
  boardRevision: { id: string; version: string; ckBoardsName: string } | null;
  watchBranch: string | null;
  triggerTypes: string[];
  signingKeyId: string | null;
  signingKey: { id: string; name: string; type: string } | null;
  buildMatrix?: import('$lib/types/models').StageBuildMatrixEntry[];
  // Repo URLs resolved from product codebases
  fwRepoUrl?: string | null;
  fwRepoBranch?: string | null;
  mfgRepoUrl?: string | null;
  mfgRepoBranch?: string | null;
  // Build trigger response fields
  buildTriggered?: boolean;
  buildRunId?: string | null;
  buildError?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Secret {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

export const STAGE_NAMES: Record<string, Record<number, string>> = {
  VALIDATION: { 1: 'Smoke', 2: 'Driver', 3: 'Integration', 4: 'Regression', 5: 'FUOTA' },
  MANUFACTURING: { 1: 'Manufacturing' },
};

export const STAGE_DESCRIPTIONS: Record<string, Record<number, string>> = {
  VALIDATION: {
    1: 'Quick sanity — boot, basic comms, no hardware needed',
    2: 'Hardware validation — power, peripherals, sensors',
    3: 'End-to-end with cloud connectivity',
    4: 'Full regression suite on mainline',
    5: 'OTA firmware update cycle test',
  },
  MANUFACTURING: {
    1: 'Production flashing and POST',
  },
};

// Flat helpers for backward compat
export function stageName(type: StageType, stage: number): string {
  return STAGE_NAMES[type]?.[stage] ?? `Stage ${stage}`;
}
export function stageDescription(type: StageType, stage: number): string {
  return STAGE_DESCRIPTIONS[type]?.[stage] ?? '';
}

export const STAGE_BUILD_COUNTS: Record<number, number> = {
  1: 2,
  2: 3,
  3: 4,
  4: 6,
  5: 8,
};
