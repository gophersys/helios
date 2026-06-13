// Home-page data (the A0 project grid, doc 12 §2/§4). For each registered project
// it computes a card summary server-side: document count, a status breakdown (the
// founder's status-first dots, doc 12 §5), and the validation state (clean / has
// violations / coverage gaps). The validator runs through the cached client, so
// the three reads per project share work with the workspace pages.

import { projectRegistry } from '$lib/server/repository';
import {
  projectDocuments,
  validateDocuments,
  ValidatorUnavailableError,
} from '$lib/server/validatorClient';
import { STATUS_ORDER } from '$lib/documentModel';
import type { PageServerLoad } from './$types';

// A status → count map over a project's documents, keyed by the lifecycle order.
function countByStatus(statuses: string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const status of STATUS_ORDER) counts[status] = 0;
  for (const status of statuses) {
    counts[status] = (counts[status] ?? 0) + 1;
  }
  return counts;
}

export interface ProjectCard {
  readonly slug: string;
  readonly title: string;
  readonly documentCount: number;
  readonly statusCounts: Record<string, number>;
  readonly violations: number;
  readonly coverageGaps: number;
  readonly ok: boolean;
  // Set when this project's corpus could not be read at all (validator missing or
  // the directory absent); the card renders an instructive state instead of stats.
  readonly errorMessage: string | null;
}

export const load: PageServerLoad = async () => {
  const cards: ProjectCard[] = [];
  for (const project of projectRegistry()) {
    try {
      const [documents, report] = await Promise.all([
        projectDocuments(project.directory),
        validateDocuments(project.directory),
      ]);
      cards.push({
        slug: project.slug,
        title: project.title,
        documentCount: documents.length,
        statusCounts: countByStatus(documents.map((document) => document.meta.status)),
        violations: report.violations.length,
        coverageGaps: report.coverage.length,
        ok: report.ok,
        errorMessage: null,
      });
    } catch (caught) {
      const message =
        caught instanceof ValidatorUnavailableError
          ? caught.message
          : caught instanceof Error
            ? caught.message
            : 'the project corpus could not be read';
      cards.push({
        slug: project.slug,
        title: project.title,
        documentCount: 0,
        statusCounts: countByStatus([]),
        violations: 0,
        coverageGaps: 0,
        ok: false,
        errorMessage: message,
      });
    }
  }
  return { cards };
};
