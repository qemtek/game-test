import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #61 - Leaderboard badge system with rank badges for top players', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Step 1: First check the API endpoint
  await page.goto('http://127.0.0.1:5000/api/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/api-badges-response.png'
  });

  // Capture raw API response text
  const apiBodyText = await page.evaluate(() => document.body.innerText);
  let apiBadgesData: any = null;
  try {
    apiBadgesData = JSON.parse(apiBodyText);
  } catch (e) {
    errors.push(`[parse] Failed to parse /api/badges JSON: ${e}`);
  }

  // Step 2: Navigate to the badges HTML page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('domcontentloaded');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badges-page-initial.png'
  });

  // Step 3: Wait for main content to load
  try {
    await page.waitForSelector('body', { timeout: 5000 });
  } catch (e) {
    errors.push(`[selector] body not found: ${e}`);
  }

  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badges-page-loaded.png'
  });

  // Step 4: Check for badge count summary at the top
  let badgeSummaryVisible = false;
  try {
    // Try various selectors that might be used for a badge count summary
    const summarySelectors = [
      '.badge-summary',
      '.badge-count',
      '.summary',
      '#badge-summary',
      '#summary',
      '[class*="summary"]',
      '[class*="count"]',
      'h2',
      'h3',
      '.stats'
    ];

    for (const selector of summarySelectors) {
      const el = await page.$(selector);
      if (el) {
        badgeSummaryVisible = true;
        break;
      }
    }
  } catch (e) {
    errors.push(`[check] Badge summary check failed: ${e}`);
  }

  // Step 5: Screenshot of the top section (badge count summary)
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badge-count-summary.png',
    clip: { x: 0, y: 0, width: 1280, height: 300 }
  });

  // Step 6: Check for gold badge players
  const pageContent = await page.content();
  const goldPlayers = ['PixelKnight', 'NeonRacer'];
  const silverPlayers = ['GhostByte', 'VortexPilot', 'CyberFox', 'LaserWolf', 'ShadowBit'];
  const bronzePlayers = ['QuantumAce', 'TurboHawk', 'BlinkDash', 'IronClad', 'StormRider', 'NovaStar', 'ZeroGrav', 'VoltEdge'];

  const missingGold: string[] = [];
  const missingSilver: string[] = [];
  const missingBronze: string[] = [];

  for (const player of goldPlayers) {
    if (!pageContent.includes(player)) {
      missingGold.push(player);
      errors.push(`[visual] Gold player missing from page: ${player}`);
    }
  }

  for (const player of silverPlayers) {
    if (!pageContent.includes(player)) {
      missingSilver.push(player);
      errors.push(`[visual] Silver player missing from page: ${player}`);
    }
  }

  for (const player of bronzePlayers) {
    if (!pageContent.includes(player)) {
      missingBronze.push(player);
      errors.push(`[visual] Bronze player missing from page: ${player}`);
    }
  }

  // Step 7: Screenshot showing the badge grid
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badge-grid.png'
  });

  // Step 8: Check for badge grid container
  try {
    const gridSelectors = [
      '.badge-grid',
      '.grid',
      '#badge-grid',
      '[class*="grid"]',
      '.badges',
      '#badges',
      '.card',
      '.player-badge',
      'table',
      'ul',
      'ol'
    ];

    let gridFound = false;
    for (const selector of gridSelectors) {
      const el = await page.$(selector);
      if (el) {
        gridFound = true;
        await page.screenshot({
          path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badge-grid-element.png'
        });
        break;
      }
    }
    if (!gridFound) {
      errors.push('[visual] No badge grid container element found on page');
    }
  } catch (e) {
    errors.push(`[check] Badge grid check failed: ${e}`);
  }

  // Step 9: Check for gold color (#FFD700)
  const hasGoldColor = pageContent.includes('#FFD700') || pageContent.includes('ffd700') || pageContent.includes('FFD700') || pageContent.includes('gold');
  if (!hasGoldColor) {
    errors.push('[visual] Gold color (#FFD700) not found in page source');
  }

  // Step 10: Check for silver color (#C0C0C0)
  const hasSilverColor = pageContent.includes('#C0C0C0') || pageContent.includes('c0c0c0') || pageContent.includes('C0C0C0') || pageContent.includes('silver');
  if (!hasSilverColor) {
    errors.push('[visual] Silver color (#C0C0C0) not found in page source');
  }

  // Step 11: Check for bronze color (#CD7F32)
  const hasBronzeColor = pageContent.includes('#CD7F32') || pageContent.includes('cd7f32') || pageContent.includes('CD7F32') || pageContent.includes('bronze');
  if (!hasBronzeColor) {
    errors.push('[visual] Bronze color (#CD7F32) not found in page source');
  }

  // Step 12: Dark theme check — look for dark background colors
  const hasDarkTheme = pageContent.includes('#1a1a') || pageContent.includes('#2a2a') || pageContent.includes('#0d0d') ||
    pageContent.includes('background') && (pageContent.includes('#1') || pageContent.includes('#2') || pageContent.includes('dark'));
  if (!hasDarkTheme) {
    errors.push('[visual] Dark theme styling not detected in page source');
  }

  // Step 13: Check API badges endpoint structure if data was parsed
  if (apiBadgesData !== null) {
    if (!Array.isArray(apiBadgesData)) {
      errors.push('[api] /api/badges did not return a JSON array');
    } else {
      const expectedFields = ['player', 'badge', 'best_score'];
      if (apiBadgesData.length > 0) {
        const firstItem = apiBadgesData[0];
        for (const field of expectedFields) {
          if (!(field in firstItem)) {
            errors.push(`[api] Badge object missing field: ${field}`);
          }
        }
      } else {
        errors.push('[api] /api/badges returned empty array — no badge assignments found');
      }

      // Check badge value thresholds
      for (const badge of apiBadgesData) {
        if (badge.badge === 'gold' && badge.best_score < 8000) {
          errors.push(`[api] Gold badge assigned incorrectly: ${badge.player} has score ${badge.best_score} (needs >= 8000)`);
        }
        if (badge.badge === 'silver' && (badge.best_score < 5000 || badge.best_score > 7999)) {
          errors.push(`[api] Silver badge assigned incorrectly: ${badge.player} has score ${badge.best_score} (needs 5000-7999)`);
        }
        if (badge.badge === 'bronze' && (badge.best_score < 2000 || badge.best_score > 4999)) {
          errors.push(`[api] Bronze badge assigned incorrectly: ${badge.player} has score ${badge.best_score} (needs 2000-4999)`);
        }
      }

      const goldCount = apiBadgesData.filter((b: any) => b.badge === 'gold').length;
      const silverCount = apiBadgesData.filter((b: any) => b.badge === 'silver').length;
      const bronzeCount = apiBadgesData.filter((b: any) => b.badge === 'bronze').length;

      if (goldCount !== 2) errors.push(`[api] Expected 2 gold badges, got ${goldCount}`);
      if (silverCount !== 5) errors.push(`[api] Expected 5 silver badges, got ${silverCount}`);
      if (bronzeCount !== 8) errors.push(`[api] Expected 8 bronze badges, got ${bronzeCount}`);
    }
  }

  // Step 14: Scroll down to capture full page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badges-page-scrolled-bottom.png'
  });

  await page.evaluate(() => window.scrollTo(0, 0));

  // Step 15: Full page screenshot
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/badges-page-full.png',
    fullPage: true
  });

  // Step 16: Structural assertions (bonus)
  const title = await page.title();
  expect(title).toBeTruthy();

  // Check that the page has some content
  const bodyText = await page.evaluate(() => document.body.innerText);
  expect(bodyText.length).toBeGreaterThan(0);

  // Check that the page URL is correct
  expect(page.url()).toContain('/badges');

  // Write diagnostics file
  const diagnostics = {
    errors,
    url: page.url(),
    summary: {
      badgeSummaryVisible,
      hasGoldColor,
      hasSilverColor,
      hasBronzeColor,
      hasDarkTheme,
      missingGoldPlayers: missingGold,
      missingSilverPlayers: missingSilver,
      missingBronzePlayers: missingBronze,
      apiDataParsed: apiBadgesData !== null,
      apiBadgeCount: Array.isArray(apiBadgesData) ? apiBadgesData.length : 0,
      pageTitle: title,
      pageContentLength: pageContent.length
    }
  };

  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-61/diagnostics.json',
    JSON.stringify(diagnostics, null, 2)
  );
});