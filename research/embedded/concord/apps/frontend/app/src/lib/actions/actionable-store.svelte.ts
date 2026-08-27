/**
 * Module-level state for the context-menu singleton.
 *
 * The `actionable` Svelte action posts "open the copy-link menu" events
 * to this store; `<ActionContextMenu />` (mounted once in the root
 * layout) subscribes and renders the menu at the click coordinates.
 *
 * Keeping this separate from `actionable.ts` lets us keep the action
 * file tiny and importable without side effects.
 */

import type { ActionableId } from './registry';

export interface ContextMenuRequest {
  id: ActionableId;
  label: string;
  x: number;
  y: number;
}

class ContextMenuState {
  request = $state<ContextMenuRequest | null>(null);

  open(req: ContextMenuRequest) {
    this.request = req;
  }

  close() {
    this.request = null;
  }
}

export const contextMenuState = new ContextMenuState();
