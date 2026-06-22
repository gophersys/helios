// setupWizard — the pure model behind the SETUP WIZARD, the in-workspace step a project runs while
// its lifecycle status is `wizard`. The wizard IS the supervisor's FSM made visible: the supervisor
// session (the live build agent the create-saga launched) drives a short product-scoping interview,
// and the wizard renders that interview from the artifacts the supervisor COMMITS to the project's
// workspace worktree (init/product/questionnaire/* → the questions, init/product/answers/* → the
// recorded answers) plus the live session SSE. This module is the deterministic, side-effect-free
// read of those inputs into the wizard's renderable state, so the SetupWizard component stays a pure
// view and the logic is unit-testable on its own (one concept, one home).
//
// The four wizard steps mirror the supervisor's interview phases:
//   1. STACKS        — choose the platform targets (web/desktop/mobile/…); a GROWABLE data list.
//   2. DESCRIBE      — a 100-word "describe the simplest product" brief, fed to the supervisor.
//   3. QUESTIONNAIRE — the supervisor's committed questions arrive under init/product/questionnaire/*.
//   4. QA            — each answer is posted to the supervisor + committed under init/product/answers/*;
//                      the advance guard (no open questions) gates leaving the step.

/** One platform stack the wizard offers in step 1. `id` is the stable token sent to the supervisor;
 *  `label`/`hint` are the human copy; `glyph` is a decorative marker. The list is GROWABLE — a new
 *  target is one entry here (and the supervisor learns the token), nothing else changes. */
export interface WizardStack {
  id: string;
  label: string;
  hint: string;
  glyph: string;
}

/** The growable stack palette, in display order. The supervisor receives the selected ids verbatim
 *  (so adding a target is purely additive: append here, teach the supervisor the token). */
export const WIZARD_STACKS: readonly WizardStack[] = [
  { id: 'web', label: 'Web', hint: 'A responsive web app', glyph: '◻' },
  { id: 'desktop', label: 'Desktop', hint: 'A native desktop build', glyph: '▢' },
  { id: 'mobile', label: 'Mobile', hint: 'iOS + Android', glyph: '▭' },
];

/** The hard limit on the DESCRIBE brief — the wizard prompts for "the simplest product" in one short
 *  breath, so the brief is capped at 100 words (the supervisor scopes the rest through the
 *  questionnaire). Exported so the view and the validator share ONE source. */
export const DESCRIBE_WORD_LIMIT = 100;

/** countWords returns the whitespace-delimited word count of text (an empty/whitespace string is 0).
 *  The DESCRIBE step caps the brief at DESCRIBE_WORD_LIMIT using this — one counting rule, one home. */
export function countWords(text: string): number {
  const trimmed = text.trim();
  if (trimmed === '') return 0;
  return trimmed.split(/\s+/).length;
}

/** describeWithinLimit reports whether a brief is a legal DESCRIBE submission: non-empty and at or
 *  under the word limit. The view derives the submit affordance from this (never a hand-guessed
 *  condition), so an over-limit or blank brief can never be sent to the supervisor. */
export function describeWithinLimit(text: string): boolean {
  const words = countWords(text);
  return words > 0 && words <= DESCRIBE_WORD_LIMIT;
}

/** The four ordered wizard steps. The wizard ADVANCES through them; the step is the wizard's own FSM
 *  cursor, distinct from (and gated by) the supervisor's committed artifacts. */
export type WizardStep = 'stacks' | 'describe' | 'questionnaire' | 'qa';

/** The ordered step list (for the progress dots + the next/back derivation). */
export const WIZARD_STEPS: readonly WizardStep[] = ['stacks', 'describe', 'questionnaire', 'qa'];

/** One question the supervisor committed under init/product/questionnaire/*. Each file is ONE
 *  question: `id` is the slug derived from the filename (the answer is committed under the same slug
 *  in init/product/answers/), `prompt` is the file's body (the question text). `path` is the source
 *  path for the live "committed assets" render. */
export interface WizardQuestion {
  id: string;
  prompt: string;
  path: string;
}

/** One answer the wizard recorded (committed under init/product/answers/<id>.md). `id` correlates to
 *  the question slug; `text` is the recorded answer body. */
export interface WizardAnswer {
  id: string;
  text: string;
}

/** A file in the project's workspace worktree as the wizard source surfaces it: a slash-separated
 *  path RELATIVE to the worktree root and its UTF-8 text content. The wizard only ever reads the
 *  init/product/* tree, which is small committed text — never a binary or a build artifact. */
