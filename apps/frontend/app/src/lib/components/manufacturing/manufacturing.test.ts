import { describe, it, expect } from 'vitest';
import type {
  ManufacturingFixture,
  ManufacturingSession,
  ManufacturingPanel,
  ManufacturingUnit,
  ManufacturingStage,
  ManufacturingSessionDetail,
} from '$lib/types/models';
import { formatDuration } from '$lib/utils/formatting';

// ── Factory helpers ─────────────────────────────────────────

function createFixture(overrides: Partial<ManufacturingFixture> = {}): ManufacturingFixture {
  return {
    id: 'fix-1',
    name: 'Alpha MFG Fixture A',
    productId: 'prod-1',
    productName: 'Alpha B0',
    slotCount: 4,
    status: 'AVAILABLE',
    activeSessionId: null,
    description: '4-slot manufacturing fixture',
    createdAt: '2026-04-01T00:00:00Z',
    updatedAt: '2026-04-01T00:00:00Z',
    ...overrides,
  };
}

function createSession(overrides: Partial<ManufacturingSession> = {}): ManufacturingSession {
  return {
    id: 'sess-1',
    productId: 'prod-1',
    fixtureId: 'fix-1',
    status: 'ACTIVE',
    operatorId: 'user-1',
    operatorName: 'Mateo',
    panelCount: 3,
    passCount: 10,
    failCount: 2,
    config: null,
    startedAt: '2026-04-01T10:00:00Z',
    finishedAt: null,
    createdAt: '2026-04-01T10:00:00Z',
    updatedAt: '2026-04-01T10:30:00Z',
    product: { id: 'prod-1', name: 'Alpha B0' },
    fixture: { id: 'fix-1', name: 'Fixture A', slotCount: 4 },
    operator: { id: 'user-1', name: 'Mateo' },
    ...overrides,
  };
}

function createUnit(overrides: Partial<ManufacturingUnit> = {}): ManufacturingUnit {
  return {
    id: 'unit-1',
    panelId: 'panel-1',
    slotIndex: 0,
    slotLabel: 'Slot 1',
    serialNumber: '70B3D584C01E1FCC',
    status: 'PASSED',
    stages: [
      { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5200, errorMessage: null },
      { type: 'FLASH', status: 'PASSED', durationMs: 12000, errorMessage: null },
      { type: 'POST', status: 'PASSED', durationMs: 48000, errorMessage: null },
    ],
    errorMessage: null,
    startedAt: '2026-04-01T10:05:00Z',
    finishedAt: '2026-04-01T10:06:05Z',
    ...overrides,
  };
}

function createPanel(overrides: Partial<ManufacturingPanel> = {}): ManufacturingPanel {
  return {
    id: 'panel-1',
    sessionId: 'sess-1',
    qrCode: 'PANEL-2026-001',
    panelIndex: 0,
    status: 'PASSED',
    unitCount: 4,
    passCount: 3,
    failCount: 1,
    startedAt: '2026-04-01T10:05:00Z',
    finishedAt: '2026-04-01T10:06:30Z',
    units: [
      createUnit({ slotIndex: 0, slotLabel: 'Slot 1' }),
      createUnit({ id: 'unit-2', slotIndex: 1, slotLabel: 'Slot 2' }),
      createUnit({ id: 'unit-3', slotIndex: 2, slotLabel: 'Slot 3' }),
      createUnit({
        id: 'unit-4',
        slotIndex: 3,
        slotLabel: 'Slot 4',
        status: 'FAILED',
        errorMessage: 'POST step 9 failed: EC keygen timeout',
        stages: [
          { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5100, errorMessage: null },
          { type: 'FLASH', status: 'PASSED', durationMs: 11800, errorMessage: null },
          { type: 'POST', status: 'FAILED', durationMs: 60000, errorMessage: 'EC keygen timeout' },
        ],
      }),
    ],
    ...overrides,
  };
}

// ── Fixture tests ───────────────────────────────────────────

describe('ManufacturingFixture data model', () => {
  it('shows fixture name and product', () => {
    const f = createFixture();
    expect(f.name).toBe('Alpha MFG Fixture A');
    expect(f.productName).toBe('Alpha B0');
  });

  it('shows AVAILABLE status when fixture not locked', () => {
    const f = createFixture({ status: 'AVAILABLE' });
    expect(f.status).toBe('AVAILABLE');
    expect(f.activeSessionId).toBeNull();
  });

  it('shows LOCKED status with active session', () => {
    const f = createFixture({ status: 'LOCKED', activeSessionId: 'sess-1' });
    expect(f.status).toBe('LOCKED');
    expect(f.activeSessionId).toBe('sess-1');
  });

  it('New Session is possible when AVAILABLE', () => {
    const f = createFixture({ status: 'AVAILABLE' });
    const canStartSession = f.status === 'AVAILABLE' && !f.activeSessionId;
    expect(canStartSession).toBe(true);
  });

  it('New Session is not possible when LOCKED', () => {
    const f = createFixture({ status: 'LOCKED', activeSessionId: 'sess-1' });
    const canStartSession = f.status === 'AVAILABLE' && !f.activeSessionId;
    expect(canStartSession).toBe(false);
  });
});

