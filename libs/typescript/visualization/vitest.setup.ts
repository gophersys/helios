// libs/typescript/visualization/vitest.setup.ts — the jsdom component-test setup.
//
// Registers @testing-library/jest-dom's matchers (toBeInTheDocument, toHaveAttribute, …) and auto-
// cleans the rendered DOM between tests, so each component test starts from a clean document. This
// is the in-process (jsdom) lane only; the browser a11y evidence runs under Playwright (tests-a11y).
//
// The hotspot-map is a pure SVG scatter (no bits-ui overlay, no scroll-lock); it needs no
// scrollIntoView / ResizeObserver shim, so this setup is the minimal jsdom registration.
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';

afterEach(() => {
  cleanup();
});
