/**
 * `@eden/visualization` — the codeinsight `Report` payload types (the CONSUMER half of the
 * abstraction seam). See docs/architecture/contracts/codeinsight.md §3 (Report schema) + §5 (Views
 * render-plan).
 *
 * `codeinsight` (the Go analyzer, the producer) walks a git repository and emits ONE self-describing
 * `Report`: per-entity static + behavioral metrics, pairwise logical coupling, repo-level ratings,
 * ownership, trends, and a `Views` render-plan. The `Report` JSON is the wire shape; these TypeScript
 * types mirror the Go struct's JSON tags EXACTLY so the analyzer (producer) and `@eden/visualization`
 * (consumer) build independently against the same contract — a frontend renders any repo's dashboard
 * with zero per-repo code (contract §1, §3).
 *
 * ONE CONCEPT, ONE HOME (10 §9): the wire shape is owned by the Go `codeinsight.Report`; this module
 * is the cited TypeScript projection of it, never a second source of truth. A producer field added at
 * the contract is mirrored here; this file does not invent fields the contract does not declare.
 *
 * Optionality maps the Go JSON tags: a `,omitempty` Go field is an OPTIONAL TypeScript property
 * (`field?:`) because the producer omits it when zero/absent; a non-omitempty field is required. A
 * Go pointer (`*float64`) that is `,omitempty` is `field?: number` (absent when nil). Numbers are Go
 * ints/float64 (both `number`); strings are RFC3339 / hex / free text per the contract comment.
 */

/** Where a `Report` was computed — the repository identity + the commit it was snapshotted at (§3). */
export interface RepositoryRef {
  /** Logical name (never a secret / a URL carrying credentials). */
  readonly identifier: string;
  /** The 40-hex commit the snapshot was taken at. */
  readonly headCommit: string;
  /** RFC3339; stamped by the caller's Clock. */
  readonly analyzedAt: string;
  readonly commitCount: number;
}

/** Which slice of history fed the temporal metrics — the analyzed commit range (§3). */
export interface Window {
  /** Lower commit bound (omitted → open-ended start). */
  readonly fromCommit?: string;
  /** Upper commit bound — usually {@link RepositoryRef.headCommit}. */
  readonly toCommit: string;
  /** RFC3339 lower bound (omitted when not time-bounded). */
  readonly since?: string;
  /** RFC3339 upper bound (omitted when not time-bounded). */
  readonly until?: string;
  /** Commits in the window. */
  readonly revisions: number;
}

/**
 * A per-file / per-package node — the unit the hotspot-map, enclosure, heatmap, and ownership-map
 * primitives render (contract §3). Every numeric datum is reproducible from `(repository, window)`.
 * The reserved (`omitempty`) fields fill as the analyzer's computation lands; this shape does not
 * change when they do (contract §4).
 */
export interface Entity {
  readonly path: string;
  /** `"file"` | `"directory"` | `"package"` (contract OD-CI-2: file is the v1 default). */
  readonly kind: string;
  readonly language?: string;
  readonly lines: number;
  readonly cyclomatic?: number;
  /** Cognitive complexity (§R2 tooling). */
  readonly cognitive?: number;
  /** 0–100, VS-rescaled. */
  readonly maintainability?: number;
  /** added + deleted across the window. */
  readonly churnAbsolute: number;
  /** churnAbsolute / lines — the preferred defect predictor (contract §3/§4). */
  readonly churnRelative: number;
  /** #commits touching this entity in the window. */
  readonly changeFrequency: number;
  /** changeFrequency × complexity, 0–1 normalized — the hotspot intensity (contract §3). */
  readonly hotspotScore: number;
  /** Days since the last substantive change. */
  readonly ageDays: number;
  /** Ingested from a coverage profile when present (Go `*float64`, omitempty). */
  readonly coverage?: number;
  readonly primaryAuthor?: string;
  readonly authorCount?: number;
}

/** A pairwise logical-coupling edge — feeds the dependency-matrix primitive (contract §3). */
export interface Coupling {
  readonly entityA: string;
  readonly entityB: string;
  /** 0–100 = sharedRevisions / averageRevisions. */
  readonly degree: number;
  readonly sharedRevisions: number;
  /** Gate ≥10 to suppress accidental co-change (contract §3). */
  readonly averageRevisions: number;
}

