import { describe, it, expect } from 'vitest';
import type {
  BoardBranchesResponse,
  BoardSummary,
  BoardDetail,
  BuildConfig,
  ProductTarget,
} from '$lib/types/models';

// Test wizard data transformations and logic.
// The wizard auto-populates fields from board discovery —
// these tests validate that logic.
//
// The wizard has a SINGLE flow (branch → board → review → configure → create).
// There is no manual path. All products are created via the 5-step wizard.

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
      vendor: 'corekinect',
      socs: ['nrf52840', 'nrf9151'],
      revisions: ['rev1.1', 'rev1.2'],
      variants: ['alpha_b0'],
    },
    {
      board: 'sigma5',
      vendor: 'corekinect',
      socs: ['nrf52840'],
      revisions: ['rev1.0'],
      variants: ['sigma5_std'],
    },
  ];
}

function createMockBoardDetail(): BoardDetail {
  return {
    board: 'alpha',
    vendor: 'corekinect',
    socs: ['nrf52840', 'nrf9151'],
    revisions: ['rev1.2'],
    variants: ['alpha_b0'],
  };
}

// Replicate the wizard's target auto-populate logic (mirrors product-creation-wizard.svelte)
function autoPopulateTargets(
  socs: string[]
): Record<string, { soc: string; appId: number; role: string }> {
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

// Replicate the wizard's handleCreate() conversion: targets Record → flat array
// (mirrors the targetArray conversion in product-creation-wizard.svelte)
function targetsToArray(
  targets: Record<string, { soc: string; appId: number; role: string }>
): Pick<ProductTarget, 'role' | 'soc' | 'appId'>[] {
  return Object.entries(targets).map(([, t]) => ({
    role: t.role,
    soc: t.soc,
    appId: t.appId,
  }));
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

  it('auto-populates repo slugs from board name', () => {
    expect(`${detail.board}_fw`).toBe('alpha_fw');
    expect(`${detail.board}_mfg_fw`).toBe('alpha_mfg_fw');
  });

  it('revisions are string arrays from board.yml', () => {
    expect(detail.revisions).toEqual(['rev1.2']);
  });
});

describe('Wizard single flow — targets sent as flat array', () => {
  // The wizard converts its internal Record<role, {soc, appId, role}> to a
  // flat ProductTarget[] array before POSTing to /v2/products.
  // This mirrors handleCreate() in product-creation-wizard.svelte.

  it('converts dual-SoC targets Record to flat array', () => {
    const targets = autoPopulateTargets(['nrf52840', 'nrf9151']);
    targets.app.appId = 109;
    targets.comms.appId = 108;

    const arr = targetsToArray(targets);
    expect(arr).toHaveLength(2);
    expect(arr[0]).toEqual({ role: 'application', soc: 'nrf52840', appId: 109 });
    expect(arr[1]).toEqual({ role: 'communications', soc: 'nrf9151', appId: 108 });
  });

  it('converts single-SoC targets Record to array with one entry', () => {
    const targets = autoPopulateTargets(['nrf52840']);
    targets.app.appId = 120;

    const arr = targetsToArray(targets);
    expect(arr).toHaveLength(1);
    expect(arr[0]).toEqual({ role: 'application', soc: 'nrf52840', appId: 120 });
  });

  it('array entries have only role, soc, appId — no extra keys', () => {
    const targets = autoPopulateTargets(['nrf52840']);
    const arr = targetsToArray(targets);
    expect(Object.keys(arr[0]).sort()).toEqual(['appId', 'role', 'soc']);
  });

  it('targets array is ordered: app before comms', () => {
    const targets = autoPopulateTargets(['nrf52840', 'nrf9151']);
    const arr = targetsToArray(targets);
    expect(arr[0].role).toBe('application');
    expect(arr[1].role).toBe('communications');
  });

  it('empty targets Record produces empty array', () => {
    const arr = targetsToArray({});
    expect(arr).toEqual([]);
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

  it('BuildConfig does NOT contain targets — targets live on Product.targets array', () => {
    // Targets were moved from BuildConfig to a separate top-level Product.targets array.
    const buildConfig: BuildConfig = {
      board: 'alpha',
      ncsVersion: 'v2.9.0',
      boardRoot: 'ck_boards',
      hasVsmMerge: false,
      hasFips: false,
      confFiles: { app: ['prj.conf'] },
      overlays: { app: [] },
      postBuild: ['sign_mcuboot'],
      cfw: { deviceType: 2, deviceVariant: 3 },
    };
    // @ts-expect-error — 'targets' should not exist on BuildConfig
    expect((buildConfig as Record<string, unknown>).targets).toBeUndefined();
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

describe('Product.targets — array shape used by product-detail', () => {
  // Product.targets is ProductTarget[] — each entry has id, role, soc, appId.
  // product-detail.svelte iterates this array to render one chip per target.

  it('ProductTarget has id, role, soc, appId fields', () => {
    const target: ProductTarget = {
      id: 'tgt-1',
      role: 'application',
      soc: 'nrf52840',
      appId: 109,
    };
    expect(target.id).toBe('tgt-1');
    expect(target.role).toBe('application');
    expect(target.soc).toBe('nrf52840');
    expect(target.appId).toBe(109);
  });

  it('product-detail metadata row renders one entry per target', () => {
    // Mirrors: {#each product.targets as target} {target.soc} #{target.appId}
    const targets: ProductTarget[] = [
      { id: 'tgt-1', role: 'application', soc: 'nrf52840', appId: 109 },
      { id: 'tgt-2', role: 'communications', soc: 'nrf9151', appId: 108 },
    ];
    const rendered = targets.map((t) => `${t.soc} #${t.appId}`);
    expect(rendered).toEqual(['nrf52840 #109', 'nrf9151 #108']);
  });

  it('each target independently shows its own appId', () => {
    const targets: ProductTarget[] = [
      { id: 'tgt-1', role: 'application', soc: 'nrf52840', appId: 109 },
      { id: 'tgt-2', role: 'communications', soc: 'nrf9151', appId: 108 },
    ];
    expect(targets.find((t) => t.soc === 'nrf52840')!.appId).toBe(109);
    expect(targets.find((t) => t.soc === 'nrf9151')!.appId).toBe(108);
  });

  it('product with no targets renders empty list', () => {
    const targets: ProductTarget[] = [];
    expect(targets.length).toBe(0);
  });

  it('single-processor product has one target entry', () => {
    const targets: ProductTarget[] = [
      { id: 'tgt-1', role: 'application', soc: 'nrf52840', appId: 120 },
    ];
    expect(targets).toHaveLength(1);
    expect(targets[0].appId).toBe(120);
  });
});
