// Mock data for validation flow demo

import type { FlowNodeData, FlowEdgeData, ValidationStep } from './types';
import type { BuildJob, BuildJobArtifact } from '$lib/types/ci';

// Mock builds for the BUILD node
export const MOCK_BUILDS: BuildJob[] = [
  {
    id: 'build-mfg-base',
    product: 'alpha_mfg_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'mfg',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.5.0',
    matrixLabel: 'MFG_BASE',
    matrixIndex: 0,
    buildNum: 1,
    durationSeconds: 360,
    startedAt: '2026-03-10T18:00:00Z',
    finishedAt: '2026-03-10T18:06:00Z',
    createdAt: '2026-03-10T18:00:00Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-mfg-bump',
    product: 'alpha_mfg_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'mfg',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.5.1',
    matrixLabel: 'MFG_BUMP',
    matrixIndex: 1,
    buildNum: 2,
    durationSeconds: 340,
    startedAt: '2026-03-10T18:06:00Z',
    finishedAt: '2026-03-10T18:11:40Z',
    createdAt: '2026-03-10T18:06:00Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-debug-a',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'debug',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.0',
    matrixLabel: 'FUT_DEBUG_A',
    matrixIndex: 2,
    buildNum: 3,
    durationSeconds: 380,
    startedAt: '2026-03-10T18:11:40Z',
    finishedAt: '2026-03-10T18:18:00Z',
    createdAt: '2026-03-10T18:11:40Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-debug-b',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'debug',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.1',
    matrixLabel: 'FUT_DEBUG_B',
    matrixIndex: 3,
    buildNum: 4,
    durationSeconds: 360,
    startedAt: '2026-03-10T18:18:00Z',
    finishedAt: '2026-03-10T18:24:00Z',
    createdAt: '2026-03-10T18:18:00Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-release-a',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'release',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.2',
    matrixLabel: 'FUT_RELEASE_A',
    matrixIndex: 4,
    buildNum: 5,
    durationSeconds: 350,
    startedAt: '2026-03-10T18:24:00Z',
    finishedAt: '2026-03-10T18:29:50Z',
    createdAt: '2026-03-10T18:24:00Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-release-b',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'release',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.3',
    matrixLabel: 'FUT_RELEASE_B',
    matrixIndex: 5,
    buildNum: 6,
    durationSeconds: 340,
    startedAt: '2026-03-10T18:29:50Z',
    finishedAt: '2026-03-10T18:35:30Z',
    createdAt: '2026-03-10T18:29:50Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-baseline',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'release',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.0',
    matrixLabel: 'MAIN_BASELINE',
    matrixIndex: 6,
    buildNum: 7,
    durationSeconds: 360,
    startedAt: '2026-03-10T18:35:30Z',
    finishedAt: '2026-03-10T18:41:30Z',
    createdAt: '2026-03-10T18:35:30Z',
    buildLog: null,
    artifacts: [],
  },
  {
    id: 'build-merged',
    product: 'alpha_fw',
    board: 'alpha_b0',
    target: 'alpha_b0',
    variant: 'release',
    branch: 'concord-main',
    commitSha: 'abc1234567890',
    status: 'SUCCESS',
    versionString: '0.8.1',
    matrixLabel: 'MAIN_MERGED',
    matrixIndex: 7,
    buildNum: 8,
    durationSeconds: 350,
    startedAt: '2026-03-10T18:41:30Z',
    finishedAt: '2026-03-10T18:47:20Z',
    createdAt: '2026-03-10T18:41:30Z',
    buildLog: null,
    artifacts: [],
  },
];

