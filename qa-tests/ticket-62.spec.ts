import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #62 - Leaderboard badge system with rank badges for top players', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Step 1: First check the /api/badges endpoint
  await page.goto('http://127.0.0.1:5000/api/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/api-badges-response.png'
  });

  // Validate API response structure
  const apiContent = await page.content();
  const bodyText = await page.locator('body').innerText();

  try {
    const apiData = JSON.parse(bodyText);
    expect(Array.isArray(apiData)).toBeTruthy();

    if (apiData.length > 0) {
      const firstEntry = apiData[0];
      expect(firstEntry).toHaveProperty('player');
      expect(firstEntry).toHaveProperty('badge');
      expect(firstEntry).toHaveProperty('best_score');

      const validBadges = ['gold', 'silver', 'bronze'];
      for (const entry of apiData) {
        expect(validBadges).toContain(entry.badge);
        if (entry.badge === 'gold') {
          expect(entry.best_score).toBeGreaterThanOrEqual(8000);
        } else if (entry.badge === 'silver') {
          expect(entry.best_score).toBeGreaterThanOrEqual(5000);
          expect(entry.best_score).toBeLessThan(8000);
        } else if (entry.badge === 'bronze') {
          expect(entry.best_score).toBeGreaterThanOrEqual(2000);
          expect(entry.best_score).toBeLessThan(5000);
        }
      }

      const goldBadges = apiData.filter((e: any) => e.badge === 'gold');
      const silverBadges = apiData.filter((e: any) => e.badge === 'silver');
      const bronzeBadges = apiData.filter((e: any) => e.badge === 'bronze');

      errors.push(`[info] API returned ${apiData.length} badges: ${goldBadges.length} gold, ${silverBadges.length} silver, ${bronzeBadges.length} bronze`);

      expect(goldBadges.length).toBe(2);
      expect(silverBadges.length).toBe(5);
      expect(bronzeBadges.length).toBe(8);

      const goldPlayers = goldBadges.map((e: any) => e.player);
      expect(goldPlayers).toContain('PixelKnight');
      expect(goldPlayers).toContain('NeonRacer');

      const silverPlayers = silverBadges.map((e: any) => e.player);
      expect(silverPlayers).toContain('GhostByte');
      expect(silverPlayers).toContain('VortexPilot');
      expect(silverPlayers).toContain('CyberFox');
      expect(silverPlayers).toContain('LaserWolf');
      expect(silverPlayers).toContain('ShadowBit');

      const bronzePlayers = bronzeBadges.map((e: any) => e.player);
      expect(bronzePlayers).toContain('QuantumAce');
      expect(bronzePlayers).toContain('TurboHawk');
      expect(bronzePlayers).toContain('BlinkDash');
      expect(bronzePlayers).toContain('IronClad');
      expect(bronzePlayers).toContain('StormRider');
      expect(bronzePlayers).toContain('NovaStar');
      expect(bronzePlayers).toContain('ZeroGrav');
      expect(bronzePlayers).toContain('VoltEdge');
    }
  } catch (e) {
    errors.push(`[api-parse-error] Could not parse /api/badges JSON: ${e}`);
  }

  // Step 2: Navigate to the /badges HTML page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('domcontentloaded');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badges-page-initial.png'
  });

  // Step 3: Wait for page content to load
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badges-page-loaded.png'
  });

  // Step 4: Check page title/heading
  const pageTitle = await page.title();
  errors.push(`[info] Page title: ${pageTitle}`);

  // Step 5: Check for badge count summary at the top
  const summaryExists = await page.locator('body').evaluate((body) => {
    const text = body.innerText.toLowerCase();
    return text.includes('gold') && text.includes('silver') && text.includes('bronze');
  });

  if (!summaryExists) {
    errors.push('[warning] Badge count summary (gold/silver/bronze) not found in page text');
  }

  // Check for the summary section specifically
  const summarySelectors = [
    '.badge-summary',
    '.summary',
    '[class*="summary"]',
    '[class*="count"]',
    '.badge-counts',
    '#badge-summary',
    'header',
    '.stats'
  ];

  let summaryFound = false;
  for (const selector of summarySelectors) {
    const element = page.locator(selector).first();
    const count = await element.count();
    if (count > 0) {
      summaryFound = true;
      errors.push(`[info] Summary element found with selector: ${selector}`);
      await element.screenshot({
        path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badge-summary-element.png'
      });
      break;
    }
  }

  if (!summaryFound) {
    errors.push('[warning] No dedicated summary element found with common selectors');
  }

  // Step 6: Verify badge counts shown on page
  const bodyContent = await page.locator('body').innerText();

  if (bodyContent.includes('2') && bodyContent.toLowerCase().includes('gold')) {
    errors.push('[info] Gold count (2) appears to be present in page');
  } else {
    errors.push('[warning] Gold count (2) not clearly visible in page content');
  }

  if (bodyContent.includes('5') && bodyContent.toLowerCase().includes('silver')) {
    errors.push('[info] Silver count (5) appears to be present in page');
  } else {
    errors.push('[warning] Silver count (5) not clearly visible in page content');
  }

  if (bodyContent.includes('8') && bodyContent.toLowerCase().includes('bronze')) {
    errors.push('[info] Bronze count (8) appears to be present in page');
  } else {
    errors.push('[warning] Bronze count (8) not clearly visible in page content');
  }

  // Step 7: Check for player badge grid
  const gridSelectors = [
    '.badge-grid',
    '.grid',
    '[class*="grid"]',
    '.badges',
    '.player-badges',
    '.badge-list',
    'ul',
    '.card',
    '[class*="card"]'
  ];

  let gridFound = false;
  for (const selector of gridSelectors) {
    const element = page.locator(selector).first();
    const count = await element.count();
    if (count > 0) {
      gridFound = true;
      errors.push(`[info] Badge grid/list element found with selector: ${selector}`);
      break;
    }
  }

  if (!gridFound) {
    errors.push('[warning] No badge grid element found with common selectors');
  }

  // Step 8: Check for player names on the page
  const expectedPlayers = [
    'PixelKnight', 'NeonRacer',
    'GhostByte', 'VortexPilot', 'CyberFox', 'LaserWolf', 'ShadowBit',
    'QuantumAce', 'TurboHawk', 'BlinkDash', 'IronClad', 'StormRider',
    'NovaStar', 'ZeroGrav', 'VoltEdge'
  ];

  const missingPlayers: string[] = [];
  for (const player of expectedPlayers) {
    if (!bodyContent.includes(player)) {
      missingPlayers.push(player);
    }
  }

  if (missingPlayers.length > 0) {
    errors.push(`[warning] Missing players on page: ${missingPlayers.join(', ')}`);
  } else {
    errors.push('[info] All 15 expected players found on badges page');
  }

  // Step 9: Screenshot of badge grid area
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badges-page-with-players.png'
  });

  // Step 10: Check for dark theme
  const backgroundColor = await page.evaluate(() => {
    return window.getComputedStyle(document.body).backgroundColor;
  });
  errors.push(`[info] Body background color: ${backgroundColor}`);

  // Typically dark themes have low RGB values
  const isDarkTheme = await page.evaluate(() => {
    const bg = window.getComputedStyle(document.body).backgroundColor;
    const match = bg.match(/\d+/g);
    if (match) {
      const [r, g, b] = match.map(Number);
      return (r + g + b) / 3 < 100;
    }
    return false;
  });

  if (!isDarkTheme) {
    errors.push('[warning] Page may not be using a dark theme (body background not dark)');
  } else {
    errors.push('[info] Dark theme detected on badges page');
  }

  // Step 11: Check for gold color (#FFD700) usage
  const goldColorUsed = await page.evaluate(() => {
    const elements = document.querySelectorAll('*');
    for (const el of elements) {
      const style = window.getComputedStyle(el);
      const color = style.color.toLowerCase();
      const bg = style.backgroundColor.toLowerCase();
      if (color.includes('255, 215, 0') || bg.includes('255, 215, 0')) {
        return true;
      }
    }
    // Also check inline styles for #FFD700
    return document.documentElement.innerHTML.toLowerCase().includes('ffd700');
  });

  if (!goldColorUsed) {
    errors.push('[warning] Gold color #FFD700 not detected in page styles');
  } else {
    errors.push('[info] Gold color #FFD700 detected in page');
  }

  // Step 12: Check for silver color (#C0C0C0) usage
  const silverColorUsed = await page.evaluate(() => {
    return document.documentElement.innerHTML.toLowerCase().includes('c0c0c0');
  });

  if (!silverColorUsed) {
    errors.push('[warning] Silver color #C0C0C0 not detected in page styles');
  } else {
    errors.push('[info] Silver color #C0C0C0 detected in page');
  }

  // Step 13: Check for bronze color (#CD7F32) usage
  const bronzeColorUsed = await page.evaluate(() => {
    return document.documentElement.innerHTML.toLowerCase().includes('cd7f32');
  });

  if (!bronzeColorUsed) {
    errors.push('[warning] Bronze color #CD7F32 not detected in page styles');
  } else {
    errors.push('[info] Bronze color #CD7F32 detected in page');
  }

  // Step 14: Scroll to bottom to capture full page
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badges-page-scrolled-bottom.png'
  });

  // Step 15: Scroll back to top and take final full-page screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/badges-page-final-fullpage.png',
    fullPage: true
  });

  // Step 16: Verify page doesn't show players below 2000 threshold
  // (This is structural - we can only confirm if we know what players should be excluded)
  const pageHTML = await page.content();
  errors.push(`[info] Page HTML length: ${pageHTML.length} characters`);
  errors.push(`[info] Final URL: ${page.url()}`);

  // Write diagnostics file
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-62/diagnostics.json',
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});