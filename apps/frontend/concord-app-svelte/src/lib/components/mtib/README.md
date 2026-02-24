# MTIB Monitoring Components

Real-time visualization components for MTIB (Manufacturing Test Interface Board) observability and logic analyzer data.

## Components

### PowerMonitorCard

Real-time power monitoring with dual line charts for voltage and current.

**Features:**
- Dual charts: voltage (0-5V) and current (0-1000mA)
- 60-second rolling window (600 samples at 10Hz)
- Per-channel visibility toggles
- Current readings table with color-coded channels
- CSV export
- Canvas-based rendering for performance

**Usage:**
```svelte
<script>
  import { PowerMonitorCard } from '$lib/components/mtib';
</script>

<PowerMonitorCard nodeId="mtib-001" />
<!-- OR filter specific channels -->
<PowerMonitorCard nodeId="mtib-001" channels={[0, 1]} />
```

**Props:**
- `nodeId: string` - MTIB node identifier (required)
- `channels?: number[]` - Filter specific power channels (optional, defaults to all)

---

### GpioStateCard

Visual GPIO pin state indicators with direction and value display.

**Features:**
- Grid layout (responsive: 2-6 columns)
- Color-coded states: HIGH (green), LOW (gray)
- Direction indicators (INPUT/OUTPUT)
- Pin labels (P0.00, P0.01, etc.)
- Real-time updates

**Usage:**
```svelte
<script>
  import { GpioStateCard } from '$lib/components/mtib';
</script>

<GpioStateCard nodeId="mtib-001" />
```

**Props:**
- `nodeId: string` - MTIB node identifier (required)

---

### AdcReadingsCard

ADC channel readings with horizontal bar graphs and min/max tracking.

**Features:**
- Per-channel voltage bars (0-5V range)
- Min/max/current value tracking
- Update rate indicator
- CSV export
- Responsive layout

**Usage:**
```svelte
<script>
  import { AdcReadingsCard } from '$lib/components/mtib';
</script>

<AdcReadingsCard nodeId="mtib-001" />
<!-- OR filter specific channels -->
<AdcReadingsCard nodeId="mtib-001" channels={[0, 1, 2]} />
```

**Props:**
- `nodeId: string` - MTIB node identifier (required)
- `channels?: number[]` - Filter specific ADC channels (optional, defaults to all)

---

### AnalyzerWaveformViewer

Logic analyzer waveform viewer with zoom, pan, and export capabilities.

**Features:**
- Canvas-based waveform rendering (8 digital channels)
- Zoom controls (1x to 10x)
- Pan support (drag when zoomed)
- Channel legend with color coding
- Export to CSV and VCD formats
- Real-time capture progress
- Time markers (nanoseconds/microseconds)

**Usage:**
```svelte
<script>
  import { AnalyzerWaveformViewer } from '$lib/components/mtib';
  import { analyzerStore } from '$lib/stores/analyzer.svelte';
  import { onMount } from 'svelte';

  const captureId = crypto.randomUUID();

  onMount(() => {
    // Start capture
    analyzerStore.startCapture('mtib-001', captureId);

    return () => {
      analyzerStore.stopCapture();
    };
  });
</script>

<AnalyzerWaveformViewer {captureId} />
<!-- OR filter specific channels -->
<AnalyzerWaveformViewer {captureId} channels={[0, 1, 2, 3]} />
```

**Props:**
- `captureId: string` - Unique capture session identifier (required)
- `channels?: number[]` - Filter specific digital channels (optional, defaults to [0-7])

---

## Design System

All components use design tokens from the Tailwind config:

**Backgrounds:**
- `bg-surface-0` - Deepest background
- `bg-surface-1` - Card background
- `bg-surface-2` - Elevated/hover state
- `bg-surface-3` - Loading skeletons

**Text:**
- `text-text-primary` - Primary text
- `text-text-secondary` - Secondary text
- `text-text-tertiary` - Muted text

**Status Colors:**
- `text-accent` / `bg-accent` - Primary accent (blue)
- `text-success` / `bg-success` - Success state (green)
- `text-error` / `bg-error` - Error state (red)
- `text-warning` / `bg-warning` - Warning state (amber)

**Borders:**
- `border-surface-2` - Default border
- `border-accent` - Active/focused border

---

## Accessibility

All components include:
- ARIA labels for interactive elements
- Semantic HTML
- Keyboard navigation support
- Focus indicators
- Screen reader announcements for state changes

---

## Performance Notes

- **Canvas rendering**: PowerMonitorCard and AnalyzerWaveformViewer use Canvas for performance with large datasets
- **Ring buffer**: PowerMonitorCard limits data to 600 samples to prevent memory growth
- **Reactive updates**: Components use Svelte 5 runes for efficient reactivity
- **CSS animations**: Loading states use GPU-accelerated CSS animations

---

## Example Integration

Full page example:

```svelte
<script lang="ts">
  import {
    PowerMonitorCard,
    GpioStateCard,
    AdcReadingsCard,
    AnalyzerWaveformViewer
  } from '$lib/components/mtib';
  import { analyzerStore } from '$lib/stores/analyzer.svelte';
  import { onMount, onDestroy } from 'svelte';

  const nodeId = 'mtib-001';
  const captureId = crypto.randomUUID();

  onMount(() => {
    // Start analyzer capture
    analyzerStore.startCapture(nodeId, captureId);
  });

  onDestroy(() => {
    analyzerStore.stopCapture();
  });
</script>

<div class="container mx-auto p-6 space-y-6">
  <h1 class="text-3xl font-bold text-text-primary">MTIB Dashboard</h1>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <PowerMonitorCard {nodeId} />
    <GpioStateCard {nodeId} />
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <AdcReadingsCard {nodeId} />
  </div>

  <AnalyzerWaveformViewer {captureId} />
</div>
```
