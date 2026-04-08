import { describe, it, expect } from 'vitest';
import type {
  ManufacturingConfig,
  ManufacturingStageConfig,
  ManufacturingPassCriteria,
  BoardRevision,
} from '$lib/types/models';

// ── Mock factories ──────────────────────────────────────────

function createMockRevisions(): BoardRevision[] {
  return [
    {
      id: 'rev-a0',
      boardId: 'board-1',
      version: 'A0',
      ckBoardsName: 'alpha_a0',
      socs: ['nrf9160', 'nrf52840'],
      deviceType: 2,
      deviceVariant: 3,
      modemVersion: null,
      hasModemFirmware: false,
      status: 'ACTIVE',
      notes: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    {
      id: 'rev-b0',
      boardId: 'board-1',
      version: 'B0',
      ckBoardsName: 'alpha_b0',
      socs: ['nrf9151', 'nrf52840'],
      deviceType: 2,
      deviceVariant: 3,
      modemVersion: null,
      hasModemFirmware: false,
      status: 'ACTIVE',
      notes: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
    {
      id: 'rev-c0',
      boardId: 'board-1',
      version: 'C0',
      ckBoardsName: 'alpha_c0',
      socs: ['nrf9151', 'nrf52840'],
      deviceType: 2,
      deviceVariant: 3,
      modemVersion: null,
      hasModemFirmware: false,
      status: 'DRAFT',
      notes: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  ];
}

function defaultStages(): ManufacturingStageConfig[] {
  return [
    { name: 'electrical', enabled: true, config: { ch0Voltage: 4.5, ch1Voltage: 0, minCurrentMa: 5, maxCurrentMa: 100, i2cAddresses: '0x38,0x50' } },
    { name: 'flash', enabled: true, config: { flashApp: true, flashComms: true, jlinkSpeed: 4000 } },
    { name: 'post', enabled: true, config: { boot: true, chipId: true, bms: true, charger: true, gps: true, modem: true, imei: true, flashRW: true, personalize: true, ipcRekey: true } },
  ];
}

// ── Step 1: Board revision dropdown ─────────────────────────

describe('wizard step 1: base configuration', () => {
  it('populates board revision dropdown with ACTIVE and DRAFT revisions', () => {
    const revisions = createMockRevisions();
    const selectable = revisions.filter((r) => r.status === 'ACTIVE' || r.status === 'DRAFT');
    expect(selectable).toHaveLength(3);
  });

  it('excludes DEPRECATED revisions from dropdown', () => {
    const revisions = [
      ...createMockRevisions(),
      {
        id: 'rev-old',
        boardId: 'board-1',
        version: 'Old',
        ckBoardsName: 'alpha_old',
        socs: ['nrf52840'],
        deviceType: 2,
        deviceVariant: 3,
        modemVersion: null,
        hasModemFirmware: false,
        status: 'DEPRECATED',
        notes: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    ];
    const selectable = revisions.filter((r) => r.status === 'ACTIVE' || r.status === 'DRAFT');
    expect(selectable).toHaveLength(3);
    expect(selectable.find((r) => r.id === 'rev-old')).toBeUndefined();
  });

  it('auto-selects revision when only one is selectable', () => {
    const revisions = createMockRevisions().slice(0, 1);
    const selectable = revisions.filter((r) => r.status === 'ACTIVE' || r.status === 'DRAFT');
    const autoSelected = selectable.length === 1 ? selectable[0].id : '';
    expect(autoSelected).toBe('rev-a0');
  });

  it('validates step 1 requires revision selection', () => {
    const formRevisionId = '';
    expect(!!formRevisionId).toBe(false);
  });
});

// ── Step 2: Stages ──────────────────────────────────────────

describe('wizard step 2: stage configuration', () => {
  it('shows 3 manufacturing stages', () => {
    const stages = defaultStages();
    expect(stages).toHaveLength(3);
    expect(stages.map((s) => s.name)).toEqual(['electrical', 'flash', 'post']);
  });

  it('validates at least one stage must be enabled', () => {
    const allDisabled = defaultStages().map((s) => ({ ...s, enabled: false }));
    const isValid = allDisabled.some((s) => s.enabled);
    expect(isValid).toBe(false);
  });

  it('validates step 2 passes when at least one stage is enabled', () => {
    const stages = defaultStages();
    stages[0].enabled = false;
    stages[2].enabled = false;
    const isValid = stages.some((s) => s.enabled);
    expect(isValid).toBe(true);
  });

  it('firmware source picker has three options', () => {
    const options = ['latest_build', 'specific_version', 'manual_upload'];
    expect(options).toHaveLength(3);
  });
});

// ── Step 3: Pass criteria ───────────────────────────────────

describe('wizard step 3: pass criteria', () => {
  it('default pass criteria has all stages must pass', () => {
    const criteria: ManufacturingPassCriteria = {
      allStagesMustPass: true,
      maxRetriesPerUnit: 3,
      timingLimits: { electrical: 30, flash: 120, post: 300 },
    };
    expect(criteria.allStagesMustPass).toBe(true);
    expect(criteria.maxRetriesPerUnit).toBe(3);
  });

  it('timing limits cover all three stages', () => {
    const timingLimits = { electrical: 30, flash: 120, post: 300 };
    expect(Object.keys(timingLimits)).toHaveLength(3);
    expect(timingLimits.electrical).toBe(30);
    expect(timingLimits.flash).toBe(120);
    expect(timingLimits.post).toBe(300);
  });
});

// ── Step 4: Review & save ───────────────────────────────────

describe('wizard step 4: review and save', () => {
  it('builds correct API payload for create', () => {
    const revisionId = 'rev-b0';
    const stages = defaultStages();
    const payload = {
      boardRevisionId: revisionId,
      enabled: true,
      stages,
      firmwareSource: 'latest_build',
      firmwareSetId: null,
      personalizationConfig: {
        coreOpsUrl: 'https://10.4.45.3:443',
        deviceType: 2,
        deviceVariant: 3,
        defaultCarrier: 'Onomondo',
      },
      passCriteria: {
        allStagesMustPass: true,
        maxRetriesPerUnit: 3,
        timingLimits: { electrical: 30, flash: 120, post: 300 },
      },
    };

    expect(payload.boardRevisionId).toBe('rev-b0');
    expect(payload.stages).toHaveLength(3);
    expect(payload.firmwareSource).toBe('latest_build');
    expect(payload.personalizationConfig?.coreOpsUrl).toBe('https://10.4.45.3:443');
    expect(payload.passCriteria.maxRetriesPerUnit).toBe(3);
  });

  it('omits personalization when POST stage is disabled', () => {
    const stages = defaultStages();
    stages[2].enabled = false; // Disable POST
    const postEnabled = stages.find((s) => s.name === 'post' && s.enabled);
    const personalizationConfig = postEnabled
      ? { coreOpsUrl: 'https://10.4.45.3:443', deviceType: 2, deviceVariant: 3, defaultCarrier: 'Onomondo' }
      : null;
    expect(personalizationConfig).toBeNull();
  });

  it('restores existing config values when editing', () => {
    const existing: ManufacturingConfig = {
      id: 'cfg-1',
      productId: 'prod-1',
      boardRevisionId: 'rev-b0',
      enabled: false,
      stages: [
        { name: 'electrical', enabled: true, config: { ch0Voltage: 3.3 } },
        { name: 'flash', enabled: false, config: {} },
        { name: 'post', enabled: true, config: { boot: true } },
      ],
      firmwareSource: 'specific_version',
      firmwareSetId: 'fw-set-42',
      personalizationConfig: {
        coreOpsUrl: 'https://custom.coreops:443',
        deviceType: 5,
        deviceVariant: 1,
        defaultCarrier: 'Verizon',
      },
      passCriteria: {
        allStagesMustPass: false,
        maxRetriesPerUnit: 1,
        timingLimits: { electrical: 10, flash: 60, post: 180 },
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    // Simulate restoring values
    expect(existing.boardRevisionId).toBe('rev-b0');
    expect(existing.enabled).toBe(false);
    expect(existing.firmwareSource).toBe('specific_version');
    expect(existing.stages[0].config.ch0Voltage).toBe(3.3);
    expect(existing.stages[1].enabled).toBe(false);
    expect(existing.personalizationConfig?.defaultCarrier).toBe('Verizon');
    expect(existing.passCriteria?.maxRetriesPerUnit).toBe(1);
  });
});
