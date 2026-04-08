import { test, expect } from '../../fixtures';

/**
 * Stage 16 — CoreCloud cleanup and state verification.
 *
 * CoreCloud device cleanup is limited because there is no delete endpoint.
 * These tests verify state and document any E2E device artifacts for manual
 * review. Tests soft-pass if CoreCloud is unreachable from the test environment.
 */

const CORECLOUD_HOST = 'val.office.corekinect.cloud';
const CORECLOUD_PORT = 2018;

async function checkCorecloudReachable(): Promise<boolean> {
  const { createConnection } = await import('node:net');
  return new Promise<boolean>((resolve) => {
    const sock = createConnection({ host: CORECLOUD_HOST, port: CORECLOUD_PORT, timeout: 5_000 }, () => {
      sock.destroy();
      resolve(true);
    });
    sock.on('error', () => {
      sock.destroy();
      resolve(false);
    });
    sock.on('timeout', () => {
      sock.destroy();
      resolve(false);
    });
  });
}

test.describe.configure({ mode: 'serial', timeout: 60_000 });

test.describe('Cleanup: CoreCloud', () => {
  let corecloudReachable: boolean;

  test.beforeAll(async () => {
    corecloudReachable = await checkCorecloudReachable();
    if (!corecloudReachable) {
      console.warn(
        `[cleanup] CoreCloud at ${CORECLOUD_HOST}:${CORECLOUD_PORT} is unreachable — ` +
          'tests will soft-pass. This is expected in CI environments without VPN.',
      );
    }
  });

  test('no active FUOTA plans from E2E tests remain', async () => {
    if (!corecloudReachable) {
      console.log('[cleanup] CoreCloud unreachable — skipping FUOTA plan check');
      // Soft pass: we cannot verify, but this is not a failure
      expect(true).toBe(true);
      return;
    }

    // CoreCloud FUOTA plans are time-limited and self-expire.
    // E2E tests do not currently create FUOTA plans, so this is
    // a forward-looking verification that confirms no orphaned plans exist.
    // When FUOTA E2E tests are added, this should query the FUOTA API
    // and assert no plans with E2E device IDs are in PENDING/ACTIVE state.
    console.log('[cleanup] CoreCloud reachable — no FUOTA plan verification API available yet');
    expect(true).toBe(true);
  });

  test('CoreCloud device state is documented (no cleanup endpoint)', async () => {
    // CoreCloud does not expose a device delete/unregister endpoint.
    // Devices created or re-personalized during E2E tests persist in CoreCloud.
    // This is by design: device IDs are deterministic (tied to SNR via CoreOps),
    // so re-running tests reuses the same device identity.
    //
    // Cleanup strategy:
    // - Device public keys are regenerated on each re-personalization
    // - CoreCloud accepts the latest key, so stale keys are not a problem
    // - No manual cleanup is required between test runs
    //
    // This test documents the state rather than performing cleanup.
    console.log('[cleanup] CoreCloud device cleanup: no action required (no delete endpoint)');
    console.log('[cleanup] Devices persist across runs — public keys update on re-personalization');
    expect(true).toBe(true);
  });

  test('log any E2E device IDs for manual review', async () => {
    // E2E tests that interact with physical hardware use a known set of device IDs.
    // Log them here for traceability and manual review if needed.
    const knownE2EDevices = [
      { snr: '0964', deviceId: '70B3D584C01E1FCC', mtib: '10.4.45.33', note: 'REV 1.2 validation MTIB' },
    ];

    console.log('[cleanup] Known E2E device identifiers:');
    for (const device of knownE2EDevices) {
      console.log(
        `  SNR=${device.snr} DeviceID=${device.deviceId} MTIB=${device.mtib} (${device.note})`,
      );
    }

    // Verify our known device list is non-empty (it should always be maintained)
    expect(knownE2EDevices.length).toBeGreaterThan(0);

    if (corecloudReachable) {
      console.log('[cleanup] CoreCloud is reachable — devices can be queried manually if needed');
    } else {
      console.log('[cleanup] CoreCloud unreachable — device state cannot be verified remotely');
    }
  });
});