export const MOCK_BUILD_ARTIFACTS: Record<string, BuildJobArtifact[]> = {
  'build-mfg-base': [
    { id: 'a1', buildJobId: 'build-mfg-base', name: 'app_nrf52840.hex', storageKey: 'builds/...', sizeBytes: 1276634, checksum: 'abc123', downloadUrl: '#', createdAt: '' },
    { id: 'a2', buildJobId: 'build-mfg-base', name: 'comms_nrf9151.hex', storageKey: 'builds/...', sizeBytes: 1228834, checksum: 'def456', downloadUrl: '#', createdAt: '' },
    { id: 'a3', buildJobId: 'build-mfg-base', name: '107.0.5.0.cfw', storageKey: 'builds/...', sizeBytes: 400098, checksum: 'ghi789', downloadUrl: '#', createdAt: '' },
    { id: 'a4', buildJobId: 'build-mfg-base', name: '100.0.5.0.cfw', storageKey: 'builds/...', sizeBytes: 422243, checksum: 'jkl012', downloadUrl: '#', createdAt: '' },
    { id: 'a5', buildJobId: 'build-mfg-base', name: 'build.json', storageKey: 'builds/...', sizeBytes: 206, checksum: 'mno345', downloadUrl: '#', createdAt: '' },
  ],
  'build-mfg-bump': [
    { id: 'b1', buildJobId: 'build-mfg-bump', name: 'app_nrf52840.hex', storageKey: 'builds/...', sizeBytes: 1276634, checksum: 'abc123', downloadUrl: '#', createdAt: '' },
    { id: 'b2', buildJobId: 'build-mfg-bump', name: 'comms_nrf9151.hex', storageKey: 'builds/...', sizeBytes: 1228834, checksum: 'def456', downloadUrl: '#', createdAt: '' },
    { id: 'b3', buildJobId: 'build-mfg-bump', name: '107.0.5.1.cfw', storageKey: 'builds/...', sizeBytes: 400098, checksum: 'ghi789', downloadUrl: '#', createdAt: '' },
    { id: 'b4', buildJobId: 'build-mfg-bump', name: '100.0.5.1.cfw', storageKey: 'builds/...', sizeBytes: 422243, checksum: 'jkl012', downloadUrl: '#', createdAt: '' },
  ],
};

export const MOCK_BUILD_LOGS: Record<string, string[]> = {
  'build-mfg-base': [
    '\x1b[36m[1/4] Application Processor (nRF52840)\x1b[0m',
    '-- west build: generating a build system',
    '   *****************************',
    '   *****************************',
    '-- Generating done',
    '   *************************************',
    '   *************************************',
    '  [1/373] Preparing syscall dependency handling',
    '  [2/373] Generating ../../zephyr/include/generated/zephyr_commit.h',
    '  ...',
    '  [370/373] Linking C executable zephyr/zephyr_pre0.elf',
    '  [371/373] Generating isr_tables.c',
    '  [372/373] Building C object zephyr/CMakeFiles/zephyr_final.dir/isr_tables.c.obj',
    '  [373/373] Linking C executable zephyr/zephyr.elf',
    '\x1b[32m  app_nrf52840.hex\x1b[0m',
    '',
    '\x1b[36m[2/4] Skipping VSM merge (Alpha has no VSM)\x1b[0m',
    '',
    '\x1b[36m[3/4] Communication Coprocessor (nrf9151)\x1b[0m',
    '-- west build: generating a build system',
    '  [1/453] Preparing syscall dependency handling',
    '  ...',
    '  [453/453] Linking C executable zephyr/zephyr.elf',
    '\x1b[32m  comms_nrf9151.hex\x1b[0m',
    '',
    '\x1b[36m[4/4] FIPS hash recalculation + final rebuild\x1b[0m',
    '-- Generating done',
    '  [1/10] Performing build step for \'comm_coproc_mfg\'',
    '  [10/10] Linking C executable zephyr/zephyr.elf',
    '',
    '\x1b[32mResolved version: 0.5.0\x1b[0m',
    '    \x1b[32mapp_nrf52840.hex\x1b[0m',
    '    \x1b[32mcomms_nrf9151.hex\x1b[0m',
    '    \x1b[32mdfu_application.zip\x1b[0m',
    '    \x1b[36mVersion: 0.5.0\x1b[0m',
    '    \x1b[36mVariant: no_debug\x1b[0m',
    '  \x1b[36mGenerating CFW files...\x1b[0m',
    '    \x1b[32mbuild.json\x1b[0m',
    '  \x1b[32mArtifacts -> /tmp/builds/output/0.5.0/no_debug/\x1b[0m',
    '',
    '\x1b[32mBuild completed successfully in 360s (6 min 0 sec)\x1b[0m',
  ],
};

