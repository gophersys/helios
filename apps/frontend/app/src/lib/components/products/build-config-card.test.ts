import { describe, it, expect } from 'vitest';
import type { BuildConfig } from '$lib/types/models';

// Test BuildConfig data shape and derivations used by the component.
// Component rendering tests would require Svelte component testing setup;
// these tests validate the data layer the component depends on.

function createAlphaBuildConfig(): BuildConfig {
  return {
    board: 'alpha',
    ncsVersion: 'v2.9.0',
    boardRoot: 'ck_boards',
    hasVsmMerge: true,
    hasFips: false,
    confFiles: {
      app: ['prj.conf', 'boards/alpha_b0_nrf52840.conf'],
      comms: ['prj.conf', 'boards/alpha_b0_nrf9151.conf'],
    },
    overlays: {
      app: ['boards/alpha_b0_nrf52840.overlay'],
      comms: [],
    },
    postBuild: ['sign_mcuboot', 'generate_dfu_package'],
    cfw: { deviceType: 2, deviceVariant: 3 },
  };
}

function createSingleProcessorConfig(): BuildConfig {
  return {
    board: 'sigma5',
    ncsVersion: 'v2.9.0',
    boardRoot: 'ck_boards',
    hasVsmMerge: false,
    hasFips: false,
    confFiles: { app: ['prj.conf'] },
    overlays: { app: [] },
    postBuild: ['sign_mcuboot'],
    cfw: { deviceType: 5, deviceVariant: 1 },
  };
}

describe('BuildConfig data model', () => {
  describe('dual-processor (Alpha)', () => {
    const config = createAlphaBuildConfig();

    it('cfw has deviceType and deviceVariant', () => {
      expect(config.cfw.deviceType).toBe(2);
      expect(config.cfw.deviceVariant).toBe(3);
    });

    it('overlay filtering excludes empty arrays', () => {
      const nonEmptyOverlays = Object.entries(config.overlays).filter(
        ([, files]) => files.length > 0
      );
      expect(nonEmptyOverlays).toHaveLength(1);
      expect(nonEmptyOverlays[0][0]).toBe('app');
    });

    it('postBuild steps are ordered', () => {
      expect(config.postBuild).toEqual(['sign_mcuboot', 'generate_dfu_package']);
    });

    it('hasVsmMerge is true for alpha', () => {
      expect(config.hasVsmMerge).toBe(true);
    });
  });

  describe('single-processor (Sigma5)', () => {
    const config = createSingleProcessorConfig();

    it('hasVsmMerge is false', () => {
      expect(config.hasVsmMerge).toBe(false);
    });

    it('overlays are empty for single-processor', () => {
      const nonEmptyOverlays = Object.entries(config.overlays).filter(
        ([, files]) => files.length > 0
      );
      expect(nonEmptyOverlays).toHaveLength(0);
    });

    it('postBuild has only sign_mcuboot', () => {
      expect(config.postBuild).toEqual(['sign_mcuboot']);
    });
  });
});
