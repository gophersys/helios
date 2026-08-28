/**
 * Tests for color constants and utilities.
 * Ensures consistent theming across the app.
 */
import { describe, it, expect } from 'vitest';
import {
  ACTION_COLORS,
  DEFAULT_ACTION_COLOR,
  getActionColor,
  STATUS_COLORS,
  DEFAULT_STATUS_COLOR,
  getStatusColor,
  SEVERITY_COLORS,
  getSeverityColor
} from './colors';

describe('ACTION_COLORS', () => {
  it('has Create action with success colors', () => {
    expect(ACTION_COLORS.Create).toBeDefined();
    expect(ACTION_COLORS.Create.bg).toContain('success');
    expect(ACTION_COLORS.Create.text).toContain('success');
  });

  it('has View action with info colors', () => {
    expect(ACTION_COLORS.View).toBeDefined();
    expect(ACTION_COLORS.View.bg).toContain('info');
  });

  it('has Update action with warning colors', () => {
    expect(ACTION_COLORS.Update).toBeDefined();
    expect(ACTION_COLORS.Update.bg).toContain('warning');
  });

  it('has Delete action with error colors', () => {
    expect(ACTION_COLORS.Delete).toBeDefined();
    expect(ACTION_COLORS.Delete.bg).toContain('error');
  });

  it('has Manage action with accent colors', () => {
    expect(ACTION_COLORS.Manage).toBeDefined();
    expect(ACTION_COLORS.Manage.bg).toContain('accent');
  });

  it('all actions have required properties', () => {
    for (const [action, colors] of Object.entries(ACTION_COLORS)) {
      expect(colors.bg, `${action} should have bg`).toBeDefined();
      expect(colors.text, `${action} should have text`).toBeDefined();
      expect(colors.dot, `${action} should have dot`).toBeDefined();
    }
  });
});

describe('getActionColor', () => {
  it('returns correct color for known actions', () => {
    expect(getActionColor('Create')).toBe(ACTION_COLORS.Create);
    expect(getActionColor('View')).toBe(ACTION_COLORS.View);
    expect(getActionColor('Delete')).toBe(ACTION_COLORS.Delete);
  });

  it('returns default color for unknown actions', () => {
    expect(getActionColor('Unknown')).toBe(DEFAULT_ACTION_COLOR);
    expect(getActionColor('')).toBe(DEFAULT_ACTION_COLOR);
  });

  it('default color has neutral styling', () => {
    expect(DEFAULT_ACTION_COLOR.bg).toContain('surface');
    expect(DEFAULT_ACTION_COLOR.text).toContain('secondary');
  });
});

describe('STATUS_COLORS', () => {
  describe('Success States', () => {
    it('has Running status', () => {
      expect(STATUS_COLORS.Running).toBeDefined();
      expect(STATUS_COLORS.Running.bg).toContain('success');
    });

    it('has Ready status', () => {
      expect(STATUS_COLORS.Ready).toBeDefined();
      expect(STATUS_COLORS.Ready.bg).toContain('success');
    });

    it('has Completed status', () => {
      expect(STATUS_COLORS.Completed).toBeDefined();
      expect(STATUS_COLORS.Completed.bg).toContain('success');
    });
  });

  describe('Warning States', () => {
    it('has Pending status', () => {
      expect(STATUS_COLORS.Pending).toBeDefined();
      expect(STATUS_COLORS.Pending.bg).toContain('warning');
    });

    it('has Terminating status', () => {
      expect(STATUS_COLORS.Terminating).toBeDefined();
      expect(STATUS_COLORS.Terminating.bg).toContain('warning');
    });
  });

  describe('Error States', () => {
    it('has Failed status', () => {
      expect(STATUS_COLORS.Failed).toBeDefined();
      expect(STATUS_COLORS.Failed.bg).toContain('error');
    });

    it('has CrashLoopBackOff status', () => {
      expect(STATUS_COLORS.CrashLoopBackOff).toBeDefined();
      expect(STATUS_COLORS.CrashLoopBackOff.bg).toContain('error');
    });

    it('has NotReady status', () => {
      expect(STATUS_COLORS.NotReady).toBeDefined();
      expect(STATUS_COLORS.NotReady.bg).toContain('error');
    });
  });

  it('all statuses have required properties', () => {
    for (const [status, colors] of Object.entries(STATUS_COLORS)) {
      expect(colors.bg, `${status} should have bg`).toBeDefined();
      expect(colors.text, `${status} should have text`).toBeDefined();
      expect(colors.dot, `${status} should have dot`).toBeDefined();
    }
  });
});

describe('getStatusColor', () => {
  it('returns correct color for known statuses', () => {
    expect(getStatusColor('Running')).toBe(STATUS_COLORS.Running);
    expect(getStatusColor('Failed')).toBe(STATUS_COLORS.Failed);
    expect(getStatusColor('Pending')).toBe(STATUS_COLORS.Pending);
  });

  it('returns default color for unknown statuses', () => {
    expect(getStatusColor('CustomStatus')).toBe(DEFAULT_STATUS_COLOR);
  });
});

describe('SEVERITY_COLORS', () => {
  it('has critical severity', () => {
    expect(SEVERITY_COLORS.critical).toBeDefined();
    expect(SEVERITY_COLORS.critical.bg).toContain('error');
  });

  it('has error severity', () => {
    expect(SEVERITY_COLORS.error).toBeDefined();
    expect(SEVERITY_COLORS.error.bg).toContain('error');
  });

  it('has warning severity', () => {
    expect(SEVERITY_COLORS.warning).toBeDefined();
    expect(SEVERITY_COLORS.warning.bg).toContain('warning');
  });

  it('has info severity', () => {
    expect(SEVERITY_COLORS.info).toBeDefined();
    expect(SEVERITY_COLORS.info.bg).toContain('info');
  });

  it('has success severity', () => {
    expect(SEVERITY_COLORS.success).toBeDefined();
    expect(SEVERITY_COLORS.success.bg).toContain('success');
  });

  it('all severities have border property', () => {
    for (const [severity, colors] of Object.entries(SEVERITY_COLORS)) {
      expect(colors.border, `${severity} should have border`).toBeDefined();
    }
  });
});

describe('getSeverityColor', () => {
  it('returns correct color for known severities', () => {
    expect(getSeverityColor('error')).toBe(SEVERITY_COLORS.error);
    expect(getSeverityColor('warning')).toBe(SEVERITY_COLORS.warning);
  });

  it('is case-insensitive', () => {
    expect(getSeverityColor('ERROR')).toBe(SEVERITY_COLORS.error);
    expect(getSeverityColor('Warning')).toBe(SEVERITY_COLORS.warning);
    expect(getSeverityColor('INFO')).toBe(SEVERITY_COLORS.info);
  });

  it('returns info color for unknown severities', () => {
    expect(getSeverityColor('unknown')).toBe(SEVERITY_COLORS.info);
  });
});

describe('Color Consistency', () => {
  it('uses consistent opacity patterns', () => {
    // All action colors should use /10 or /20 opacity pattern
    for (const colors of Object.values(ACTION_COLORS)) {
      expect(colors.bg).toMatch(/\/(10|20)/);
    }
  });

  it('uses semantic color tokens', () => {
    // Should use design tokens, not raw colors
    const validTokens = ['success', 'error', 'warning', 'info', 'accent', 'surface', 'text', 'border', 'violet'];

    for (const colors of Object.values(ACTION_COLORS)) {
      const hasValidToken = validTokens.some(token => colors.bg.includes(token));
      expect(hasValidToken, `${colors.bg} should use semantic tokens`).toBe(true);
    }
  });
});
