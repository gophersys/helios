/**
 * `use:actionable` Svelte action.
 *
 * Usage:
 *   <button
 *     use:actionable={{ id: 'upload-fw', label: 'Upload firmware' }}
 *     onclick={...}
 *   >
 *     Upload .zip
 *   </button>
 *
 * What it does:
 *   1. Stamps `data-action="<id>"` on the element so the deep-link
 *      highlighter can find it.
 *   2. Hooks `contextmenu` to open a "Copy link" menu at the cursor.
 *
 * The right-click menu is rendered by `<ActionContextMenu />`, mounted
 * once in the root layout, which reads from `contextMenuState`.
 */

import { contextMenuState } from './actionable-store.svelte';
import type { ActionableId } from './registry';

export interface ActionableOptions {
  id: ActionableId;
  /**
   * Human-readable label for the context menu (e.g., "Upload firmware").
   * Falls back to the id if omitted.
   */
  label?: string;
  /** Disable the right-click handler (still stamps `data-action`). */
  disableContextMenu?: boolean;
}

export function actionable(node: HTMLElement, options: ActionableOptions) {
  let current: ActionableOptions = options;

  node.setAttribute('data-action', current.id);

  const onContextMenu = (event: MouseEvent) => {
    if (current.disableContextMenu) return;
    event.preventDefault();
    event.stopPropagation();
    contextMenuState.open({
      id: current.id,
      label: current.label ?? current.id,
      x: event.clientX,
      y: event.clientY,
    });
  };

  node.addEventListener('contextmenu', onContextMenu);

  return {
    update(newOptions: ActionableOptions) {
      if (newOptions.id !== current.id) {
        node.setAttribute('data-action', newOptions.id);
      }
      current = newOptions;
    },
    destroy() {
      node.removeEventListener('contextmenu', onContextMenu);
      node.removeAttribute('data-action');
    },
  };
}
