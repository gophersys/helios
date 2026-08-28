<!--
  @eden/primitives — SettingsSurface (ADR-0024 / doc 17 §4 organisms · §7 Settings).

  The sheet-hosted Settings organism doc 17 §4 names and §7 rules: a left SECTION RAIL (mono/eyebrow
  section labels with an active state) beside a CONTENT AREA rendered per active section via a snippet.
  It is a SELECTION of the existing overlay behavior layer — the OVERLAY / FOCUS TRAP / SCROLL LOCK /
  ESCAPE-to-close / focus-return-to-trigger are delegated ENTIRELY to the bits-ui `Dialog` primitive
  (the SAME RD-16/OD-1-ratified layer the Eden Dialog composes). This organism REINVENTS NOTHING: it
  does not hand-roll a focus trap, an Escape handler, or a scrim — it wires the rail + the per-section
  content into `Dialog.Portal`, and the tokens ride the SAME portal seam (an inline `style` custom-
  property string bound onto the portaled Overlay + Content, so Eden tokens inherit THROUGH the portal).

  THE APPEARANCE is decided entirely by `deriveSettingsSurfaceTokens` (settings-surface/tokens.ts):
  every colour/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token.
  This template carries NO literal colour and NO literal px — it references `var(--eden-settings-surface-*)`
  only. The rail label is the MONO data voice; the section title the SANS interface voice (P-D4).

  ARIA (the dialog pattern): the Content is `Dialog.Content` (role="dialog" + aria-modal via bits-ui),
  named by `Dialog.Title`; the rail is a `tablist` of `tab` buttons (the ACTIVE row carries
  `aria-current="page"` + the accent so the selection reads without colour being the only channel), and
  the content area is a `<section>` landmark labelled by the active section's rail label (aria-labelledby)
  — the SR announces which section is showing. The consumer supplies the sections + the content snippet.
-->
<script lang="ts">
  import { Dialog as BitsDialog } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import {
    deriveSettingsSurfaceTokens,
    settingsSurfaceStyleVars,
    type SettingsSection,
  } from './tokens.js';

  interface SettingsSurfaceProps {
    /** The ordered sections — one entry per rail item (the rail's length + labels). */
    sections: readonly SettingsSection[];
    /** The active section id — selects which section's content the area renders (bindable). */
    active: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** Controlled open state (bindable); the sheet is portaled + focus-trapped when open. */
    open?: boolean;
    /** Open-state change handler (fires on every open/close, incl. Escape and outside-click). */
    onOpenChange?: (open: boolean) => void;
    /** Section-change handler — fired when the user picks a rail item (the consumer may also bind active). */
    onSectionChange?: (id: string) => void;
    /** The accessible title for the settings sheet (rendered into `Dialog.Title`, announced by the SR). */
    title?: string;
    /** The per-section CONTENT — receives the ACTIVE section id, so the consumer renders that section's body. */
    content: Snippet<[string]>;
    /** Pass-through attributes (data-testid / any attr) spread onto the portaled sheet Content root —
     *  the app-migration seam (the app's e2e targets the sheet by a data-testid it puts here). */
    [key: string]: unknown;
  }

  // onOpenChange defaults to a no-op so the value forwarded to bits-ui is always a function (under
  // exactOptionalPropertyTypes an explicit `undefined` is not assignable to OnChangeFn<boolean>); a
  // caller's handler replaces it. bind:open still propagates the state to a caller's bound variable.
  let {
    sections,
    active = $bindable(),
    theme,
    open = $bindable(false),
    onOpenChange = () => undefined,
    onSectionChange = () => undefined,
    title = 'Settings',
    content,
    ...rest
  }: SettingsSurfaceProps = $props();

  // Derive the sheet tokens from the injected theme (or the C21 default). Reactive: a host swapping the
  // theme (light↔dark, density) re-derives every colour/size — never a cached literal.
  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const styleVars = $derived(settingsSurfaceStyleVars(deriveSettingsSurfaceTokens(resolvedTheme)));

  // A stable id base per instance for the region↔label link (SSR-consistent Svelte 5 rune). The active
  // section's rail button gets `${base}-tab-${id}`; the content region's aria-labelledby points at it.
  const uid = $props.id();
  const tabId = (id: string): string => `eden-settings-surface-${uid}-tab-${id}`;

  /** Select a section — set the active id + fire the intent. A total lookup (an unknown id simply does
   *  not match any rail item, and the content snippet renders whatever the consumer keys off `active`). */
  function select(id: string): void {
    active = id;
    onSectionChange(id);
  }
</script>

