import { test } from '@playwright/test';
import * as path from 'path';

const SCREENSHOT_DIR = '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-66';

test('Ticket 66 - Leaderboard badge system visual QA', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // First check the API endpoint
  await page.goto('http://127.0.0.1:5000/api/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: `${SCREENSHOT_DIR}/api-badges-response.png`,
    fullPage: true
  });

  // Navigate to the badges HTML page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  // Full page screenshot of the badges page
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/badges-page-full.png`,
    fullPage: true
  });

  // Try to capture badge count summary at the top
  const summarySelectors = [
    '.badge-summary',
    '.badge-count',
    '.summary',
    '#badge-summary',
    '#summary',
    'header',
    '.header',
    '.stats',
    '.counts',
    'h1',
    'h2'
  ];

  let summaryCaptured = false;
  for (const selector of summarySelectors) {
    try {
      const el = await page.$(selector);
      if (el) {
        await page.screenshot({
          path: `${SCREENSHOT_DIR}/badge-count-summary.png`,
          fullPage: false
        });
        summaryCaptured = true;
        break;
      }
    } catch (_) {}
  }

  if (!summaryCaptured) {
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/badge-count-summary.png`,
      fullPage: false
    });
  }

  // Try to capture the badge grid area
  const gridSelectors = [
    '.badge-grid',
    '.badges-grid',
    '.grid',
    '#badge-grid',
    '#badges-grid',
    '.badges-container',
    '.badge-list',
    '.player-badges',
    'table',
    'ul',
    'ol'
  ];

  let gridCaptured = false;
  for (const selector of gridSelectors) {
    try {
      const el = await page.$(selector);
      if (el) {
        const boundingBox = await el.boundingBox();
        if (boundingBox) {
          await page.screenshot({
            path: `${SCREENSHOT_DIR}/badge-grid-focused.png`,
            clip: {
              x: boundingBox.x,
              y: boundingBox.y,
              width: Math.min(boundingBox.width, 1280),
              height: Math.min(boundingBox.height, 800)
            }
          });
          gridCaptured = true;
          break;
        }
      }
    } catch (_) {}
  }

  if (!gridCaptured) {
    // Scroll to middle of page and screenshot to capture grid area
    await page.evaluate(() => window.scrollTo(0, 300));
    await page.waitForTimeout(500);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/badge-grid-focused.png`,
      fullPage: false
    });
  }

  // Write diagnostics
  const fs = require('fs');
  fs.writeFileSync(
    `${SCREENSHOT_DIR}/diagnostics.json`,
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});