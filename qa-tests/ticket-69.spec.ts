import { test } from '@playwright/test';
import * as path from 'path';

test('Ticket 69 - Player streak tracker visual QA', async ({ page }) => {
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

  // Try to focus on the streak table if it exists
  const tableLocator = page.locator('table');
  const tableCount = await tableLocator.count();
  if (tableCount > 0) {
    await tableLocator.first().scrollIntoViewIfNeeded();
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-table-focused.png',
      fullPage: false,
    });
  } else {
    // If no table, screenshot whatever content is present
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-table-focused.png',
      fullPage: false,
    });
  }

  // Also hit the JSON API endpoint and capture a screenshot of the raw JSON response
  await page.goto('http://127.0.0.1:5000/api/streaks');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/api-streaks-json.png',
    fullPage: true,
  });

  // Write diagnostics
  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/diagnostics.json',
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});