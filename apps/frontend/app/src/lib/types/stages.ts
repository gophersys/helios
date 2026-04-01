export interface ProductStageConfig {
  id: string;
  productId: string;
  stage: number;
  name: string;
  enabled: boolean;
  boardRevisionId: string | null;
  boardRevision: { id: string; version: string; ckBoardsName: string } | null;
  watchBranch: string | null;
  triggerTypes: string[];
  signingKeyId: string | null;
  signingKey: { id: string; name: string; type: string } | null;
  createdAt: string;
  updatedAt: string;
}

export interface Secret {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

export const STAGE_NAMES: Record<number, string> = {
  1: 'Smoke',
  2: 'Silicon',
  3: 'Integration',
  4: 'Nightly',
  5: 'FUOTA',
};

export const STAGE_DESCRIPTIONS: Record<number, string> = {
  1: 'Quick sanity — boot, basic comms, no hardware needed',
  2: 'Hardware validation — power, peripherals, sensors',
  3: 'End-to-end with cloud connectivity',
  4: 'Full regression suite on mainline',
  5: 'OTA firmware update cycle test',
};

export const STAGE_BUILD_COUNTS: Record<number, number> = {
  1: 2,
  2: 3,
  3: 4,
  4: 6,
  5: 8,
};
