/**
 * Unit tests for CI service — stage computation, query-string building,
 * filename sanitization, and field filtering logic.
 *
 * All network calls are mocked; the tests exercise the pure logic that
 * lives between the apiFetch call and the returned value.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { BuildRunDetail, BuildRunBuildSummary } from '$lib/types/ci';

// ── Mock $lib/api before importing the service ─────────────────────────────

const mockApiFetch = vi.fn();
const mockApiPost = vi.fn();
const mockApiDownload = vi.fn();

vi.mock('$lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  apiDownload: (...args: unknown[]) => mockApiDownload(...args),
  apiUpload: vi.fn(),
  api: {
    get: vi.fn(),
    post: (...args: unknown[]) => mockApiPost(...args),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

// Import after mocking
import {
  fetchBuildRun,
  fetchBuildRuns,
  downloadBuildRunArtifacts,
  downloadSingleArtifact,
  createManualBuild,
} from './ci';

// ── Helpers ────────────────────────────────────────────────────────────────

function makePipelineBase(overrides: Partial<BuildRunDetail> = {}): BuildRunDetail {
  return {
    id: 'pipe-1',
    name: 'Test BuildRunDetail',
    product: 'alpha',
    board: 'alpha_b0',
    branch: 'main',
    commitSha: 'abc123',
    status: 'BUILDING',
    triggerType: 'webhook',
    expectedBuilds: 1,
    completedBuilds: 0,
    validationRunId: null,
    autoValidate: false,
    startedAt: '2024-01-01T00:00:00Z',
    finishedAt: null,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    builds: [],
    ...overrides,
  };
}

function makeBuild(status: BuildRunBuildSummary['status'], overrides: Partial<BuildRunBuildSummary> = {}): BuildRunBuildSummary {
  return {
    id: `build-${Math.random()}`,
    product: 'alpha',
    status,
    variant: 'release',
    buildNum: 1,
    versionString: '1.0.0',
    durationSeconds: 60,
    artifactCount: 3,
    ...overrides,
  };
}

// ── fetchBuildRun — stage computation ─────────────────────────────────────

describe('fetchBuildRun stage computation', () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  describe('BUILD stage status', () => {
    it('is PENDING when there are no builds', async () => {
      const pipeline = makePipelineBase({ builds: [] });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('PENDING');
    });

    it('is RUNNING when any build is BUILDING', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('BUILDING')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('RUNNING');
    });

    it('is RUNNING when builds exist but none are complete (QUEUED)', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('QUEUED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('RUNNING');
    });

    it('is FAILED when any build is FAILED (even if others succeeded)', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('SUCCESS'), makeBuild('FAILED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('FAILED');
    });

    it('is SUCCESS when all builds are SUCCESS', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('SUCCESS'), makeBuild('SUCCESS')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('SUCCESS');
    });

    it('is SUCCESS when all builds are SUCCESS or CANCELLED', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('SUCCESS'), makeBuild('CANCELLED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('SUCCESS');
    });

    it('RUNNING takes priority over FAILED in status derivation', async () => {
      // anyBuildRunning is checked first
      const pipeline = makePipelineBase({
        builds: [makeBuild('BUILDING'), makeBuild('FAILED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.status).toBe('RUNNING');
    });
  });

  describe('BUILD stage detail', () => {
    it('shows "N/M builds passed" detail when builds exist', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('SUCCESS'), makeBuild('FAILED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.detail).toBe('1/2 builds passed');
    });

    it('has null detail when no builds', async () => {
      const pipeline = makePipelineBase({ builds: [] });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.detail).toBeNull();
    });

    it('shows finishedAt only when all builds complete', async () => {
      const finishedAt = '2024-01-01T01:00:00Z';
      const pipeline = makePipelineBase({
        builds: [makeBuild('SUCCESS')],
        finishedAt,
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.finishedAt).toBe(finishedAt);
    });

    it('has null finishedAt when builds not complete', async () => {
      const pipeline = makePipelineBase({
        builds: [makeBuild('BUILDING')],
        finishedAt: '2024-01-01T01:00:00Z',
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const buildStage = result.stages!.find((s: any) => s.stage === 'BUILD')!;
      expect(buildStage.finishedAt).toBeNull();
    });
  });

  describe('FLASH stage', () => {
    it('is not present when no validationRunId and status is not VALIDATING', async () => {
      const pipeline = makePipelineBase({ validationRunId: null, status: 'BUILDING' });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH');
      expect(flashStage).toBeUndefined();
    });

    it('is present when pipeline has a validationRunId', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        builds: [makeBuild('SUCCESS')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH');
      expect(flashStage).toBeDefined();
    });

    it('is present when pipeline status is VALIDATING', async () => {
      const pipeline = makePipelineBase({ status: 'VALIDATING', validationRunId: null });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH');
      expect(flashStage).toBeDefined();
    });

    it('is SUCCESS when build stage succeeded', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        builds: [makeBuild('SUCCESS')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH')!;
      expect(flashStage.status).toBe('SUCCESS');
    });

    it('is SKIPPED when build stage failed', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        builds: [makeBuild('FAILED')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH')!;
      expect(flashStage.status).toBe('SKIPPED');
    });

    it('is PENDING when build stage is still running', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        builds: [makeBuild('BUILDING')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const flashStage = result.stages!.find((s: any) => s.stage === 'FLASH')!;
      expect(flashStage.status).toBe('PENDING');
    });
  });

  describe('VALIDATE stage', () => {
    it('is not present when no validationRunId', async () => {
      const pipeline = makePipelineBase({ validationRunId: null });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const validateStage = result.stages!.find((s: any) => s.stage === 'VALIDATE');
      expect(validateStage).toBeUndefined();
    });

    it('is SUCCESS when pipeline status is COMPLETED', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        status: 'COMPLETED',
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const validateStage = result.stages!.find((s: any) => s.stage === 'VALIDATE')!;
      expect(validateStage.status).toBe('SUCCESS');
    });

    it('is FAILED when pipeline status is FAILED', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        status: 'FAILED',
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const validateStage = result.stages!.find((s: any) => s.stage === 'VALIDATE')!;
      expect(validateStage.status).toBe('FAILED');
    });

    it('is PENDING when pipeline status is VALIDATING', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        status: 'VALIDATING',
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const validateStage = result.stages!.find((s: any) => s.stage === 'VALIDATE')!;
      expect(validateStage.status).toBe('PENDING');
    });
  });

  describe('stage ordering', () => {
    it('always emits BUILD as first stage', async () => {
      const pipeline = makePipelineBase({ builds: [makeBuild('SUCCESS')] });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      expect(result.stages![0].stage).toBe('BUILD');
    });

    it('emits BUILD → FLASH → VALIDATE order when all present', async () => {
      const pipeline = makePipelineBase({
        validationRunId: 'run-1',
        status: 'VALIDATING',
        builds: [makeBuild('SUCCESS')],
      });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      const stageNames = result.stages!.map(s => s.stage);
      expect(stageNames).toEqual(['BUILD', 'FLASH', 'VALIDATE']);
    });
  });

  describe('buildJob computed field', () => {
    it('sets buildJob to null when no builds', async () => {
      const pipeline = makePipelineBase({ builds: [] });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      expect(result.buildJob).toBeNull();
    });

    it('populates buildJob from first build', async () => {
      const build = makeBuild('SUCCESS', { id: 'b-1', product: 'alpha', variant: 'release' });
      const pipeline = makePipelineBase({ builds: [build], board: 'alpha_b0', branch: 'main' });
      mockApiFetch.mockResolvedValue({ data: pipeline, errors: [] });

      const result = await fetchBuildRun('pipe-1');
      expect(result.buildJob).not.toBeNull();
      expect(result.buildJob!.id).toBe('b-1');
      expect(result.buildJob!.board).toBe('alpha_b0');
      expect(result.buildJob!.branch).toBe('main');
      expect(result.buildJob!.artifacts).toEqual([]);
    });
  });
});

// ── fetchBuildRuns — query string building ─────────────────────────────────

describe('fetchBuildRuns query string building', () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
    mockApiFetch.mockResolvedValue({
      data: [],
      errors: [],
      page: 1,
      totalPages: 1,
      totalResults: 0,
      resultsPerPage: 25,
    });
  });

  it('calls with no query string when no params', async () => {
    await fetchBuildRuns();
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).toBe('/v2/builds/runs?');
  });

  it('includes page param', async () => {
    await fetchBuildRuns({ page: 3 });
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).toContain('page=3');
  });

  it('includes status param', async () => {
    await fetchBuildRuns({ status: 'FAILED' });
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).toContain('status=FAILED');
  });

  it('includes branch param', async () => {
    await fetchBuildRuns({ branch: 'feature/foo' });
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).toContain('branch=feature%2Ffoo');
  });

  it('includes matrixMode param', async () => {
    await fetchBuildRuns({ matrixMode: 'fuota' });
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).toContain('matrixMode=fuota');
  });

  it('omits undefined params', async () => {
    await fetchBuildRuns({ page: undefined, status: 'SUCCESS' });
    const url: string = mockApiFetch.mock.calls[0][0];
    expect(url).not.toContain('page=');
    expect(url).toContain('status=SUCCESS');
  });

  it('returns pagination defaults when API response is missing fields', async () => {
    mockApiFetch.mockResolvedValue({ data: [], errors: [] }); // no page fields
    const result = await fetchBuildRuns();
    expect(result.pagination).toEqual({ page: 1, limit: 25, total: 0, pages: 0 });
  });
});

// ── downloadBuildRunArtifacts — branch sanitization ───────────────────────

describe('downloadBuildRunArtifacts branch sanitization', () => {
  beforeEach(() => {
    mockApiDownload.mockReset().mockResolvedValue(undefined);
  });

  it('passes clean branch through unchanged', async () => {
    await downloadBuildRunArtifacts('pipe-1', 'alpha', 'main');
    expect(mockApiDownload).toHaveBeenCalledWith(
      '/v2/builds/runs/pipe-1/artifacts/download',
      'alpha_main_all.zip'
    );
  });

  it('replaces forward slashes with underscores', async () => {
    await downloadBuildRunArtifacts('pipe-1', 'alpha', 'feature/my-branch');
    const [, filename] = mockApiDownload.mock.calls[0];
    expect(filename).toBe('alpha_feature_my-branch_all.zip');
  });

  it('replaces dots with underscores', async () => {
    await downloadBuildRunArtifacts('pipe-1', 'alpha', 'release.1.0');
    const [, filename] = mockApiDownload.mock.calls[0];
    expect(filename).toBe('alpha_release_1_0_all.zip');
  });

  it('replaces spaces with underscores', async () => {
    await downloadBuildRunArtifacts('pipe-1', 'alpha', 'my branch');
    const [, filename] = mockApiDownload.mock.calls[0];
    expect(filename).toBe('alpha_my_branch_all.zip');
  });

  it('preserves hyphens and underscores', async () => {
    await downloadBuildRunArtifacts('pipe-1', 'alpha', 'my-branch_v2');
    const [, filename] = mockApiDownload.mock.calls[0];
    expect(filename).toBe('alpha_my-branch_v2_all.zip');
  });

  it('uses correct pipeline endpoint', async () => {
    await downloadBuildRunArtifacts('pipe-42', 'alpha', 'main');
    const [url] = mockApiDownload.mock.calls[0];
    expect(url).toBe('/v2/builds/runs/pipe-42/artifacts/download');
  });
});

// ── downloadBuildRunArtifacts — filename construction ─────────────────────────

describe('downloadBuildRunArtifacts', () => {
  beforeEach(() => {
    mockApiDownload.mockReset().mockResolvedValue(undefined);
  });

  it('constructs filename from product and branch', async () => {
    await downloadBuildRunArtifacts('build-1', 'alpha', 'release');
    expect(mockApiDownload).toHaveBeenCalledWith(
      '/v2/builds/runs/build-1/artifacts/download',
      'alpha_release_all.zip'
    );
  });
});

// ── downloadSingleArtifact — URL encoding ─────────────────────────────────

describe('downloadSingleArtifact', () => {
  beforeEach(() => {
    mockApiDownload.mockReset().mockResolvedValue(undefined);
  });

  it('URL-encodes the artifact name in the path', async () => {
    await downloadSingleArtifact('build-1', 'my artifact.hex');
    const [url] = mockApiDownload.mock.calls[0];
    expect(url).toBe('/v2/builds/build-1/artifacts/my%20artifact.hex');
  });

  it('uses the raw artifact name as the download filename', async () => {
    await downloadSingleArtifact('build-1', 'firmware.hex');
    const [, filename] = mockApiDownload.mock.calls[0];
    expect(filename).toBe('firmware.hex');
  });
});

// ── createManualBuild — field filtering ───────────────────────────────────

describe('createManualBuild field filtering', () => {
  beforeEach(() => {
    mockApiPost.mockReset();
    mockApiPost.mockResolvedValue({ data: { id: 'build-new' }, errors: [] });
  });

  it('always sets triggerType to manual and initialStatus to SUCCESS', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.triggerType).toBe('manual');
    expect(body.initialStatus).toBe('SUCCESS');
  });

  it('omits versionString when empty string provided', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main', versionString: '',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.versionString).toBeUndefined();
  });

  it('includes versionString when non-empty', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main', versionString: '1.2.3',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.versionString).toBe('1.2.3');
  });

  it('omits notes when empty string provided', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main', notes: '',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.notes).toBeUndefined();
  });

  it('omits productId when empty string provided', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main', productId: '',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.productId).toBeUndefined();
  });

  it('includes productId when provided', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main', productId: 'prod-123',
    });
    const [, body] = mockApiPost.mock.calls[0];
    expect(body.productId).toBe('prod-123');
  });

  it('posts to /v2/builds', async () => {
    await createManualBuild({
      product: 'alpha', board: 'alpha_b0', target: 'nrf52840',
      variant: 'release', branch: 'main',
    });
    const [url] = mockApiPost.mock.calls[0];
    expect(url).toBe('/v2/builds');
  });
});
