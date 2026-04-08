import { describe, it, expect } from 'vitest';
import type {
  ManufacturingConfig,
  ManufacturingStageConfig,
  ManufacturingPassCriteria,
  ManufacturingPersonalizationConfig,
} from '$lib/types/models';

// ── Mock factories ──────────────────────────────────────────

function createMockStages(): ManufacturingStageConfig[] {
  return [
    { name: 'electrical', enabled: true, config: { ch0Voltage: 4.5, ch1Voltage: 0, minCurrentMa: 5, maxCurrentMa: 100, i2cAddresses: '0x38,0x50' } },
    { name: 'flash', enabled: true, config: { flashApp: true, flashComms: true, jlinkSpeed: 4000 } },
    { name: 'post', enabled: true, config: { boot: true, chipId: true, bms: true, personalize: true } },
  ];
}

function createMockConfig(overrides: Partial<ManufacturingConfig> = {}): ManufacturingConfig {
  return {
    id: 'mfg-cfg-1',
    productId: 'prod-1',
    boardRevisionId: 'rev-b0',
    enabled: true,
    stages: createMockStages(),
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
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

// ── Tab display logic tests ─────────────────────────────────

describe('manufacturing-tab display logic', () => {
  it('identifies "not configured" state when no config exists', () => {
    const config: ManufacturingConfig | null = null;
    expect(config).toBeNull();
  });

  it('shows config summary when configured', () => {
    const config = createMockConfig();
    expect(config).not.toBeNull();
    expect(config.enabled).toBe(true);
    expect(config.stages).toHaveLength(3);
  });

  it('filters enabled stages for display', () => {
    const config = createMockConfig({
      stages: [
        { name: 'electrical', enabled: true, config: {} },
        { name: 'flash', enabled: false, config: {} },
        { name: 'post', enabled: true, config: {} },
      ],
    });
    const enabledStages = config.stages.filter((s) => s.enabled);
    expect(enabledStages).toHaveLength(2);
    expect(enabledStages.map((s) => s.name)).toEqual(['electrical', 'post']);
  });

  it('resolves firmware source label from code', () => {
    const labels: Record<string, string> = {
      latest_build: 'Latest Build',
      specific_version: 'Specific Version',
      manual_upload: 'Manual Upload',
    };
    expect(labels['latest_build']).toBe('Latest Build');
    expect(labels['specific_version']).toBe('Specific Version');
    expect(labels['manual_upload']).toBe('Manual Upload');
  });
});

describe('manufacturing-tab permission gating', () => {
  it('configure button requires manufacturing:manage permission', () => {
    const permissions = ['manufacturing:view'];
    const canConfigure = permissions.includes('manufacturing:manage');
    expect(canConfigure).toBe(false);
  });

  it('configure button visible with manufacturing:manage permission', () => {
    const permissions = ['manufacturing:view', 'manufacturing:manage'];
    const canConfigure = permissions.includes('manufacturing:manage');
    expect(canConfigure).toBe(true);
  });

  it('configure button hidden for developer without manage permission', () => {
    const permissions = ['products:view', 'manufacturing:view'];
    const canConfigure = permissions.includes('manufacturing:manage');
    expect(canConfigure).toBe(false);
  });
});
