// Unit suite for the Connectors write-only display spine (design §3.5 #2 — the no-echo invariant).
// Pure-TS: asserts that the display helpers NEVER echo a plaintext value, only the one-way
// fingerprint + non-secret metadata. Run via `bash ./ctl.sh unit` (scoped to *.unit.test.ts).
import { describe, expect, it } from 'vitest';
import {
  CONNECTOR_KINDS,
  fingerprintDisplay,
  isConnected,
  isConnectorKind,
  kindGlyph,
  kindLabel,
  scopeChipText,
  shortId,
  stateBadgeVariant,
  stateLabel,
  type ConnectorView,
} from './connectors';

// A sample plaintext credential — the value that must NEVER appear in any display output.
const SECRET = 'sk-ant-super-secret-value-1234567890';

describe('connector kind enum (§2.2 — closed, honest-chrome)', () => {
  it('locks the v1 set to claude-api / github / openrouter', () => {
    expect([...CONNECTOR_KINDS]).toEqual(['claude-api', 'github', 'openrouter']);
  });

  it('narrows only the working kinds (an off-list kind is rejected — P-D6)', () => {
    expect(isConnectorKind('claude-api')).toBe(true);
    expect(isConnectorKind('github')).toBe(true);
    expect(isConnectorKind('aws')).toBe(false);
    expect(isConnectorKind('')).toBe(false);
  });

  it('resolves human labels + glyphs, falling back honestly for an unknown kind', () => {
    expect(kindLabel('claude-api')).toBe('Claude API');
    expect(kindLabel('github')).toBe('GitHub');
    expect(kindLabel('mystery')).toBe('mystery');
    expect(kindGlyph('mystery')).toBe('•');
  });
});

describe('fingerprintDisplay — the no-echo helper (§1.1 / §3.5 #2)', () => {
  it('renders ONLY the server fingerprint, masked — never the value', () => {
    const shown = fingerprintDisplay('9f3a');
    expect(shown).toBe('••••9f3a');
    // The plaintext value must not appear anywhere in the display output.
    expect(shown).not.toContain(SECRET);
    expect(shown).not.toContain('sk-ant');
  });

  it('degrades an empty fingerprint to a mask (never a blank that reads as "no secret")', () => {
    expect(fingerprintDisplay('')).toBe('••••');
    expect(fingerprintDisplay('   ')).toBe('••••');
  });
});

describe('isConnected — gates the write-only vs offer display', () => {
  const base: ConnectorView = {
    id: 'connector-1',
    kind: 'github',
    name: 'GitHub',
    scope: { level: 'org' },
    state: 'healthy',
    accountHint: 'gh-9f3a',
    fingerprint: '9f3a',
  };

  it('is connected when a fingerprint is stored and the state is not not-set', () => {
    expect(isConnected(base)).toBe(true);
  });

  it('is NOT connected for a not-set / fingerprintless row (an offered provider)', () => {
    expect(isConnected({ ...base, state: 'not-set', fingerprint: '' })).toBe(false);
    expect(isConnected({ ...base, fingerprint: '' })).toBe(false);
  });
});

describe('state → Badge (real status, never decorative; the word survives grayscale)', () => {
  it('maps each state to its status variant + human word', () => {
    expect(stateBadgeVariant('healthy')).toBe('healthy');
    expect(stateBadgeVariant('degraded')).toBe('degraded');
    expect(stateBadgeVariant('down')).toBe('down');
    expect(stateBadgeVariant('updating')).toBe('updating');
    expect(stateBadgeVariant('not-set')).toBe('neutral');

    expect(stateLabel('healthy')).toBe('healthy');
    expect(stateLabel('not-set')).toBe('not set');
    expect(stateLabel('updating')).toBe('validating');
  });
});

describe('scope chip (mono data voice; org shows no target)', () => {
  it('renders org-wide scopes as just the level (user_id NULL ⇒ org)', () => {
    expect(scopeChipText({ level: 'org' })).toBe('org');
    expect(scopeChipText({ level: 'org', targetId: 'ignored' })).toBe('org');
  });

  it('renders a targeted scope with the short id', () => {
    expect(scopeChipText({ level: 'user', targetId: 'user-abcdef0123456789' })).toBe(
      'user:user-abc',
    );
  });

  it('shortId truncates an opaque id to a scannable head (never the full value)', () => {
    expect(shortId('short')).toBe('short');
    expect(shortId('0123456789abcdef')).toBe('01234567');
  });
});
