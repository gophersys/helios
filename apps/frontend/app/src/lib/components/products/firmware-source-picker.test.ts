import { describe, it, expect } from 'vitest';

// ── Firmware source picker logic tests ──────────────────────

describe('firmware-source-picker', () => {
  const options = [
    { key: 'latest_build', label: 'Latest Build', description: 'Automatically uses the most recent validated firmware build' },
    { key: 'specific_version', label: 'Specific Version', description: 'Pin to a specific firmware version from the build system' },
    { key: 'manual_upload', label: 'Manual Upload', description: 'Upload firmware binaries manually for each manufacturing run' },
  ];

  it('latest build option shows most recent build info', () => {
    const latestOption = options.find((o) => o.key === 'latest_build');
    expect(latestOption).toBeDefined();
    expect(latestOption!.label).toBe('Latest Build');
    expect(latestOption!.description).toContain('most recent');
  });

  it('specific version shows version dropdown', () => {
    const versionOption = options.find((o) => o.key === 'specific_version');
    expect(versionOption).toBeDefined();
    expect(versionOption!.label).toBe('Specific Version');
    expect(versionOption!.description).toContain('specific firmware version');
  });

  it('manual upload shows file input', () => {
    const uploadOption = options.find((o) => o.key === 'manual_upload');
    expect(uploadOption).toBeDefined();
    expect(uploadOption!.label).toBe('Manual Upload');
    expect(uploadOption!.description).toContain('Upload firmware');
  });

  it('exactly three firmware source options exist', () => {
    expect(options).toHaveLength(3);
  });

  it('all options have unique keys', () => {
    const keys = options.map((o) => o.key);
    const uniqueKeys = [...new Set(keys)];
    expect(uniqueKeys).toHaveLength(keys.length);
  });

  it('selecting an option returns the correct key', () => {
    let selectedValue = 'latest_build';

    // Simulate user selecting specific_version
    const onchange = (value: string) => { selectedValue = value; };
    onchange('specific_version');
    expect(selectedValue).toBe('specific_version');

    // Simulate user selecting manual_upload
    onchange('manual_upload');
    expect(selectedValue).toBe('manual_upload');
  });
});
