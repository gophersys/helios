/**
 * CSS custom-property emission (research §C.4 build outputs).
 *
 * Turns a generated {@link Theme} into the runtime substrate: `--color-*`, `--space-*`, `--size-*`,
 * `--font-*`, `--duration-*`, `--ease-*`, `--z-*` custom properties (research §C.4). Colors are
 * emitted as `oklch(...)` so the browser does the perceptually-uniform interpolation; CSS custom
 * properties are the ratified runtime theming substrate (ADR-0005 thesis, retained by ADR-0024).
 */

import type { OkLch } from './oklch.js';
import type { Theme, RoleColor } from './generate.js';

/** Round to 4dp and render as a string (the strict lint forbids bare numbers in template literals). */
const r4 = (x: number): string => String(Math.round(x * 10000) / 10000);

/** Render an OKLCH color as a CSS `oklch()` function (L as a 0–1 number, C, H in deg). */
export function oklchToCss({ l, c, h }: OkLch): string {
  return `oklch(${r4(l)} ${r4(c)} ${r4(h)})`;
}

function roleVar(name: string, role: RoleColor): string {
  return `  --color-${name}: ${oklchToCss(role.value)};`;
}

/**
 * Emit a theme's `:root` CSS custom-property block (research §C.4). Returns the CSS text; the
 * caller scopes it (`:root`, `[data-theme=dark]`, `[data-density=compact]`) at the host.
 */
export function themeToCssVariables(theme: Theme): string {
  const lines: string[] = [];

  // Tier-2 semantic role colors (the tokens components consume).
  const roles = theme.roles;
  lines.push(roleVar('surface', roles.surface));
  lines.push(roleVar('on-surface', roles.onSurface));
  lines.push(roleVar('primary', roles.primary));
  lines.push(roleVar('on-primary', roles.onPrimary));
  lines.push(roleVar('primary-container', roles.primaryContainer));
  lines.push(roleVar('on-primary-container', roles.onPrimaryContainer));
  lines.push(roleVar('secondary', roles.secondary));
  lines.push(roleVar('outline', roles.outline));
  lines.push(roleVar('error', roles.error));
  lines.push(roleVar('on-error', roles.onError));
  lines.push(roleVar('warning', roles.warning));
  lines.push(roleVar('success', roles.success));
  lines.push(roleVar('info', roles.info));

  // Spacing (brand-invariant geometry).
  for (const space of theme.spacing) {
    lines.push(`  --${space.name}: ${String(space.px)}px;`);
  }

  // Typography sizes + line-heights.
  for (const role of theme.typography) {
    lines.push(`  --font-size-${role.name}: ${r4(role.fontSizePx)}px;`);
    lines.push(`  --line-height-${role.name}: ${r4(role.lineHeight)};`);
  }

  // Motion durations + easing.
  for (const [token, ms] of Object.entries(theme.motion.durations)) {
    lines.push(`  --duration-${token.replace('.', '-')}: ${String(ms)}ms;`);
  }
  for (const [token, bezier] of Object.entries(theme.motion.easing)) {
    lines.push(`  --ease-${token}: cubic-bezier(${bezier.join(', ')});`);
  }
  lines.push(`  --ease-emphasized-fallback: ${theme.motion.emphasizedLinearFallback};`);

  // z-index.
  for (const [token, z] of Object.entries(theme.motion.zIndex)) {
    lines.push(`  --z-${token}: ${String(z)};`);
  }

  return `:root {\n${lines.join('\n')}\n}`;
}
