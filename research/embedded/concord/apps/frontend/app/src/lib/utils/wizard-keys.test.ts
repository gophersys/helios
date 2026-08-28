import { describe, it, expect, vi } from 'vitest';
import { makeWizardKeyHandler } from './wizard-keys';

function fakeKeyEvent(
  key: string,
  opts: { tagName?: string; isContentEditable?: boolean; closest?: () => Element | null; modifiers?: Partial<KeyboardEvent> } = {},
): KeyboardEvent {
  const target = {
    tagName: opts.tagName ?? 'DIV',
    isContentEditable: opts.isContentEditable ?? false,
    closest: opts.closest ?? (() => null),
  };
  return {
    key,
    target: target as unknown as EventTarget,
    preventDefault: vi.fn(),
    shiftKey: false,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    ...opts.modifiers,
  } as unknown as KeyboardEvent;
}

describe('makeWizardKeyHandler', () => {
  it('calls onEnter when Enter pressed outside text-consuming elements', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    const e = fakeKeyEvent('Enter');
    handler(e);
    expect(onEnter).toHaveBeenCalledOnce();
    expect(e.preventDefault).toHaveBeenCalled();
  });

  it('does NOT call onEnter when focused inside a textarea', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    handler(fakeKeyEvent('Enter', { tagName: 'TEXTAREA' }));
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('does NOT call onEnter when focused inside a select', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    handler(fakeKeyEvent('Enter', { tagName: 'SELECT' }));
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('does NOT call onEnter when focused inside a contenteditable element', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    handler(fakeKeyEvent('Enter', { isContentEditable: true }));
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('does NOT call onEnter when focused inside a CodeMirror editor', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    const inEditor = fakeKeyEvent('Enter', {
      closest: (() => ({}) as Element) as () => Element | null,
    });
    handler(inEditor);
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('lets buttons handle Enter natively (treats as click)', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    handler(fakeKeyEvent('Enter', { tagName: 'BUTTON' }));
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('ignores Enter with modifier keys held', () => {
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter }));
    handler(fakeKeyEvent('Enter', { modifiers: { shiftKey: true } }));
    handler(fakeKeyEvent('Enter', { modifiers: { ctrlKey: true } }));
    handler(fakeKeyEvent('Enter', { modifiers: { metaKey: true } }));
    handler(fakeKeyEvent('Enter', { modifiers: { altKey: true } }));
    expect(onEnter).not.toHaveBeenCalled();
  });

  it('calls onEscape on Escape regardless of focus', () => {
    const onEscape = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEscape }));
    handler(fakeKeyEvent('Escape', { tagName: 'TEXTAREA' }));
    expect(onEscape).toHaveBeenCalledOnce();
  });

  it('does nothing when disabled', () => {
    const onEnter = vi.fn();
    const onEscape = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter, onEscape, disabled: true }));
    handler(fakeKeyEvent('Enter'));
    handler(fakeKeyEvent('Escape'));
    expect(onEnter).not.toHaveBeenCalled();
    expect(onEscape).not.toHaveBeenCalled();
  });

  it('reads disabled flag fresh each call (live getter)', () => {
    let disabled = true;
    const onEnter = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter, disabled }));
    handler(fakeKeyEvent('Enter'));
    expect(onEnter).not.toHaveBeenCalled();
    disabled = false;
    handler(fakeKeyEvent('Enter'));
    expect(onEnter).toHaveBeenCalledOnce();
  });

  it('ignores other keys', () => {
    const onEnter = vi.fn();
    const onEscape = vi.fn();
    const handler = makeWizardKeyHandler(() => ({ onEnter, onEscape }));
    handler(fakeKeyEvent('a'));
    handler(fakeKeyEvent('Tab'));
    handler(fakeKeyEvent('ArrowDown'));
    expect(onEnter).not.toHaveBeenCalled();
    expect(onEscape).not.toHaveBeenCalled();
  });
});