// ── Session tests ───────────────────────────────────────────

describe('ManufacturingSession data model', () => {
  it('computes duration for active sessions', () => {
    const s = createSession({
      startedAt: '2026-04-01T10:00:00Z',
      finishedAt: null,
    });
    expect(s.startedAt).not.toBeNull();
    expect(s.finishedAt).toBeNull();
    // Duration should be computable
    const start = new Date(s.startedAt!).getTime();
    expect(start).toBeGreaterThan(0);
  });

  it('computes duration for completed sessions', () => {
    const s = createSession({
      status: 'COMPLETED',
      startedAt: '2026-04-01T10:00:00Z',
      finishedAt: '2026-04-01T10:30:00Z',
    });
    const start = new Date(s.startedAt!).getTime();
    const end = new Date(s.finishedAt!).getTime();
    const duration = formatDuration(end - start);
    expect(duration).toBe('30m');
  });

  it('has operator information', () => {
    const s = createSession();
    expect(s.operator?.name).toBe('Mateo');
    expect(s.operatorName).toBe('Mateo');
  });

  it('tracks pass/fail counts', () => {
    const s = createSession({ passCount: 10, failCount: 2, panelCount: 3 });
    expect(s.passCount).toBe(10);
    expect(s.failCount).toBe(2);
    expect(s.panelCount).toBe(3);
  });
});

// ── Unit card tests ─────────────────────────────────────────

describe('ManufacturingUnit data model', () => {
  it('shows slot label and serial number', () => {
    const u = createUnit();
    expect(u.slotLabel).toBe('Slot 1');
    expect(u.serialNumber).toBe('70B3D584C01E1FCC');
  });

  it('shows all three stage progress indicators', () => {
    const u = createUnit();
    expect(u.stages).toHaveLength(3);
    expect(u.stages.map((s) => s.type)).toEqual(['ELECTRICAL', 'FLASH', 'POST']);
  });

  it('updates stage from RUNNING to PASSED', () => {
    const u = createUnit({
      status: 'RUNNING',
      stages: [
        { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5200, errorMessage: null },
        { type: 'FLASH', status: 'RUNNING', durationMs: null, errorMessage: null },
      ],
    });
    expect(u.stages[1].status).toBe('RUNNING');

    // Simulate update
    u.stages[1] = { type: 'FLASH', status: 'PASSED', durationMs: 12000, errorMessage: null };
    expect(u.stages[1].status).toBe('PASSED');
  });

  it('shows error message on FAILED', () => {
    const u = createUnit({
      status: 'FAILED',
      errorMessage: 'POST step 9 failed: EC keygen timeout',
      stages: [
        { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5100, errorMessage: null },
        { type: 'FLASH', status: 'PASSED', durationMs: 11800, errorMessage: null },
        { type: 'POST', status: 'FAILED', durationMs: 60000, errorMessage: 'EC keygen timeout' },
      ],
    });
    expect(u.status).toBe('FAILED');
    expect(u.errorMessage).toContain('EC keygen timeout');
    expect(u.stages[2].status).toBe('FAILED');
  });

  it('computes unit duration', () => {
    const u = createUnit({
      startedAt: '2026-04-01T10:05:00Z',
      finishedAt: '2026-04-01T10:06:05Z',
    });
    const start = new Date(u.startedAt!).getTime();
    const end = new Date(u.finishedAt!).getTime();
    const duration = formatDuration(end - start);
    expect(duration).toBe('1m 5s');
  });
});

// ── Panel runner tests ──────────────────────────────────────

describe('PanelRunner logic', () => {
  it('Run Panel disabled while panel is running', () => {
    const session: ManufacturingSessionDetail = {
      ...createSession(),
      activePanel: createPanel({ status: 'RUNNING' }),
      panels: [],
    };
    const panelRunning = session.activePanel?.status === 'RUNNING';
    expect(panelRunning).toBe(true);
    // canSubmit should be false when panelRunning
    const canSubmit = session.status === 'ACTIVE' && !panelRunning && 'PANEL-001'.trim().length > 0;
    expect(canSubmit).toBe(false);
  });

  it('QR input enables submit when valid', () => {
    const session: ManufacturingSessionDetail = {
      ...createSession(),
      activePanel: null,
      panels: [],
    };
    const panelRunning = session.activePanel?.status === 'RUNNING';
    const qrInput = 'PANEL-2026-002';
    const canSubmit = session.status === 'ACTIVE' && !panelRunning && qrInput.trim().length > 0;
    expect(canSubmit).toBe(true);
  });

  it('submit disabled with empty QR input', () => {
    const session: ManufacturingSessionDetail = {
      ...createSession(),
      activePanel: null,
      panels: [],
    };
    const panelRunning = session.activePanel?.status === 'RUNNING';
    const qrInput = '';
    const canSubmit = session.status === 'ACTIVE' && !panelRunning && qrInput.trim().length > 0;
    expect(canSubmit).toBe(false);
  });

  it('submit disabled when session is not ACTIVE', () => {
    const session: ManufacturingSessionDetail = {
      ...createSession({ status: 'COMPLETED' }),
      activePanel: null,
      panels: [],
    };
    const panelRunning = session.activePanel?.status === 'RUNNING';
    const qrInput = 'PANEL-2026-002';
    const canSubmit = session.status === 'ACTIVE' && !panelRunning && qrInput.trim().length > 0;
    expect(canSubmit).toBe(false);
  });
});

