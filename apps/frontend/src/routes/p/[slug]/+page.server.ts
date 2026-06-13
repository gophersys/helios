// The workspace data for a single project (doc 12 §5 document consumption). It
// pulls the three projections (documents, links, validation) and pre-computes the
// structures the page renders over so the client stays presentational:
//   · documents sorted into tiers (doc 11 §2) for the sidebar;
//   · a backlinks index — the derived reverse edges (doc 11 §3 "realized by …"),
//     computed from the upstream-only link graph;
//   · a per-document validation slice (violations + T6 coverage gaps touching it).
// A missing validator surfaces as a 503 with an instructive message (the route
// helper maps it); the page renders that as a setup banner.

import { error } from '@sveltejs/kit';

import { requireProject } from '../../api/projects/[slug]/resolveProject';
import {
  projectDocuments,
  projectLinks,
  validateDocuments,
  ValidatorUnavailableError,
  type Diagnostic,
  type LinkEdge,
  type ProjectedDocument,
} from '$lib/server/validatorClient';
import { tierOf, typeRank, type Tier } from '$lib/documentModel';

// One backlink: an upstream item learns which downstream items realize/verify it,
// and through which typed edge — the "realized by …" relation (doc 11 §3, doc 12
// §5 typed backlinks, never an undifferentiated hairball).
export interface Backlink {
  readonly from: string;
  readonly type: string;
}

export interface WorkspaceData {
  readonly slug: string;
  readonly title: string;
  readonly documents: ProjectedDocument[];
  readonly links: LinkEdge[];
  // documentId-or-itemId → the edges pointing at it (its reverse edges).
  readonly backlinks: Record<string, Backlink[]>;
  readonly validation: {
    readonly violations: Diagnostic[];
    readonly coverage: Diagnostic[];
    readonly ok: boolean;
    readonly violationsExit: boolean;
  };
  // Validator could not run at all; the page shows a setup banner instead.
  readonly validatorError: string | null;
}

// Group + order documents into the three tiers for the sidebar. Within a tier,
// order by the type's registry position then by id, so the listing is stable.
function groupByTier(
  documents: ProjectedDocument[],
): Array<{ key: Tier['key']; documents: ProjectedDocument[] }> {
  const order: Tier['key'][] = ['product', 'architecture', 'implementation'];
  return order.map((key) => ({
    key,
    documents: documents
      .filter((document) => tierOf(document.meta.type) === key)
      .sort((left, right) => {
        const byType = typeRank(left.meta.type) - typeRank(right.meta.type);
        if (byType !== 0) return byType;
        return left.meta.id.localeCompare(right.meta.id);
      }),
  }));
}

// Build the backlinks index from the upstream-only edge list: every edge `from →
// to` contributes a reverse entry at `to` recording who points at it and how.
function buildBacklinks(links: LinkEdge[]): Record<string, Backlink[]> {
  const index: Record<string, Backlink[]> = {};
  for (const edge of links) {
    (index[edge.to] ??= []).push({ from: edge.from, type: edge.type });
  }
  for (const target of Object.keys(index)) {
    index[target].sort((left, right) => left.from.localeCompare(right.from));
  }
  return index;
}

export const load = async ({ params }: { params: { slug: string } }) => {
  const project = requireProject(params.slug);

  let documents: ProjectedDocument[] = [];
  let links: LinkEdge[] = [];
  let validation: WorkspaceData['validation'] = {
    violations: [],
    coverage: [],
    ok: true,
    violationsExit: false,
  };
  let validatorError: string | null = null;

  try {
    [documents, links, validation] = await Promise.all([
      projectDocuments(project.directory),
      projectLinks(project.directory),
      validateDocuments(project.directory),
    ]);
  } catch (caught) {
    if (caught instanceof ValidatorUnavailableError) {
      validatorError = caught.message;
    } else {
      // A genuine failure (bad corpus, IO) is a 500 — the operator should see it.
      throw error(500, caught instanceof Error ? caught.message : 'failed to load the project');
    }
  }

  const data: WorkspaceData = {
    slug: project.slug,
    title: project.title,
    documents,
    links,
    backlinks: buildBacklinks(links),
    validation,
    validatorError,
  };

  return {
    workspace: data,
    tiers: groupByTier(documents),
  };
};