export const MOCK_NODES: FlowNodeData[] = [
  { id: 'build', type: 'BUILD', label: 'Build', category: 'PRD', status: 'PASSED', summary: '8/8 builds' },
  { id: 'flash_mfg', type: 'FLASH', label: 'Flash MFG', category: 'PRD', status: 'PASSED', summary: 'v0.5.0' },
  { id: 'post_1', type: 'TEST', label: 'POST', category: 'PRD', status: 'PASSED', summary: '12/12' },
  { id: 'fuota_mfg', type: 'FUOTA', label: 'FUOTA MFG', category: 'PRD', status: 'RUNNING', progress: 67, summary: '342/512' },
  { id: 'post_2', type: 'TEST', label: 'POST Check', category: 'PRD', status: 'PENDING' },
  { id: 'fuota_debug', type: 'FUOTA', label: 'FUOTA Debug', category: 'PRD', status: 'PENDING' },
  { id: 'test_debug', type: 'TEST', label: 'Test Debug', category: 'PRD', status: 'PENDING' },
  { id: 'fuota_release', type: 'FUOTA', label: 'FUOTA Release', category: 'PRD', status: 'BLOCKED' },
  { id: 'test_release', type: 'TEST', label: 'Test Release', category: 'PRD', status: 'BLOCKED' },
];

export const MOCK_EDGES: FlowEdgeData[] = [
  { id: 'e1', source: 'build', target: 'flash_mfg' },
  { id: 'e2', source: 'flash_mfg', target: 'post_1' },
  { id: 'e3', source: 'post_1', target: 'fuota_mfg' },
  { id: 'e4', source: 'fuota_mfg', target: 'post_2' },
  { id: 'e5', source: 'post_2', target: 'fuota_debug' },
  { id: 'e6', source: 'fuota_debug', target: 'test_debug' },
  { id: 'e7', source: 'test_debug', target: 'fuota_release' },
  { id: 'e8', source: 'fuota_release', target: 'test_release' },
];