export interface WizardFile {
  path: string;
  text: string;
}

/** The committed init/product/* sub-trees the wizard reads. The supervisor commits the questionnaire
 *  under the first and the wizard commits answers under the second — the one home for these paths. */
export const QUESTIONNAIRE_PREFIX = 'init/product/questionnaire/';
export const ANSWERS_PREFIX = 'init/product/answers/';

/** slugFromPath derives a stable question/answer id from a committed file path: the basename without
 *  its extension (init/product/questionnaire/01-audience.md → "01-audience"). The answer for a
 *  question is committed under the SAME slug in the answers tree, so the slug is the join key. */
export function slugFromPath(path: string): string {
  const base = path.slice(path.lastIndexOf('/') + 1);
  const dot = base.lastIndexOf('.');
  return dot > 0 ? base.slice(0, dot) : base;
}

/** parseQuestions reads the committed questionnaire files into the ordered question list. It selects
 *  exactly the files under QUESTIONNAIRE_PREFIX, derives each id from the filename, takes the file
 *  body as the prompt, and SORTS by path so a numeric filename prefix (01-, 02-) gives a stable
 *  presentation order. A file whose body is blank after trimming is skipped (a placeholder commit is
 *  not yet a real question). Pure — the view recomputes it whenever the worktree listing changes. */
export function parseQuestions(files: readonly WizardFile[]): WizardQuestion[] {
  const questions: WizardQuestion[] = [];
  for (const file of files) {
    if (!file.path.startsWith(QUESTIONNAIRE_PREFIX)) continue;
    const prompt = file.text.trim();
    if (prompt === '') continue;
    questions.push({ id: slugFromPath(file.path), prompt, path: file.path });
  }
  questions.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  return questions;
}

/** parseAnswers reads the committed answer files into a slug→answer map. It selects the files under
 *  ANSWERS_PREFIX, joins each to its question by the shared slug, and takes a non-blank trimmed body
 *  as the recorded answer (a blank commit is "not answered yet"). Pure. */
export function parseAnswers(files: readonly WizardFile[]): Map<string, WizardAnswer> {
  const answers = new Map<string, WizardAnswer>();
  for (const file of files) {
    if (!file.path.startsWith(ANSWERS_PREFIX)) continue;
    const text = file.text.trim();
    if (text === '') continue;
    const id = slugFromPath(file.path);
    answers.set(id, { id, text });
  }
  return answers;
}

/** A question joined to its recorded answer (when any) for the Q&A render. `answer` is null until the
 *  matching answers/<id> file is committed; `open` is true while it is unanswered (the advance guard). */
export interface WizardQuestionState {
  question: WizardQuestion;
  answer: WizardAnswer | null;
  open: boolean;
}

/** joinQuestions folds the question list + the answer map into the per-question render state, in the
 *  questionnaire's order. This is the ONE place the question↔answer correlation lives. */
export function joinQuestions(
  questions: readonly WizardQuestion[],
  answers: ReadonlyMap<string, WizardAnswer>,
): WizardQuestionState[] {
  return questions.map((question) => {
    const answer = answers.get(question.id) ?? null;
    return { question, answer, open: answer === null };
  });
}

/** hasOpenQuestions is the QA-step ADVANCE GUARD: true while ANY committed question is unanswered. The
 *  wizard cannot leave the Q&A step (and the supervisor cannot proceed to build) while a question is
 *  open. A questionnaire with no questions is NOT open (nothing to gate) — the guard is about
 *  unanswered questions, not about the questionnaire's existence (that is questionnaireReady). */
export function hasOpenQuestions(states: readonly WizardQuestionState[]): boolean {
  return states.some((state) => state.open);
}

/** questionnaireReady reports whether the supervisor has committed at least one question yet — the
 *  gate the QUESTIONNAIRE step waits on before it can advance to Q&A. Until the supervisor commits the
 *  questionnaire the step shows a "waiting on the supervisor" state and the advance is disabled. */
export function questionnaireReady(questions: readonly WizardQuestion[]): boolean {
  return questions.length > 0;
}

/** answersPathFor returns the committed-answer path for a question id (the wizard writes the answer
 *  here via the supervisor). The one home for the answers path shape. */
export function answersPathFor(questionId: string): string {
  return `${ANSWERS_PREFIX}${questionId}.md`;
}
