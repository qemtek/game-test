import { test } from '@playwright/test';
import * as path from 'path';

const SCREENSHOT_DIR = '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69';

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
    path: `${SCREENSHOT_DIR}/streaks-page-full.png`,
    fullPage: true
  });

  // Try to capture the streak table specifically
  const tableSelector = 'table';
  const tableExists = await page.$(tableSelector);
  if (tableExists) {
    await page.waitForSelector(tableSelector, { timeout: 5000 });
    await tableExists.screenshot({
      path: `${SCREENSHOT_DIR}/streaks-table-focused.png`
    });
  } else {
    // Fallback: screenshot of the main content area or body
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/streaks-table-focused.png`,
      fullPage: false
    });
  }

  // Also check the API endpoint for diagnostics
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/streaks');
  if (apiResponse.status() >= 400) {
    errors.push(`[api-check] /api/streaks returned ${apiResponse.status()}`);
  } else {
    try {
      const apiJson = await apiResponse.json();
      errors.push(`[api-info] /api/streaks returned ${Array.isArray(apiJson) ? apiJson.length : 'non-array'} records`);
    } catch {
      errors.push(`[api-info] /api/streaks response could not be parsed as JSON`);
    }
  }

  // Look for highlighted rows (streaks >= 3 days)
  const highlightedRows = await page.$$('tr.highlight, tr.streak-highlight, .streak-high, [class*="highlight"], [class*="streak"]');
  errors.push(`[info] Found ${highlightedRows.length} potentially highlighted streak rows`);

  // Screenshot focused on top of page to capture header/title area
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/streaks-header-area.png`,
    clip: { x: 0, y: 0, width: 1280, height: 400 }
  });

  // Write diagnostics
  const fs = require('fs');
  fs.writeFileSync(
    `${SCREENSHOT_DIR}/diagnostics.json`,
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});