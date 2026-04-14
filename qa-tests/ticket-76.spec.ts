import { test } from '@playwright/test';
import * as path from 'path';

test('Ticket #76 - Top-3 podium display on /scoreboard', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  await page.goto('http://127.0.0.1:5000/scoreboard');
  await page.waitForLoadState('networkidle');

  // Full-page screenshot of the scoreboard
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/scoreboard-full-page.png',
    fullPage: true,
  });

  // Attempt to scroll to / focus on the podium section at the top
  // Try to locate the podium or TOP PLAYERS heading area
  const podiumOrHeading = page.locator('text=TOP PLAYERS').first();
  const podiumOrHeadingCount = await podiumOrHeading.count();

  if (podiumOrHeadingCount > 0) {
    await podiumOrHeading.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    // Screenshot focused on the TOP PLAYERS / podium area
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/podium-heading-focused.png',
      fullPage: false,
    });
  } else {
    // Fallback: screenshot the top portion of the page viewport
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/podium-heading-focused.png',
      fullPage: false,
    });
  }

  // Try to capture the podium columns specifically (look for podium container)
  const podiumContainer = page.locator('.podium, [class*="podium"], .top-players, [class*="top-player"]').first();
  const podiumContainerCount = await podiumContainer.count();

  if (podiumContainerCount > 0) {
    const box = await podiumContainer.boundingBox();
    if (box) {
      await page.screenshot({
        path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/podium-columns-closeup.png',
        clip: {
          x: Math.max(0, box.x - 20),
          y: Math.max(0, box.y - 20),
          width: box.width + 40,
          height: box.height + 40,
        },
      });
    }
  } else {
    // Fallback: screenshot upper viewport area where podium should be
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);
    const viewportSize = page.viewportSize();
    const width = viewportSize?.width ?? 1280;
    const height = viewportSize?.height ?? 720;
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/podium-columns-closeup.png',
      clip: {
        x: 0,
        y: 0,
        width: width,
        height: Math.min(500, height),
      },
    });
  }

  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-76/diagnostics.json',
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});