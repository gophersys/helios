/**
 * Tests for the error-reporter store — focused on the WS reconnect-noise filter.
 *
 * The /manufacturing page produced a flood of "Notification WS error: xhr post
 * error" reports whenever the WS gateway briefly cycled (deploys, NAT idle).
 * Those are benign socket.io reconnect noise, not real bugs. We assert here
 * that the filter swallows them while keeping real WS errors flowing.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$env/static/public', () => ({
  PUBLIC_APP_VERSION: 'test',
  PUBLIC_APP_ENVIRONMENT: 'test',
}));

import {
  reportWsError,
  isTransientWsError,
  getErrorReporter,
} from './error-reporter.svelte';

describe('isTransientWsError', () => {
  it('matches xhr post error verbatim', () => {
    expect(isTransientWsError('xhr post error')).toBe(true);
  });

  it('matches the full reported message including namespace prefix', () => {
    // This is the exact shape websocket.ts emits — namespace + ":" + the
    // socket.io message — so the filter must match it as a substring.
    expect(isTransientWsError('Notification WS error: xhr post error')).toBe(true);
  });

  it('matches the polling-side variant', () => {
    expect(isTransientWsError('Run WS error: xhr poll error')).toBe(true);
  });

  it('matches transport close/error during gateway restart', () => {
    expect(isTransientWsError('System WS error: transport close')).toBe(true);
    expect(isTransientWsError('System WS error: transport error')).toBe(true);
  });

  it('matches case-insensitively', () => {
    expect(isTransientWsError('XHR POST ERROR')).toBe(true);
  });

  it('does NOT match real backend errors', () => {
    expect(isTransientWsError('Notification WS error: Authentication failed')).toBe(false);
    expect(isTransientWsError('System WS error: Namespace /unknown not found')).toBe(false);
    expect(isTransientWsError('Run WS error: Internal server error')).toBe(false);
  });

  it('handles empty/missing messages gracefully', () => {
    expect(isTransientWsError('')).toBe(false);
    // @ts-expect-error — exercise the runtime guard
    expect(isTransientWsError(undefined)).toBe(false);
  });
});

describe('reportWsError', () => {
  beforeEach(() => {
    // Reset the singleton state between tests so each one starts clean.
    const reporter = getErrorReporter();
    reporter.dismiss();
    reporter.history = [];
  });

  it('does not produce a report for the xhr post error reconnect noise', () => {
    const reporter = getErrorReporter();
    reportWsError({
      message: 'Notification WS error: xhr post error',
      namespace: '/notifications',
    });
    expect(reporter.current).toBeNull();
    expect(reporter.history).toHaveLength(0);
  });

  it('does not produce a report for transport close/error during reconnect', () => {
    const reporter = getErrorReporter();
    reportWsError({
      message: 'System WS error: transport close',
      namespace: '/kubernetes',
    });
    expect(reporter.current).toBeNull();
    expect(reporter.history).toHaveLength(0);
  });

  it('STILL reports real WS errors (auth failures, server errors, etc.)', () => {
    const reporter = getErrorReporter();
    reportWsError({
      message: 'Notification WS error: Authentication failed',
      namespace: '/notifications',
    });
    expect(reporter.current).not.toBeNull();
    expect(reporter.current?.message).toContain('Authentication failed');
    expect(reporter.current?.type).toBe('websocket');
    expect(reporter.history).toHaveLength(1);
  });

  it('STILL reports unknown error patterns (default to surfacing)', () => {
    const reporter = getErrorReporter();
    reportWsError({
      message: 'Run WS error: Permission denied for run subscription',
      namespace: '/runs',
    });
    expect(reporter.current).not.toBeNull();
    expect(reporter.current?.message).toContain('Permission denied');
  });
});