export const MOCK_STEPS: Record<string, ValidationStep> = {
  build: {
    id: 'step-build',
    runId: 'run-1',
    nodeId: 'build',
    nodeType: 'BUILD',
    nodeLabel: 'Build',
    category: 'PRD',
    status: 'PASSED',
    startedAt: '2026-03-10T18:00:00Z',
    finishedAt: '2026-03-10T18:45:00Z',
    durationMs: 2700000,
    summary: '8/8 builds passed',
    testsTotal: 8,
    testsPassed: 8,
    testsFailed: 0,
    testResults: [
      { name: 'MFG_BASE', status: 'PASSED', durationMs: 360000, message: 'v0.5.0' },
      { name: 'MFG_BUMP', status: 'PASSED', durationMs: 340000, message: 'v0.5.1' },
      { name: 'FUT_DEBUG_A', status: 'PASSED', durationMs: 380000, message: 'v0.8.0' },
      { name: 'FUT_DEBUG_B', status: 'PASSED', durationMs: 360000, message: 'v0.8.1' },
      { name: 'FUT_RELEASE_A', status: 'PASSED', durationMs: 350000, message: 'v0.8.2' },
      { name: 'FUT_RELEASE_B', status: 'PASSED', durationMs: 340000, message: 'v0.8.3' },
      { name: 'MAIN_BASELINE', status: 'PASSED', durationMs: 360000, message: 'v0.8.0' },
      { name: 'MAIN_MERGED', status: 'PASSED', durationMs: 350000, message: 'v0.8.1' },
    ],
    logs: `[18:00:01] Starting Stage 4 build matrix...
[18:00:02] Cloning repository...
[18:00:15] Repository cloned (concord-main @ abc1234)
[18:00:16] Starting build: MFG_BASE
[18:06:02] MFG_BASE complete: v0.5.0
[18:06:03] Starting build: MFG_BUMP
[18:11:45] MFG_BUMP complete: v0.5.1
...
[18:44:58] All 8 builds completed successfully
[18:45:00] Uploading artifacts to MinIO...
[18:45:02] Build stage complete`,
  },

  flash_mfg: {
    id: 'step-flash-mfg',
    runId: 'run-1',
    nodeId: 'flash_mfg',
    nodeType: 'FLASH',
    nodeLabel: 'Flash MFG',
    category: 'PRD',
    status: 'PASSED',
    startedAt: '2026-03-10T18:45:05Z',
    finishedAt: '2026-03-10T18:47:30Z',
    durationMs: 145000,
    summary: 'MFG v0.5.0 flashed',
    logs: `[18:45:05] Downloading MFG_BASE firmware from pipeline...
[18:45:08] Downloaded app_nrf52840.hex (1.2MB)
[18:45:10] Downloaded comms_nrf9151.hex (1.3MB)
[18:45:12] Uploading to MTIB server...
[18:45:15] Files uploaded
[18:45:16] Running nrfjprog --recover --snr 0964 -f NRF52 --speed 4000
[18:45:22] Recovery complete
[18:45:23] Flashing nRF52840 app...
[18:46:15] nRF52840 flash complete
[18:46:16] Flashing nRF9151 comms...
[18:47:08] nRF9151 flash complete
[18:47:10] Power cycling device...
[18:47:15] Device powered, waiting for boot...
[18:47:28] Boot detected, locking shell...
[18:47:30] Flash complete`,
    metrics: {
      ch0: { avg: 0.2, min: 0.0, max: 0.5 },
      ch1: { avg: 22.5, min: 15.0, max: 65.0 },
      samples: 14500,
      durationMs: 145000,
    },
  },

  post_1: {
    id: 'step-post-1',
    runId: 'run-1',
    nodeId: 'post_1',
    nodeType: 'TEST',
    nodeLabel: 'POST',
    category: 'PRD',
    status: 'PASSED',
    startedAt: '2026-03-10T18:47:35Z',
    finishedAt: '2026-03-10T18:52:10Z',
    durationMs: 275000,
    summary: '12/12 tests passed',
    testsTotal: 12,
    testsPassed: 12,
    testsFailed: 0,
    testsSkipped: 0,
    testResults: [
      { name: 'test_boot_current', status: 'PASSED', durationMs: 5200, message: 'Boot current 22.3mA (>5mA OK)' },
      { name: 'test_uart_output', status: 'PASSED', durationMs: 3100, message: 'UART output detected' },
      { name: 'test_shell_lock', status: 'PASSED', durationMs: 2800, message: 'Shell locked successfully' },
      { name: 'test_device_id_assigned', status: 'PASSED', durationMs: 1500, message: 'ID: 70B3D584C01E1FCC' },
      { name: 'test_keypair_generated', status: 'PASSED', durationMs: 45200, message: 'EC keypair generated' },
      { name: 'test_key_uploaded', status: 'PASSED', durationMs: 2100, message: 'Public key uploaded to CoreCloud' },
      { name: 'test_iccid_saved', status: 'PASSED', durationMs: 1800, message: 'ICCID: 89148000009808567681' },
      { name: 'test_personalization_complete', status: 'PASSED', durationMs: 1200, message: 'Device personalized' },
      { name: 'test_3v3_rail', status: 'PASSED', durationMs: 800, message: 'ADC ch7: 3.31V' },
      { name: 'test_vbat_rail', status: 'PASSED', durationMs: 800, message: 'ADC ch0: 4.52V' },
      { name: 'test_idle_current', status: 'PASSED', durationMs: 5300, message: 'Idle: 17.2mA avg' },
      { name: 'test_device_ready', status: 'PASSED', durationMs: 1100, message: 'Device ready for operation' },
    ],
    metrics: {
      ch0: { avg: 0.1, min: 0.0, max: 0.3 },
      ch1: { avg: 18.5, min: 12.0, max: 45.0 },
      samples: 27500,
      durationMs: 275000,
    },
    artifacts: [
      { name: 'power_profile.parquet', url: '#', type: 'power', sizeBytes: 125000 },
      { name: 'uart_app.log', url: '#', type: 'uart', sizeBytes: 45000 },
      { name: 'uart_comms.log', url: '#', type: 'uart', sizeBytes: 12000 },
    ],
  },

  fuota_mfg: {
    id: 'step-fuota-mfg',
    runId: 'run-1',
    nodeId: 'fuota_mfg',
    nodeType: 'FUOTA',
    nodeLabel: 'FUOTA MFG',
    category: 'PRD',
    status: 'RUNNING',
    startedAt: '2026-03-10T18:52:15Z',
    durationMs: 1800000, // 30 min so far
    summary: '67% (342/512)',
    fuotaPlanId: 31,
    fuotaTargets: '108.0.5.1-BMD, 109.0.5.1-BMD',
    fuotaPages: 342,
    fuotaPagesTotal: 512,
    fuotaPercent: 67,
    logs: `[18:52:15] Starting FUOTA: MFG_BASE → MFG_BUMP
[18:52:16] Uploading CFW files...
[18:52:18] Uploaded 108.0.5.1-BMD.cfw (400KB)
[18:52:20] Uploaded 109.0.5.1-BMD.cfw (422KB)
[18:52:22] Creating FUOTA plan...
[18:52:24] Plan created: id=31
[18:52:25] Assigning device 70B3D584C01E1FCC to plan...
[18:52:27] Device assigned, FUOTA enabled
[18:52:28] Power cycling device...
[18:52:35] Device booted, waiting for FUOTA progress...
[18:55:12] First page delivered
[18:58:45] Progress: 50 pages (10%)
[19:05:22] Progress: 150 pages (29%)
[19:12:18] Progress: 250 pages (49%)
[19:18:45] Progress: 342 pages (67%)
[19:22:15] Waiting for device uplink...`,
    metrics: {
      ch0: { avg: 0.0, min: 0.0, max: 0.1 },
      ch1: { avg: 25.3, min: 15.0, max: 85.0 },
      samples: 180000,
      durationMs: 1800000,
    },
  },

  post_2: {
    id: 'step-post-2',
    runId: 'run-1',
    nodeId: 'post_2',
    nodeType: 'TEST',
    nodeLabel: 'POST Check',
    category: 'PRD',
    status: 'PENDING',
  },

  fuota_debug: {
    id: 'step-fuota-debug',
    runId: 'run-1',
    nodeId: 'fuota_debug',
    nodeType: 'FUOTA',
    nodeLabel: 'FUOTA Debug',
    category: 'PRD',
    status: 'PENDING',
    fuotaTargets: '108.0.8.0-BMD, 109.0.8.0-BMD',
  },

  test_debug: {
    id: 'step-test-debug',
    runId: 'run-1',
    nodeId: 'test_debug',
    nodeType: 'TEST',
    nodeLabel: 'Test Debug',
    category: 'PRD',
    status: 'PENDING',
    summary: '64 tests',
  },

  fuota_release: {
    id: 'step-fuota-release',
    runId: 'run-1',
    nodeId: 'fuota_release',
    nodeType: 'FUOTA',
    nodeLabel: 'FUOTA Release',
    category: 'PRD',
    status: 'BLOCKED',
    fuotaTargets: '108.0.8.2-P, 109.0.8.2-P',
  },

  test_release: {
    id: 'step-test-release',
    runId: 'run-1',
    nodeId: 'test_release',
    nodeType: 'TEST',
    nodeLabel: 'Test Release',
    category: 'PRD',
    status: 'BLOCKED',
    summary: '64 tests',
  },
};

// Simulate FUOTA progress over time
export function simulateFuotaProgress(
  currentProgress: number,
  callback: (progress: number, pages: number, total: number) => void
) {
  const total = 512;
  let progress = currentProgress;

  const interval = setInterval(() => {
    progress += Math.random() * 3 + 1; // 1-4% per tick
    if (progress >= 100) {
      progress = 100;
      clearInterval(interval);
    }
    const pages = Math.floor((progress / 100) * total);
    callback(Math.round(progress), pages, total);
  }, 2000);

  return () => clearInterval(interval);
}
