// Product stage configuration types

export interface ProductStageConfig {
  id: string;
  productId: string;
  stage: number;
  name: string;
  enabled: boolean;
  buildScript: string | null;
  buildTarget: string | null;
  fwRepoUrl: string | null;
  fwRepoBranch: string | null;
  mfgRepoUrl: string | null;
  mfgRepoBranch: string | null;
  buildVariant: string | null;
  configFlags: Record<string, unknown> | null;
  buildMatrix: StageBuildDef[] | null;
  testDirectory: string | null;
  testMarker: string | null;
  testTimeout: number;
  priority: number;
  blocksMerge: boolean;
  requiresFuota: boolean;
  requiresBench: boolean;
  maxDurationSec: number;
  description: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StageBuildDef {
  label: string;
  fw_type: string;
  target: string;
  variant: string;
  git_ref: string;
  config_flags?: Record<string, unknown>;
  is_version_bump?: boolean;
  base_label?: string;
  produces_cfw?: boolean;
}

export const STAGE_NAMES: Record<number, string> = {
  1: 'Smoke',
  2: 'Silicon',
  3: 'Integration',
  4: 'Nightly',
  5: 'Gate',
};

export const STAGE_DESCRIPTIONS: Record<number, string> = {
  1: 'Software tests on native_sim — no hardware required',
  2: 'Driver hardware tests on dev kits',
  3: 'Subsystem integration tests with harness instrumentation',
  4: 'Comprehensive product validation — nightly runs',
  5: 'PR gate with FUOTA verification — blocks merge',
};

export const STAGE_COLORS: Record<number, string> = {
  1: 'text-blue-400',
  2: 'text-cyan-400',
  3: 'text-amber-400',
  4: 'text-purple-400',
  5: 'text-red-400',
};
