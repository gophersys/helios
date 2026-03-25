#!/usr/bin/env node
/**
 * Playwright smoke test — navigates all frontend pages, checks for errors.
 */

const { chromium } = require('playwright');

const BASE = process.env.BASE_URL || 'https://staging.concord.local';
const TIMEOUT = 10000;

const ROUTES = [
  '/',
  '/products',
  '/builds',
  '/builds/pipelines',
  '/validation',
  '/validation/runs',
  '/validation/queue',
  '/validation/benches',
  '/validation/benches/register',
  '/validation/designs',
  '/deployments',
  '/mtib',
  '/fixtures',
  '/kubernetes',
  '/kubernetes/pods',
  '/kubernetes/deployments',
  '/kubernetes/services',
  '/kubernetes/jobs',
  '/kubernetes/nodes',
  '/kubernetes/events',
  '/kubernetes/config',
  '/kubernetes/rbac',
  '/history',
  '/users',
  '/settings',
];

async function main() {
  const browser = await chromium.launch({ args: ['--ignore-certificate-errors', '--no-sandbox'] });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();

  const results = [];

  for (const route of ROUTES) {
    const url = `${BASE}${route}`;
    const pageErrors = [];

    const errorHandler = msg => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (text.includes('favicon') || text.includes('net::ERR')) return;
        pageErrors.push(text.substring(0, 200));
      }
    };
    const crashHandler = err => {
      pageErrors.push(`CRASH: ${err.message.substring(0, 200)}`);
    };

    page.on('console', errorHandler);
    page.on('pageerror', crashHandler);

    try {
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await page.waitForTimeout(500);

      const status = response?.status() || 0;
      const bodyText = await page.textContent('body').catch(() => '');

      if (bodyText.includes('Request failed') || bodyText.includes('request failed'))
        pageErrors.push('Request failed visible on page');
      if (bodyText.includes('Internal Error') || bodyText.includes('Unexpected error'))
        pageErrors.push('Internal error visible on page');

      const passed = status < 400 && pageErrors.length === 0;
      results.push({ route, status, passed, issues: [...pageErrors] });

      const icon = passed ? '✓' : '✗';
      const issueStr = pageErrors.length > 0 ? ` — ${pageErrors.join('; ')}` : '';
      console.log(`  ${icon} ${route} (${status})${issueStr}`);

    } catch (err) {
      results.push({ route, status: 0, passed: false, issues: [err.message.substring(0, 100)] });
      console.log(`  ✗ ${route} — ${err.message.substring(0, 80)}`);
    }

    page.removeListener('console', errorHandler);
    page.removeListener('pageerror', crashHandler);
  }

  await browser.close();

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  console.log(`\n${'='.repeat(50)}`);
  console.log(`Results: ${passed} passed, ${failed} failed out of ${results.length} pages`);

  if (failed > 0) {
    console.log('\nFailed pages:');
    for (const r of results.filter(r => !r.passed)) {
      console.log(`  ${r.route}: ${r.issues.join('; ')}`);
    }
    process.exit(1);
  }
}

main().catch(err => { console.error('Fatal:', err); process.exit(2); });
