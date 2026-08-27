// libs/typescript/primitives/vitest.setup.ts — the jsdom component-test setup.
//
// Registers @testing-library/jest-dom's matchers (toBeInTheDocument, toHaveStyle, …) and auto-
// cleans the rendered DOM between tests, so each component test starts from a clean document. This
// is the in-process (jsdom) lane only; the browser a11y evidence runs under Playwright (tests-a11y).
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/svelte';

// jsdom does not implement layout, so `Element.prototype.scrollIntoView` is undefined. The bits-ui
// Command primitive calls it to keep the active item in view on selection; in the in-process jsdom
// lane there is no scroll viewport to manage, so we install a no-op. The REAL scroll-into-view
// behavior (and its a11y consequence — the active option staying visible) is proven in the browser
// a11y lane (tests-a11y, real Chromium + WebKit), not in jsdom. Idempotent + only when absent, so it
// never shadows a real implementation in another environment.
if (typeof Element !== 'undefined' && typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = function scrollIntoView(): void {
    /* no-op: jsdom has no layout; the real behavior is covered by the browser a11y lane. */
  };
}

// jsdom does not implement `ResizeObserver` either; the bits-ui Command viewport uses it to size the
// scrollable results region. A no-op observer lets the component mount in jsdom (it never fires, but
// the layout it would drive does not exist in jsdom anyway). The real resize behavior — the viewport
// tracking the list height — is proven in the browser a11y lane. Installed only when absent.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe(): void {
      /* no-op (jsdom has no layout to observe; covered by the browser a11y lane). */
    }
    unobserve(): void {
      /* no-op */
    }
    disconnect(): void {
      /* no-op */
    }
  };
}

afterEach(async () => {
  cleanup();
  // bits-ui's body-scroll-lock (used by every Dialog-based overlay — Dialog, Popover, the command
  // palette) restores the body style on a SHORT setTimeout (24ms, to coalesce same-tick
  // destroy/create — bits-ui#1639). On unmount that timer is still pending; if the jsdom environment
  // tears down before it fires, the deferred callback touches a torn-down `document.body` and throws
  // a post-teardown unhandled error. Draining a macrotask longer than that delay here lets the
  // scroll-lock cleanup complete WHILE the document still exists, so multiple Dialog-based component
  // suites in one process tear down cleanly. (Real browser teardown — the a11y lane — has no such race.)
  await new Promise((resolve) => setTimeout(resolve, 32));
});
