# Concord Design System

**Last reviewed:** 2026-04-11
**Status:** Active

Concord is an internal hardware testing platform. The UI is data-dense, technical, and built for engineers who spend hours in it. Every decision optimizes for scannability, information density, and visual calm.

The aesthetic target: Linear meets Vercel Dashboard. Neutral surfaces, one warm accent color, lots of whitespace, no decoration.

---

## Visual Theme

**Personality:** Precise, technical, calm.
Neutral grey surfaces with a single warm coral-orange accent (#CF6A3E). No gradients, no illustrations, no visual noise. The UI should feel like a well-designed instrument panel — every element earns its space.

**Influences:** Linear (information density), Stripe Dashboard (typography hierarchy), Vercel (spacing rhythm), Anthropic Console (surface layering).

---

## Color Palette

### Surfaces (Light)

| Token | Hex | Usage |
|-------|-----|-------|
| `surface-0` | #F5F5F7 | Page background, input backgrounds |
| `surface-1` | #FFFFFF | Cards, panels, elevated content |
| `surface-2` | #F0F0F3 | Hover states, table headers, secondary backgrounds |
| `surface-3` | #E6E6EB | Pressed states, active backgrounds |

### Surfaces (Dark)

| Token | Hex | Usage |
|-------|-----|-------|
| `surface-0` | #151518 | Page background |
| `surface-1` | #1E1E23 | Cards, panels |
| `surface-2` | #28282F | Hover states, table headers |
| `surface-3` | #313139 | Pressed states |

### Text

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `text-primary` | #1A1A1A | #EDEDF0 | Headings, body text, values |
| `text-secondary` | #636370 | #A0A0AC | Descriptions, secondary info |
| `text-tertiary` | #9494A0 | #6A6A76 | Labels, placeholders, disabled text |

### Accent (Coral-Orange)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `accent` | #CF6A3E | #E8845C | Primary buttons, links, active indicators |
| `accent-hover` | #BE5E35 | #EE9570 | Hover state for accent elements |
| `accent-muted` | rgba(207,106,62,0.08) | rgba(232,132,92,0.10) | Badge backgrounds, subtle highlights |

### Status Colors

| Role | Color | Muted BG | Usage |
|------|-------|----------|-------|
| Success | `#3D8B4D` | `rgba(61,139,77,0.08)` | Passed, online, healthy, created |
| Warning | `#B8922F` | `rgba(184,146,47,0.08)` | Degraded, pending, in progress |
| Error | `#B93A2A` | `rgba(185,58,42,0.08)` | Failed, offline, deleted |
| Info | `#4A729B` | `rgba(74,114,155,0.08)` | Informational, queued, building |

### Borders

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `border` | #DCDCE2 | #2E2E36 | Card borders, input borders, dividers |
| `border-subtle` | #E8E8ED | #252530 | Table row dividers, section separators |

---

## Typography

Font stack: **Inter Variable** for UI text, **JetBrains Mono** for code/IDs, **Poppins** for brand text only.

### Scale (Major Third — 1.25 ratio)

| Name | Size | Line Height | Usage |
|------|------|-------------|-------|
| `text-2xs` | 11px | 16px | Badges, metadata, tiny labels |
| `text-xs` | 12px | 18px | Labels, timestamps, helper text |
| `text-sm` | 14px | 22px | **Default body text**, table cells, form inputs |
| `text-base` | 16px | 24px | Large buttons, emphasized content |
| `text-lg` | 18px | 28px | Section headings within pages |
| `text-xl` | 20px | 30px | Page titles |
| `text-2xl` | 24px | 32px | Hero numbers, dashboard stats |

### Weight Rules

- **Regular (400):** Body text, descriptions, table cells
- **Medium (500):** Labels, badge text, nav items, brand text (Poppins)
- **Semibold (600):** Headings at every level, card titles, column headers
- **Bold (700):** Stage numbers in circles, nothing else

### Hierarchy (What to Use Where)

| Element | Classes |
|---------|---------|
| Page title | `text-xl font-semibold text-text-primary` |
| Page description | `text-sm text-text-secondary` |
| Section heading | `text-sm font-semibold text-text-primary` |
| Card title | `text-sm font-semibold text-text-primary` |
| Table column header | `text-2xs font-medium uppercase tracking-wider text-text-tertiary` |
| Body text | `text-sm text-text-primary` |
| Secondary text | `text-sm text-text-secondary` |
| Label / metadata | `text-xs text-text-secondary` |
| Tiny label / badge | `text-2xs font-medium` |
| Monospace IDs | `font-mono text-2xs text-text-tertiary` |

---

## Spacing

### Grid

Every dimension is a multiple of **4px**. The standard spacing values:

| Tailwind | Pixels | Usage |
|----------|--------|-------|
| `1` | 4px | Icon-to-text gap, tight inline spacing |
| `1.5` | 6px | Form label to input |
| `2` | 8px | Between related items in a row, pill padding |
| `3` | 12px | Between items in a list, small card padding |
| `4` | 16px | Standard card padding (compact), grid gaps |
| `5` | 20px | Card padding (standard — only in card-md) |
| `6` | 24px | Page content padding, section spacing, card padding (large) |
| `8` | 32px | Major section separation |

### Layout Spacing Rules

| Context | Value | Tailwind |
|---------|-------|----------|
| Page outer padding | 24px | `p-6` |
| Between page header and content | 24px | `mb-6` on header |
| Between major sections | 24px | `space-y-6` or `gap-6` |
| Between items within a section | 16px | `space-y-4` or `gap-4` |
| Between heading and its content | 12px | `mb-3` |
| Within a card, between elements | 12px | `space-y-3` |
| Between inline items | 8px | `gap-2` |
| Filter bar internal gaps | 8px | `gap-2` |

---

## Component Patterns

### Cards

Every bounded content region is a card. Three sizes:

| Class | Padding | Usage |
|-------|---------|-------|
| `card card-sm` | 16px | Compact dashboard stats, sidebar items |
| `card card-md` | 20px | Standard cards, form containers |
| `card card-lg` | 24px | Feature panels, detail views |

Base styling: `rounded-lg border border-border bg-surface-1`
Interactive variant: `card-interactive` adds hover shadow and pointer cursor.

### Buttons

| Class | Height | Usage |
|-------|--------|-------|
| `btn btn-sm` | 32px | Inline actions, table row actions |
| `btn btn-md` | 40px | Standard form buttons, toolbar actions |
| `btn btn-lg` | 48px | Primary page actions, hero CTAs |

Variants: `btn-primary` (accent bg), `btn-secondary` (surface bg), `btn-ghost` (transparent), `btn-danger` (error).

### Inputs

| Class | Height | Usage |
|-------|--------|-------|
| `input input-sm` | 32px | Compact forms, filter inputs |
| `input input-md` | 40px | Standard forms (default) |
| `input input-lg` | 48px | Prominent inputs, search bars |

Focus state: `border-accent` with `box-shadow: 0 0 0 3px var(--accent-muted)`.

### Tables

```
.table-wrapper > table
  thead > tr.table-header > th  (40px row, text-2xs uppercase)
  tbody > tr.table-row > td.table-cell  (48px row, text-sm)
```

Always: `table-wrapper` for border/radius/overflow. Rows alternate `bg-surface-1`. Interactive rows get `table-row-interactive` for hover.

### Badges

Inline status indicators. Always `text-2xs font-medium`.

| Class | Usage |
|-------|-------|
| `badge badge-accent` | Primary/active states |
| `badge badge-success` | Passed, online, healthy |
| `badge badge-warning` | Pending, in progress |
| `badge badge-error` | Failed, offline, error |
| `badge badge-info` | Building, queued, informational |
| `badge badge-neutral` | Default, unknown, misc |

Use `<StatusBadge status={status} />` component — it maps 50+ status strings to the correct badge.

### Filter Bars

Every list page has a FilterBar above the content:

```svelte
<FilterBar>
  {#snippet filters()}
    <FilterSelect label="Status" ... />
    <FilterSearch placeholder="Search..." />
  {/snippet}
  <span class="ml-auto text-2xs text-text-tertiary">{count} items</span>
</FilterBar>
```

### Empty States

Centered, with a muted icon, primary message, and optional secondary text:

```svelte
<EmptyState message="No items found." />
```

### Page Structure

Every page follows:

```svelte
<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader title="Page Name" description="One-line description." />
  </div>
  <ErrorAlert message={error} />
  <FilterBar>...</FilterBar>
  <!-- Content -->
</div>
```

---

## Depth & Elevation

One depth strategy: **borders, not shadows.** Cards use `border border-border`. Shadows are reserved for:

- **Hover state** on interactive cards: `shadow-card-hover`
- **Modals**: `shadow-modal`
- **Dropdowns**: `shadow-elevated`

Never combine a border AND a shadow on the same resting element.

---

## Border Radius

One radius for almost everything: `rounded-lg` (12px). Exceptions:

| Element | Radius | Tailwind |
|---------|--------|----------|
| Cards, modals, panels | 12px | `rounded-lg` |
| Buttons, inputs, badges | 8px | `rounded-md` or `rounded-lg` |
| Avatars, status dots | 9999px | `rounded-full` |
| Stage number circles | 6px | `rounded` |

Never mix `rounded-xl` and `rounded-lg` on sibling elements.

---

## Icons

Lucide icons exclusively. Size scaling:

| Context | Size | Tailwind |
|---------|------|----------|
| Inline with text-2xs | 12px | `size={12}` |
| Inline with text-sm | 14-16px | `size={14}` or `size={16}` |
| Section/card headers | 16-20px | `size={16}` or `size={20}` |
| Empty states | 24-32px | `size={24}` with `opacity-30` |

---

## Responsive Behavior

Concord is desktop-first (engineers on large monitors). Breakpoints:

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Default | ≥1280px | Full layout, sidebar visible |
| `lg` | 1024px | Grid columns collapse |
| `md` | 768px | Sidebar collapsible, single column |
| `sm` | 640px | Compact spacing, stacked layouts |

Most content uses `grid-cols-1 lg:grid-cols-2` or similar. Never assume mobile-first.

---

## Do's and Don'ts

### Do

- Use design token classes (`bg-surface-1`, `text-text-secondary`) for all colors
- Use component classes (`card card-md`, `btn btn-primary`) for all interactive elements
- Keep card padding consistent — pick one size class per context
- Use `StatusBadge` for all status indicators
- Use `text-sm` as the default body text size
- Use `gap-` on flex/grid instead of margin on children
- Put counts and totals in the filter bar's right side

### Don't

- Use raw hex colors (`#333`, `#ccc`) — always use token utilities
- Use `p-5` or `p-7` — they break the 4px grid rhythm (use `p-4`, `p-6`, `p-8`)
- Nest cards inside cards — flatten the hierarchy
- Use arbitrary values like `w-[347px]` — snap to the grid or use percentage/flex
- Add decorative gradients, patterns, or background images
- Use different border-radius values on sibling elements
- Use shadows on elements that already have borders (pick one depth strategy)
- Mix font families (Inter is for everything except brand marks and code)
- Use `rounded-xl` on cards — `rounded-lg` is the standard
