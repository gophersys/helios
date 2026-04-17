import { describe, it, expect, beforeEach, vi } from 'vitest';
import { actionable } from './actionable';
import { contextMenuState } from './actionable-store.svelte';

describe('actionable Svelte action', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    contextMenuState.close();
  });

  it('stamps data-action on the element', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    actionable(el, { id: 'upload-fw', label: 'Upload firmware' });
    expect(el.getAttribute('data-action')).toBe('upload-fw');
  });

  it('opens the context menu on right-click', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    actionable(el, { id: 'upload-fw', label: 'Upload firmware' });

    const evt = new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: true,
      clientX: 100,
      clientY: 200,
    });
    el.dispatchEvent(evt);

    expect(contextMenuState.request).not.toBeNull();
    expect(contextMenuState.request?.id).toBe('upload-fw');
    expect(contextMenuState.request?.label).toBe('Upload firmware');
    expect(contextMenuState.request?.x).toBe(100);
    expect(contextMenuState.request?.y).toBe(200);
    expect(evt.defaultPrevented).toBe(true);
  });

  it('falls back to the id when label is omitted', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    actionable(el, { id: 'new-product' });

    el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true }));
    expect(contextMenuState.request?.label).toBe('new-product');
  });

  it('respects disableContextMenu', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    actionable(el, { id: 'upload-fw', disableContextMenu: true });

    const evt = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
    el.dispatchEvent(evt);

    expect(contextMenuState.request).toBeNull();
    expect(evt.defaultPrevented).toBe(false);
  });

  it('update() replaces data-action when id changes', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    const instance = actionable(el, { id: 'upload-fw' });
    expect(el.getAttribute('data-action')).toBe('upload-fw');

    instance.update({ id: 'new-product' });
    expect(el.getAttribute('data-action')).toBe('new-product');
  });

  it('destroy() removes the listener and the attribute', () => {
    const el = document.createElement('button');
    document.body.appendChild(el);
    const instance = actionable(el, { id: 'upload-fw' });

    instance.destroy();

    expect(el.hasAttribute('data-action')).toBe(false);
    const spy = vi.spyOn(contextMenuState, 'open');
    el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true }));
    expect(spy).not.toHaveBeenCalled();
  });
});
