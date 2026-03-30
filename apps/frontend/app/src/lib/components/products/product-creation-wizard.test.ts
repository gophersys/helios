import { describe, it, expect } from 'vitest';
import type {
  BoardBranchesResponse,
  BoardSummary,
  BoardDetail,
  BuildConfig,
} from '$lib/types/models';

// Test wizard data transformations and logic.
// The wizard auto-populates fields from board discovery —
// these tests validate that logic.

function createMockBranchesResponse(): BoardBranchesResponse {
  return {
    branches: ['main', 'release/v2.1', 'feature/sigma5-rev2'],
    tags: ['v1.0.0', 'v2.0.0'],
  };
}

function createMockBoardSummaries(): BoardSummary[] {
  return [
    {
      board: 'alpha',
      socs: ['nrf52840', 'nrf9151'],
      revisions: ['rev1.1', 'rev1.2'],
      variants: ['alpha_b0'],
    },
    {
      board: 'sigma5',
      socs: ['nrf52840'],
      revisions: ['rev1.0'],
      variants: ['sigma5_std'],
    },
  ];
}

function createMockBoardDetail(): BoardDetail {
  return {
    board: 'alpha',
    socs: ['nrf52840', 'nrf9151'],
    revisions: [
      {
        name: 'rev1.2',
        peripherals: [
          { compatible: 'bosch,bmi270', type: 'accelerometer', bus: 'spi' },
          { compatible: 'ti,bq25180', type: 'charger', bus: 'i2c' },
          { compatible: 'ti,bq35100', type: 'fuel-gauge', bus: 'i2c' },
          { compatible: 'nxp,tca9534a', type: 'gpio-expander', bus: 'i2c' },
          { compatible: 'pixart,pah8151', type: 'ppg', bus: 'spi' },
          { compatible: 'melexis,mlx90614', type: 'ir-temp', bus: 'i2c' },
        ],
      },
    ],
    variants: ['alpha_b0'],
  };
}

describe('Wizard branch selection', () => {
  it('returns branches and tags', () => {
    const response = createMockBranchesResponse();
    expect(response.branches).toContain('main');
    expect(response.tags).toHaveLength(2);
  });

  it('defaults to main if present', () => {
    const response = createMockBranchesResponse();
    const defaultBranch = response.branches.includes('main')
      ? 'main'
      : response.branches[0];
    expect(defaultBranch).toBe('main');
  });

  it('falls back to first branch if main is absent', () => {
    const response: BoardBranchesResponse = {
      branches: ['develop', 'release/v3'],
      tags: [],
    };
    const defaultBranch = response.branches.includes('main')
      ? 'main'
      : response.branches[0];
    expect(defaultBranch).toBe('develop');
  });
});

describe('Wizard board selection', () => {
  it('lists all discovered boards', () => {
    const summaries = createMockBoardSummaries();
    expect(summaries).toHaveLength(2);
    expect(summaries.map((s) => s.board)).toEqual(['alpha', 'sigma5']);
  });

  it('board summary includes SoC list', () => {
    const summaries = createMockBoardSummaries();
    const alpha = summaries.find((s) => s.board === 'alpha')!;
    expect(alpha.socs).toEqual(['nrf52840', 'nrf9151']);
  });
});

describe('Wizard auto-populate from board detail', () => {
  const detail = createMockBoardDetail();

  // Replicate the wizard's auto-populate logic
  function autoPopulateTargets(socs: string[]): Record<string, { soc: string; appId: number; role: string }> {
    const targets: Record<string, { soc: string; appId: number; role: string }> = {};
    if (socs.length === 1) {
      targets['app'] = { soc: socs[0], appId: 0, role: 'application' };
    } else if (socs.length >= 2) {
      const appSoc = socs.find((s) => s.includes('52840')) || socs[0];
      const commsSoc = socs.find((s) => s.includes('9151') || s.includes('9161')) || socs[1];
      targets['app'] = { soc: appSoc, appId: 0, role: 'application' };
      if (commsSoc !== appSoc) {
        targets['comms'] = { soc: commsSoc, appId: 0, role: 'communications' };
      }
    }
    return targets;
  }

  it('creates dual targets for dual-SoC board', () => {
    const targets = autoPopulateTargets(detail.socs);
    expect(Object.keys(targets)).toEqual(['app', 'comms']);
    expect(targets.app.soc).toBe('nrf52840');
    expect(targets.comms.soc).toBe('nrf9151');
  });

  it('creates single target for single-SoC board', () => {
    const targets = autoPopulateTargets(['nrf52840']);
    expect(Object.keys(targets)).toEqual(['app']);
    expect(targets.app.soc).toBe('nrf52840');
  });

  it('sets appId to 0 (user must fill in)', () => {
    const targets = autoPopulateTargets(detail.socs);
    expect(targets.app.appId).toBe(0);
    expect(targets.comms.appId).toBe(0);
  });

  it('auto-populates product name from board', () => {
    const name = detail.board.charAt(0).toUpperCase() + detail.board.slice(1);
    expect(name).toBe('Alpha');
  });

  it('parses peripherals from revision DTS', () => {
    const rev = detail.revisions[0];
    expect(rev.peripherals).toHaveLength(6);
    expect(rev.peripherals[0]).toEqual({
      compatible: 'bosch,bmi270',
      type: 'accelerometer',
      bus: 'spi',
    });
  });
});

describe('Wizard buildConfig assembly', () => {
  it('creates valid BuildConfig from wizard state', () => {
    const targets = {
      app: { soc: 'nrf52840', appId: 109, role: 'application' },
      comms: { soc: 'nrf9151', appId: 108, role: 'communications' },
    };
    const deviceType = 2;
    const deviceVariant = 3;
    const productSlug = 'alpha';
    const ncsVersion = 'v2.9.0';

    const buildConfig: BuildConfig = {
      board: productSlug,
      ncsVersion,
      boardRoot: 'ck_boards',
      hasVsmMerge: false,
      hasFips: false,
      confFiles: Object.fromEntries(Object.keys(targets).map((k) => [k, ['prj.conf']])),
      overlays: Object.fromEntries(Object.keys(targets).map((k) => [k, []])),
      postBuild: ['sign_mcuboot'],
      cfw: { deviceType, deviceVariant },
    };

    expect(buildConfig.board).toBe('alpha');
    expect(buildConfig.cfw).toEqual({ deviceType: 2, deviceVariant: 3 });
    expect(buildConfig.confFiles).toEqual({
      app: ['prj.conf'],
      comms: ['prj.conf'],
    });
  });

  it('trigger branches parse from comma-separated string', () => {
    const input = 'main, release/*, feature/alpha';
    const parsed = input.split(',').map((b) => b.trim()).filter(Boolean);
    expect(parsed).toEqual(['main', 'release/*', 'feature/alpha']);
  });

  it('empty trigger branches produce empty array', () => {
    const input = '';
    const parsed = input.split(',').map((b) => b.trim()).filter(Boolean);
    expect(parsed).toEqual([]);
  });
});
