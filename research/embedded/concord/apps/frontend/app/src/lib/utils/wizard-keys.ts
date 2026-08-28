/**
 * Shared keyboard handling for wizard/modal dialogs.
 *
 * Wires Enter to submit the primary action and Escape to cancel/close.
 * Mind the active element so Enter inside a `<textarea>` (or anything that
 * legitimately consumes Enter, e.g. CodeMirror, contenteditable) doesn't
 * accidentally fire the submit.
 */

export interface WizardKeyHandlers {
  /** Called on Enter when the active element doesn't consume it. */
  onEnter?: () => void;
  /** Called on Escape (always, regardless of focus). */
  onEscape?: () => void;
  /** When true, neither handler fires. Useful while submitting/loading. */
  disabled?: boolean;
}

const ENTER_CONSUMING_TAGS = new Set(['TEXTAREA', 'SELECT']);

/** Return true if the focused element should keep its native Enter behavior. */
function enterIsClaimed(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  if (ENTER_CONSUMING_TAGS.has(el.tagName)) return true;
  if (el.isContentEditable) return true;
  // CodeMirror / Monaco / similar embedded editors set this class on the root.
  if (el.closest?.('.cm-editor, .monaco-editor')) return true;
  // Buttons handle Enter natively as "click" — let them.
  if (el.tagName === 'BUTTON') return true;
  return false;
}

/**
 * Build a keydown handler suitable for `<svelte:window onkeydown={...} />`.
 *
 * Pass it the live wizard state via a getter callback so it can read the
 * latest `disabled` flag without recreating the handler on every render.
 */
export function makeWizardKeyHandler(get: () => WizardKeyHandlers) {
  return (e: KeyboardEvent) => {
    const handlers = get();
    if (handlers.disabled) return;

    if (e.key === 'Escape') {
      if (handlers.onEscape) {
        e.preventDefault();
        handlers.onEscape();
      }
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (enterIsClaimed(e.target)) return;
      if (handlers.onEnter) {
        e.preventDefault();
        handlers.onEnter();
      }
    }
  };
}
