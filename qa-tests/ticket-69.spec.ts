import { test } from '@playwright/test';
import * as path from 'path';

test('ticket-69 streak tracker visual QA', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`); });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => { if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`); });

  await page.goto('http://127.0.0.1:5000/streaks');
  await page.waitForLoadState('networkidle');

  // Full-page screenshot of the streaks page
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streaks-full-page.png',
    fullPage: true
  });

  // Try to locate and screenshot the streak table area
  const tableSelectors = ['table', '.streak-table', '#streak-table', '[class*="streak"]', '[id*="streak"]', 'tbody'];
  let tableCaptured = false;
  for (const selector of tableSelectors) {
    const el = page.locator(selector).first();
    const count = await el.count();
    if (count > 0) {
      try {
        await el.scrollIntoViewIfNeeded();
        await page.screenshot({
          path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-table-focused.png'
        });
        tableCaptured = true;
        break;
      } catch {
        // continue
      }
    }
  }

  if (!tableCaptured) {
    // Fallback: screenshot the main content area
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-table-focused.png'
    });
  }

  // Check if any highlighted rows exist (streaks >= 3) and screenshot
  const highlightSelectors = [
    '.highlight', '.highlighted', '[class*="highlight"]',
    'tr.streak-high', 'tr.active', '[class*="active"]',
    'tr[style*="background"]', 'tr[class*="hot"]', 'tr[class*="fire"]'
  ];
  let highlightCaptured = false;
  for (const selector of highlightSelectors) {
    const el = page.locator(selector).first();
    const count = await el.count();
    if (count > 0) {
      try {
        await el.scrollIntoViewIfNeeded();
        await page.screenshot({
          path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-highlighted-rows.png'
        });
        highlightCaptured = true;
        break;
      } catch {
        // continue
      }
    }
  }

  if (!highlightCaptured) {
    // Also check /api/streaks endpoint and capture a screenshot showing the page state
    await page.goto('http://127.0.0.1:5000/api/streaks');
    await page.waitForLoadState('networkidle');
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/streak-highlighted-rows.png',
      fullPage: true
    });
  }

  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-69/diagnostics.json',
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});