import { test } from '@playwright/test';
import * as path from 'path';

test('Ticket #69 - Player streak tracker visual QA', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Navigate to the streaks HTML page
  await page.goto('http://127.0.0.1:5000/streaks');
  await page.waitForLoadState('networkidle');

  // Full-page screenshot of the streaks page
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streaks-page-full.png',
    fullPage: true,
  });

  // Try to capture a focused screenshot of the streak table if it exists
  const tableSelector = 'table';
  const tableHandle = await page.$(tableSelector);
  if (tableHandle) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streaks-table-focused.png',
      clip: await tableHandle.boundingBox() ?? undefined,
    });
  } else {
    // If no table, screenshot the main content area or body
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streaks-table-focused.png',
      fullPage: false,
    });
  }

  // Also hit the API endpoint and capture state
  await page.goto('http://127.0.0.1:5000/api/streaks');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streaks-api-response.png',
    fullPage: true,
  });

  // Write diagnostics
  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/diagnostics.json',
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});