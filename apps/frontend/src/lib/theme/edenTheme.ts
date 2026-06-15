// The app's single generated Eden theme — the C21 brand identity expanded FROM THE MATH
// (@eden/theme generateTheme(C21_SEED)). MATH IS SOURCE OF TRUTH (ADR-0024): the five locked
// C21 colors + three fonts are SEEDS; every role color, type size, spacing step, motion token is
// DERIVED here, never hand-set. One home: this module owns the app's theme so the +layout injects
// the SAME tokens it hands the @eden/primitives components, and `var(--color-*)` resolves app-wide
// off the generator (not a hand-maintained palette).

import { generateTheme, themeToCssVariables, C21_SEED, type Theme } from '@eden/theme';

/** The light-mode C21 theme — the default surface the chat renders on. Generated once (pure). */
export const edenLightTheme: Theme = generateTheme(C21_SEED, { mode: 'light' });

/** The dark-mode C21 theme — the SAME five seeds resolved for the dark surface, contrast-gated. */
export const edenDarkTheme: Theme = generateTheme(C21_SEED, { mode: 'dark' });

/** The active theme the chat hands every primitive. Light-first (the founder's paper-ink anchor);
 *  a host swapping this re-derives every color the components paint (they never cache a literal). */
export const edenTheme: Theme = edenLightTheme;

/** The light `:root` custom-property block (the runtime substrate — `--color-*`, `--space-*`,
 *  `--font-size-*`, `--duration-*`, `--ease-*`, `--z-*`). Emitted by the generator, never authored. */
export const edenLightCss: string = themeToCssVariables(edenLightTheme);

/** The dark custom-property block, scoped under the dark selector by the caller. */
export const edenDarkCss: string = themeToCssVariables(edenDarkTheme);