<BitsDialog.Root bind:open {onOpenChange}>
  <BitsDialog.Portal>
    <!-- The scrim + the sheet Content both carry the token style so they render THROUGH the portal
         with Eden tokens (the OD-1 seam). bits-ui owns the focus trap / scroll lock / Escape / focus
         return — this organism reinvents none of it. -->
    <BitsDialog.Overlay class="eden-settings-surface-scrim" style={styleVars} />
    <BitsDialog.Content
      class="eden-settings-surface"
      style={styleVars}
      data-eden-settings-surface=""
      data-active={active}
      {...rest}
    >
      <BitsDialog.Title class="eden-settings-surface-heading">{title}</BitsDialog.Title>
      <BitsDialog.Close class="eden-settings-surface-close" aria-label="Close settings"
        >×</BitsDialog.Close
      >

      <div class="eden-settings-surface-body">
        <!-- The left SECTION RAIL: a tablist of mono/eyebrow section labels; the active row carries the
             accent + aria-current, so the selection reads without colour being the only channel. The
             tab buttons are DIRECT children of the role="tablist" (the ARIA parent/child contract — no
             <li> wrappers, which would orphan the tab role). -->
        <div
          class="eden-settings-surface-rail"
          role="tablist"
          aria-orientation="vertical"
          aria-label="Settings sections"
        >
          {#each sections as section (section.id)}
            <button
              type="button"
              class="eden-settings-surface-rail-item"
              id={tabId(section.id)}
              role="tab"
              data-section={section.id}
              data-active={active === section.id}
              aria-selected={active === section.id}
              aria-current={active === section.id ? 'page' : undefined}
              onclick={() => {
                select(section.id);
              }}
            >
              {section.label}
            </button>
          {/each}
        </div>

        <!-- The CONTENT AREA: rendered per active section via the consumer's snippet. A <section> with
             aria-labelledby IS a region landmark (named by the active rail label), so the SR announces
             which section is showing — no redundant explicit role. -->
        <section class="eden-settings-surface-content" aria-labelledby={tabId(active)}>
          {@render content(active)}
        </section>
      </div>
    </BitsDialog.Content>
  </BitsDialog.Portal>
</BitsDialog.Root>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    settingsSurfaceStyleVars and bound onto the portaled element). There is NO literal colour and NO
    literal px here. `:global(...)` is the deliberate, correct scope: the Overlay/Content render INSIDE
    the bits-ui Portal (document.body), so Svelte's component-scoped hash is not on them; the namespaced
    `eden-settings-surface-*` classes are the stable join keys.

    The 44px AAA tap area on the rail rows + the close control is guaranteed by min-block-size:
    var(--eden-settings-surface-hit-target) (the theme's DECOUPLED hitTargetPx ≥ 44), independent of the
    visual glyph — a dense visual row never shrinks the accessible target (I1/I2, ADR-0024).
  */
  :global(.eden-settings-surface-scrim) {
    position: fixed;
    inset: 0;
    z-index: var(--eden-settings-surface-z);
    background: var(--eden-settings-surface-scrim);
  }

  :global(.eden-settings-surface) {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: var(--eden-settings-surface-z);

    box-sizing: border-box;
    inline-size: min(880px, 92vw);
    max-block-size: min(86vh, 720px);
    padding: var(--eden-settings-surface-padding);

    color: var(--eden-settings-surface-on-surface);
    background: var(--eden-settings-surface-surface);
    border: 1px solid var(--eden-settings-surface-outline);
    border-radius: var(--eden-settings-surface-radius);
    box-shadow: var(--eden-settings-surface-shadow);

    display: grid;
    grid-template-rows: auto 1fr;
    gap: var(--eden-settings-surface-gap);
  }

  :global(.eden-settings-surface-heading) {
    margin: 0;
    color: var(--eden-settings-surface-title);
    font-family: var(--eden-settings-surface-title-font-family);
    font-size: var(--eden-settings-surface-title-font-size);
    line-height: var(--eden-settings-surface-title-line-height);
    font-weight: 600;
  }

  :global(.eden-settings-surface-close) {
    position: absolute;
    top: var(--eden-settings-surface-gap);
    right: var(--eden-settings-surface-gap);

    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    min-block-size: var(--eden-settings-surface-hit-target);
    min-inline-size: var(--eden-settings-surface-hit-target);

    color: var(--eden-settings-surface-on-surface);
    background: var(--eden-settings-surface-surface);
    border: 1px solid var(--eden-settings-surface-outline);
    border-radius: var(--eden-settings-surface-item-radius);
    cursor: pointer;
  }

  :global(.eden-settings-surface-body) {
    display: grid;
    grid-template-columns: var(--eden-settings-surface-rail-width) 1fr;
    gap: var(--eden-settings-surface-gap);
    min-block-size: 0;
    overflow: hidden;
  }

  :global(.eden-settings-surface-rail) {
    border-inline-end: 1px solid var(--eden-settings-surface-outline);
    padding-inline-end: var(--eden-settings-surface-gap);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--eden-settings-surface-item-padding);
  }

  /* the rail item — the MONO eyebrow section label; the tap area never falls below the 44px AAA floor. */
  :global(.eden-settings-surface-rail-item) {
    inline-size: 100%;
    box-sizing: border-box;
    min-block-size: var(--eden-settings-surface-hit-target);
    display: flex;
    align-items: center;
    padding-inline: var(--eden-settings-surface-item-padding);
    text-align: start;

    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--eden-settings-surface-item-radius);

    color: var(--eden-settings-surface-label-inactive);
    font-family: var(--eden-settings-surface-label-font-family);
    font-size: var(--eden-settings-surface-label-font-size);
    line-height: var(--eden-settings-surface-label-line-height);
    font-weight: 500;
    letter-spacing: 0.04em;
    cursor: pointer;
  }

  :global(.eden-settings-surface-rail-item:hover) {
    color: var(--eden-settings-surface-label-active);
  }

  /* the ACTIVE rail item: the accent colour + a soft accent tint wash (colour is NOT the only channel —
     the label also gains weight + carries aria-current="page"). */
  :global(.eden-settings-surface-rail-item[data-active='true']) {
    color: var(--eden-settings-surface-label-active);
    background: var(--eden-settings-surface-active-tint);
    border-color: var(--eden-settings-surface-label-active);
    font-weight: 700;
  }

  :global(.eden-settings-surface-rail-item:focus-visible),
  :global(.eden-settings-surface-close:focus-visible) {
    outline: 2px solid var(--eden-settings-surface-label-active);
    outline-offset: 2px;
  }

  :global(.eden-settings-surface-content) {
    overflow-y: auto;
    min-inline-size: 0;
    color: var(--eden-settings-surface-on-surface);
  }
</style>