/** Author → code attribution + bus-factor inputs — feeds the ownership-map primitive (contract §3). */
export interface Ownership {
  readonly path: string;
  /** author → fractional line ownership (0–1). */
  readonly authors: Readonly<Record<string, number>>;
  /** #authors covering >50% (default; contract OD-CI-3). */
  readonly busFactor: number;
}

/** DORA keys — bands + derivation land from research round 2; mostly `omitempty` (contract §3/§4). */
export interface DoraKeys {
  readonly deploymentFrequency?: string;
  readonly leadTimeHours?: number;
  readonly changeFailureRate?: number;
  readonly recoveryHours?: number;
  /** Elite | High | Medium | Low. */
  readonly performer?: string;
}

/** Repo-level scalars + the A–E ratings — feeds the rating-badge primitive (contract §3). */
export interface Summary {
  readonly lines: number;
  readonly entityCount: number;
  /** SQALE; 0–1. */
  readonly technicalDebtRatio: number;
  /** `"A"`…`"E"` (≤5 / <10 / <20 / <50 / ≥50 %). */
  readonly maintainabilityRating: string;
  /** Repo-level coverage (Go `*float64`, omitempty). */
  readonly coverage?: number;
  /** Repo-level minimum critical set. */
  readonly busFactor: number;
  /** §R2 — present once a deploy/incident feed is wired (Go `*DoraKeys`, omitempty). */
  readonly dora?: DoraKeys;
  /** dimension → `"A".."E"` (omitempty). */
  readonly ratings?: Readonly<Record<string, string>>;
}

/** One sample of a time series — `value` taken at the commit it was computed at (contract §3). */
export interface TrendPoint {
  /** The commit hash this sample was taken at. */
  readonly commit: string;
  /** RFC3339. */
  readonly at: string;
  readonly value: number;
}

/** A time series for the monitoring lens — feeds the trend primitive (contract §3). */
export interface TrendSeries {
  /** `"churn"` | `"debtRatio"` | `"coverage"` | a dora key. */
  readonly metric: string;
  readonly points: readonly TrendPoint[];
}

/**
 * The producer's declaration of WHICH widget primitive renders WHICH slice of the report at WHICH
 * SDLC attention point (contract §5). The frontend iterates `Views` and, for each, instantiates the
 * named primitive bound to the encoded fields — so adding a view is DATA, not code.
 */
export interface View {
  readonly id: string;
  readonly title: string;
  /** One of the 8 widget primitives (contract §5) — e.g. `"hotspot-map"`. */
  readonly primitive: string;
  /** `"pre-commit"` | `"pull-request"` | `"release-gate"` | `"monitoring"`. */
  readonly attentionPoint: string;
  /**
   * channel → report field. e.g. the hotspot-map default:
   * `{ x: "churnRelative", y: "cyclomatic", size: "lines", color: "hotspotScore", label: "path" }`.
   */
  readonly encoding: Readonly<Record<string, string>>;
  /** Which Report collection feeds it: `"entities"|"couplings"|"ownership"|"trends"|"summary"`. */
  readonly source: string;
}

/**
 * The one self-describing envelope (contract §3). Every datum is stamped with the commit it was
 * computed at, so a `Report` is replayable and diff-able across history.
 */
export interface Report {
  /** semver of THIS contract. */
  readonly schemaVersion: string;
  readonly repository: RepositoryRef;
  /** The commit range analyzed. */
  readonly window: Window;
  /** Per-file / per-package nodes. */
  readonly entities: readonly Entity[];
  /** Pairwise logical-coupling edges. */
  readonly couplings: readonly Coupling[];
  /** author→code, bus-factor inputs. */
  readonly ownership: readonly Ownership[];
  /** Repo-level scalars + A–E ratings. */
  readonly summary: Summary;
  /** Time series for the monitoring lens. */
  readonly trends: readonly TrendSeries[];
  /** The dynamic render-plan (contract §5). */
  readonly views: readonly View[];
}
