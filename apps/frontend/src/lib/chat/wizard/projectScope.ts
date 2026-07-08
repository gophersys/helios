// projectScope — the pure read of an AI-proposed ProductConfig into the create-flow's two visual
// reveals: the PLATFORM TARGETS the agent auto-selects ("this needs web + mobile + a service"), and
// the STACK chips ("built with Go, Svelte, Postgres"). It is deterministic and side-effect-free so
// the animated CreateProjectFlow stays a pure view and this logic is unit-testable on its own.
//
// "Targets" are presented against a FIXED palette (web/mobile/desktop/service/cli) so the flow can
// animate the agent SELECTING the relevant ones out of the full set — the user watches Eden pick.

import type { ProductConfig } from '$lib/gateway/types';

/** One platform target in the create-flow palette. `selected` is the agent's auto-pick for a given
 *  proposal; the unselected ones still render (dimmed) so the selection reads as a choice. */
export interface PlatformTarget {
  id: 'web' | 'mobile' | 'desktop' | 'service' | 'cli';
  label: string;
  /** A one-line "what this means" shown under the label on the selected chips. */
  hint: string;
  selected: boolean;
}

/** One stack chip in the second reveal (a language, framework, or service), tagged by role so the
 *  view can group/colour them. */
export interface StackChip {
  label: string;
  role: 'language' | 'framework' | 'service';
}

// The fixed target palette, in display order. The flow renders all five; deriveTargets marks which
// the proposal selects.
const PALETTE: ReadonlyArray<Omit<PlatformTarget, 'selected'>> = [
  { id: 'web', label: 'Web', hint: 'A responsive web app' },
  { id: 'mobile', label: 'Mobile', hint: 'iOS + Android' },
  { id: 'desktop', label: 'Desktop', hint: 'A native desktop build' },
  { id: 'service', label: 'Service', hint: 'An API + backend' },
  { id: 'cli', label: 'CLI', hint: 'A command-line tool' },
];

const includesAny = (haystack: string[], needles: string[]): boolean =>
  haystack.some((value) => needles.some((needle) => value.includes(needle)));

/** deriveTargets reads a proposal into the selected platform set, evaluated against the fixed
 *  palette so the flow can animate the agent's pick. The mapping is intentionally generous (a
 *  proposal is a starting point, not a contract): product kind drives the primary target, and the
 *  proposed frameworks widen it (a Flutter app is also mobile; a Tauri app is also desktop). The
 *  result always selects at least one target (a service is Eden's default build shape). */
export function deriveTargets(config: ProductConfig): PlatformTarget[] {
  const frameworks = config.stack.frameworks.map((value) => value.toLowerCase());
  const languages = config.stack.languages.map((value) => value.toLowerCase());
  const kind = config.productKind;

  const selected = new Set<PlatformTarget['id']>();

  if (
    kind === 'ui' ||
    kind === 'application' ||
    includesAny(frameworks, [
      'svelte',
      'react',
      'vue',
      'next',
      'astro',
      'solid',
      'angular',
      'remix',
    ])
  ) {
    selected.add('web');
  }
  if (
    includesAny(frameworks, [
      'flutter',
      'react-native',
      'expo',
      'swiftui',
      'kotlin',
      'ionic',
      'capacitor',
    ])
  ) {
    selected.add('mobile');
  }
  if (includesAny(frameworks, ['electron', 'tauri', 'wails', 'qt'])) {
    selected.add('desktop');
  }
  if (kind === 'cli') {
    selected.add('cli');
  }
  if (
    kind === 'service' ||
    kind === 'library' ||
    includesAny(languages, ['go', 'rust', 'java', 'python', 'kotlin', 'csharp', 'c#'])
  ) {
    selected.add('service');
  }

  // A proposal always resolves to something buildable — default to a service when nothing matched.
  if (selected.size === 0) {
    selected.add('service');
  }

  return PALETTE.map((target) => ({ ...target, selected: selected.has(target.id) }));
}

/** deriveStack reads a proposal into the flat, ordered chip list for the second reveal: languages
 *  first, then frameworks, then services — de-duplicated, blanks dropped. */
export function deriveStack(config: ProductConfig): StackChip[] {
  const chips: StackChip[] = [];
  const seen = new Set<string>();
  const push = (label: string, role: StackChip['role']): void => {
    const trimmed = label.trim();
    const key = `${role}:${trimmed.toLowerCase()}`;
    if (!trimmed || seen.has(key)) return;
    seen.add(key);
    chips.push({ label: trimmed, role });
  };
  for (const language of config.stack.languages) push(language, 'language');
  for (const framework of config.stack.frameworks) push(framework, 'framework');
  for (const service of config.services) push(service, 'service');
  return chips;
}
