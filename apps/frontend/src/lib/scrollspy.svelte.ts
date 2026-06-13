// Scrollspy for the document outline (doc 12 §5 reading paths; REQ-0028 outline
// acceptance). Given the ordered list of in-page anchor ids the outline points at,
// it reports which one is "active" — the section the reader is currently looking
// at — so the table-of-contents can highlight it as the page scrolls. It is a
// Svelte attachment-free helper: a small reactive class the outline instantiates
// and feeds the heading ids, observing each heading element with one shared
// IntersectionObserver.
//
// The active id is the last heading whose top has crossed an upper reading line
// (so a heading is "current" from the moment its body enters the comfortable
// reading zone until the next heading takes over). This matches the Notion/Stripe
// reading mechanic: the outline tracks where the eye is, not merely what is barely
// on screen. Server-side rendering has no DOM, so every method is a no-op until
// `observe` runs in the browser.

// One observed entry: the anchor id (matches the outline's href target) and the
// element currently carrying it, plus its last-known distance from the reading
// line, recomputed on each observer callback.
interface ObservedHeading {
  readonly id: string;
  element: Element;
}

export class Scrollspy {
  // The id the outline should highlight, or '' before the first measurement.
  activeId = $state('');

  private observer: IntersectionObserver | null = null;
  private headings: ObservedHeading[] = [];
  // The set of ids whose element is currently intersecting the reading band; the
  // active id is the topmost (document-order-first) of these, falling back to the
  // last heading scrolled past when nothing is in band (e.g. between sections).
  private readonly visible = new Set<string>();

  // Begin observing the elements for the given ids, in document order. Called from
  // an $effect in the outline so it re-runs when the document (and thus its ids)
  // changes; it tears down the prior observer first so switching documents does
  // not leak observers or stale headings.
  observe(ids: string[]): void {
    this.disconnect();
    if (typeof document === 'undefined' || ids.length === 0) return;

    const elements: ObservedHeading[] = [];
    for (const id of ids) {
      const element = document.getElementById(id);
      if (element) elements.push({ id, element });
    }
    this.headings = elements;
    if (elements.length === 0) return;

    // The reading band: from 12% below the top of the viewport to the bottom. A
    // heading is "in band" once its top passes the 12% line, so the active entry
    // updates as a section's body — not just its first pixel — enters the read zone.
    this.observer = new IntersectionObserver((entries) => this.onIntersect(entries), {
      rootMargin: '-12% 0px -55% 0px',
      threshold: 0,
    });
    for (const heading of elements) this.observer.observe(heading.element);

    // Seed the active id immediately so the outline highlights before the first
    // scroll (the topmost heading whose element is at or above the reading line).
    this.recomputeActive();
  }

  // Stop observing and clear state. Idempotent; safe to call on teardown.
  disconnect(): void {
    this.observer?.disconnect();
    this.observer = null;
    this.headings = [];
    this.visible.clear();
  }

  private onIntersect(entries: IntersectionObserverEntry[]): void {
    for (const entry of entries) {
      const id = entry.target.id;
      if (entry.isIntersecting) this.visible.add(id);
      else this.visible.delete(id);
    }
    this.recomputeActive();
  }

  // The active id: the first heading (in document order) currently in the reading
  // band. When none is in band — the reader is mid-section between two headings, or
  // scrolled past the last one — keep the last heading whose top is above the band,
  // so the outline never blanks out in long bodies.
  private recomputeActive(): void {
    for (const heading of this.headings) {
      if (this.visible.has(heading.id)) {
        this.activeId = heading.id;
        return;
      }
    }
    // Nothing in band: choose the last heading whose top is above the band line.
    if (typeof window === 'undefined') return;
    const line = window.innerHeight * 0.12;
    let candidate = this.headings[0]?.id ?? '';
    for (const heading of this.headings) {
      const top = heading.element.getBoundingClientRect().top;
      if (top <= line) candidate = heading.id;
      else break;
    }
    this.activeId = candidate;
  }
}