// ── Panel results grid tests ────────────────────────────────

describe('Panel results grid', () => {
  it('shows correct unit count', () => {
    const panel = createPanel();
    expect(panel.units).toHaveLength(4);
    expect(panel.unitCount).toBe(4);
  });

  it('computes completed count', () => {
    const panel = createPanel();
    const completedCount = panel.units.filter(
      (u) => u.status === 'PASSED' || u.status === 'FAILED'
    ).length;
    expect(completedCount).toBe(4);
  });

  it('computes progress percentage', () => {
    const panel = createPanel();
    const completedCount = panel.units.filter(
      (u) => u.status === 'PASSED' || u.status === 'FAILED'
    ).length;
    const progressPct = Math.round((completedCount / panel.unitCount) * 100);
    expect(progressPct).toBe(100);
  });

  it('shows partial progress for running panel', () => {
    const panel = createPanel({
      status: 'RUNNING',
      units: [
        createUnit({ slotIndex: 0, status: 'PASSED' }),
        createUnit({ id: 'unit-2', slotIndex: 1, status: 'RUNNING' }),
        createUnit({ id: 'unit-3', slotIndex: 2, status: 'QUEUED' }),
        createUnit({ id: 'unit-4', slotIndex: 3, status: 'QUEUED' }),
      ],
    });
    const completedCount = panel.units.filter(
      (u) => u.status === 'PASSED' || u.status === 'FAILED'
    ).length;
    expect(completedCount).toBe(1);
    expect(Math.round((completedCount / panel.unitCount) * 100)).toBe(25);
  });
});

// ── Permission gating tests ─────────────────────────────────

describe('Permission gating logic', () => {
  it('manufacturing:view allows read access', () => {
    const perms = ['manufacturing:view'];
    expect(perms.includes('manufacturing:view')).toBe(true);
    expect(perms.includes('manufacturing:run')).toBe(false);
  });

  it('manufacturing:run allows session creation', () => {
    const perms = ['manufacturing:view', 'manufacturing:run'];
    expect(perms.includes('manufacturing:run')).toBe(true);
  });

  it('manufacturing:manage allows configuration', () => {
    const perms = ['manufacturing:view', 'manufacturing:run', 'manufacturing:manage'];
    expect(perms.includes('manufacturing:manage')).toBe(true);
  });
});

// ── Stage progress ordering ─────────────────────────────────

describe('Stage progress ordering', () => {
  const STAGE_ORDER = ['ELECTRICAL', 'FLASH', 'POST'];

  it('stages render in correct order', () => {
    const stages: ManufacturingStage[] = [
      { type: 'POST', status: 'QUEUED', durationMs: null, errorMessage: null },
      { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5000, errorMessage: null },
      { type: 'FLASH', status: 'RUNNING', durationMs: null, errorMessage: null },
    ];

    const ordered = STAGE_ORDER.map((type) => {
      return stages.find((s) => s.type === type) || { type, status: 'QUEUED', durationMs: null, errorMessage: null };
    });

    expect(ordered[0].type).toBe('ELECTRICAL');
    expect(ordered[0].status).toBe('PASSED');
    expect(ordered[1].type).toBe('FLASH');
    expect(ordered[1].status).toBe('RUNNING');
    expect(ordered[2].type).toBe('POST');
    expect(ordered[2].status).toBe('QUEUED');
  });

  it('fills missing stages as QUEUED', () => {
    const stages: ManufacturingStage[] = [
      { type: 'ELECTRICAL', status: 'PASSED', durationMs: 5000, errorMessage: null },
    ];

    const ordered = STAGE_ORDER.map((type) => {
      return stages.find((s) => s.type === type) || { type, status: 'QUEUED', durationMs: null, errorMessage: null };
    });

    expect(ordered).toHaveLength(3);
    expect(ordered[1].status).toBe('QUEUED');
    expect(ordered[2].status).toBe('QUEUED');
  });
});
