import { describe, it, expect } from 'vitest';
import { effectiveRunStatus, isRunInFlight, allTargetsTerminal } from './run-status';
import type { RunTarget, TestRun } from '$lib/types/models';

function target(status: RunTarget['status'], slotIndex = 0): RunTarget {
  return {
    id: `t-${slotIndex}`,
    runId: 'run-1',
    slotIndex,
    status,
  } as RunTarget;
}

function run(status: TestRun['status'], targets: RunTarget[] = []): TestRun {
  return {
    id: 'run-1',
    type: 'MANUFACTURING',
    productId: 'p',
    fixtureId: 'f',
    status,
    operatorId: 'op',
    targetCount: targets.length,
    completedCount: 0,
    passedCount: 0,
    failedCount: 0,
    createdAt: '2026-04-30T00:00:00Z',
    updatedAt: '2026-04-30T00:00:00Z',
    targets,
  } as TestRun;
}

describe('effectiveRunStatus', () => {
  it('returns stored status verbatim when ACTIVE', () => {
    expect(effectiveRunStatus(run('ACTIVE', [target('RUNNING')]))).toBe('ACTIVE');
  });

  it('returns stored status verbatim when terminal', () => {
    expect(effectiveRunStatus(run('COMPLETED', [target('PASSED')]))).toBe('COMPLETED');
    expect(effectiveRunStatus(run('FAILED', [target('FAILED')]))).toBe('FAILED');
    expect(effectiveRunStatus(run('CANCELLED', []))).toBe('CANCELLED');
  });

  it('keeps PENDING when no target has started', () => {
    expect(effectiveRunStatus(run('PENDING', [target('PENDING'), target('PENDING', 1)]))).toBe('PENDING');
  });

  it('keeps PENDING when run has no targets yet', () => {
    expect(effectiveRunStatus(run('PENDING', []))).toBe('PENDING');
  });

  it('promotes PENDING to ACTIVE when any target is RUNNING (the bug fix)', () => {
    // Reproduces rwkjd8: target shows RUNNING in widget, row should also show ACTIVE
    expect(effectiveRunStatus(run('PENDING', [target('RUNNING'), target('PENDING', 1)]))).toBe('ACTIVE');
  });

  it('promotes PENDING to ACTIVE when any target is in a terminal state', () => {
    expect(effectiveRunStatus(run('PENDING', [target('PASSED'), target('PENDING', 1)]))).toBe('ACTIVE');
    expect(effectiveRunStatus(run('PENDING', [target('FAILED')]))).toBe('ACTIVE');
  });
});

describe('isRunInFlight', () => {
  it('is true for ACTIVE', () => {
    expect(isRunInFlight(run('ACTIVE'))).toBe(true);
  });

  it('is true for stored PENDING with no progress', () => {
    expect(isRunInFlight(run('PENDING'))).toBe(true);
  });

  it('is true for stored PENDING that has progressed', () => {
    expect(isRunInFlight(run('PENDING', [target('RUNNING')]))).toBe(true);
  });

  it('is false once the run is COMPLETED', () => {
    expect(isRunInFlight(run('COMPLETED'))).toBe(false);
  });
});

describe('allTargetsTerminal', () => {
  it('is false when there are no targets', () => {
    expect(allTargetsTerminal(run('PENDING', []))).toBe(false);
  });

  it('is false while any target is RUNNING', () => {
    expect(allTargetsTerminal(run('ACTIVE', [target('PASSED'), target('RUNNING', 1)]))).toBe(false);
  });

  it('is true when every target is terminal', () => {
    expect(allTargetsTerminal(run('ACTIVE', [target('PASSED'), target('FAILED', 1)]))).toBe(true);
  });
});
