import { test } from '@playwright/test';
import * as path from 'path';

test('ticket-67: player achievements system milestone tracking', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Navigate to achievements page
  await page.goto('http://127.0.0.1:5000/achievements');
  await page.waitForLoadState('networkidle');

  // Full-page screenshot of achievements page
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-67/achievements-full-page.png',
    fullPage: true
  });

  // Try to capture the achievements table area if it exists
  const tableLocator = page.locator('table');
  const tableCount = await tableLocator.count();
  if (tableCount > 0) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-67/achievements-table-focused.png',
      fullPage: false
    });
  } else {
    // Try to capture the main content area
    const mainContent = page.locator('main, .container, body');
    await mainContent.first().screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-67/achievements-table-focused.png'
    });
  }

  // Also check the JSON API endpoint for diagnostics
  const apiResponse = await page.evaluate(async () => {
    try {
      const res = await fetch('/api/achievements');
      const text = await res.text();
      return { status: res.status, body: text };
    } catch (e: any) {
      return { status: 0, body: e.message };
    }
  });

  if (apiResponse.status >= 400 || apiResponse.status === 0) {
    errors.push(`[api] /api/achievements returned status ${apiResponse.status}: ${apiResponse.body}`);
  }

  // Navigate to /api/achievements to screenshot JSON output
  await page.goto('http://127.0.0.1:5000/api/achievements');
  await page.waitForLoadState('networkidle');
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-67/api-achievements-json.png',
    fullPage: true
  });

  // Write diagnostics
  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-67/diagnostics.json',
    JSON.stringify({ errors, url: page.url(), apiResponse }, null, 2)
  );
});