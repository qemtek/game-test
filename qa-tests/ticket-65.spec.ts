import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #65 - Leaderboard badge system with rank badges for top players', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Step 1: Test the /api/badges endpoint first
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/badges');
  const apiStatus = apiResponse.status();
  errors.push(`[info] /api/badges status: ${apiStatus}`);

  let badgesData: any[] = [];
  if (apiStatus === 200) {
    try {
      badgesData = await apiResponse.json();
      errors.push(`[info] /api/badges returned ${badgesData.length} badge entries`);

      // Validate badge structure
      const goldBadges = badgesData.filter((b: any) => b.badge === 'gold');
      const silverBadges = badgesData.filter((b: any) => b.badge === 'silver');
      const bronzeBadges = badgesData.filter((b: any) => b.badge === 'bronze');

      errors.push(`[info] Gold badges: ${goldBadges.length}, Silver: ${silverBadges.length}, Bronze: ${bronzeBadges.length}`);

      // Validate expected players
      const goldPlayers = goldBadges.map((b: any) => b.player);
      const silverPlayers = silverBadges.map((b: any) => b.player);
      const bronzePlayers = bronzeBadges.map((b: any) => b.player);

      if (!goldPlayers.includes('PixelKnight')) errors.push('[warn] PixelKnight not found in gold badges');
      if (!goldPlayers.includes('NeonRacer')) errors.push('[warn] NeonRacer not found in gold badges');
      if (!silverPlayers.includes('GhostByte')) errors.push('[warn] GhostByte not found in silver badges');
      if (!bronzePlayers.includes('QuantumAce')) errors.push('[warn] QuantumAce not found in bronze badges');

      const voltEdge = badgesData.find((b: any) => b.player === 'VoltEdge');
      if (voltEdge) errors.push('[warn] VoltEdge should be excluded (score < 2000) but found in badges');
      else errors.push('[info] VoltEdge correctly excluded from badges (score < 2000)');

    } catch (e) {
      errors.push(`[error] Failed to parse /api/badges JSON: ${e}`);
    }
  }

  // Step 2: Navigate to /badges HTML page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  // Screenshot of initial page load
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/01-badges-page-initial.png',
    fullPage: true
  });

  // Step 3: Check page title/heading
  const pageTitle = await page.title();
  errors.push(`[info] Page title: ${pageTitle}`);

  // Step 4: Look for badge count summary at the top
  const summaryExists = await page.locator('text=/Gold|Silver|Bronze/').first().isVisible().catch(() => false);
  if (!summaryExists) {
    errors.push('[warn] Badge count summary section not clearly visible');
  }

  // Check for summary counts: 2 Gold, 5 Silver, 8 Bronze
  const goldSummary = await page.locator('text=/2.*Gold|Gold.*2/i').first().isVisible().catch(() => false);
  const silverSummary = await page.locator('text=/5.*Silver|Silver.*5/i').first().isVisible().catch(() => false);
  const bronzeSummary = await page.locator('text=/8.*Bronze|Bronze.*8/i').first().isVisible().catch(() => false);

  if (!goldSummary) errors.push('[warn] Gold count summary "2 Gold" not found');
  if (!silverSummary) errors.push('[warn] Silver count summary "5 Silver" not found');
  if (!bronzeSummary) errors.push('[warn] Bronze count summary "8 Bronze" not found');

  // Screenshot of summary section
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/02-badge-count-summary.png',
    fullPage: false
  });

  // Step 5: Check gold badge players (PixelKnight, NeonRacer)
  const pixelKnightVisible = await page.locator('text=PixelKnight').isVisible().catch(() => false);
  const neonRacerVisible = await page.locator('text=NeonRacer').isVisible().catch(() => false);

  if (!pixelKnightVisible) errors.push('[warn] PixelKnight not visible on /badges page');
  if (!neonRacerVisible) errors.push('[warn] NeonRacer not visible on /badges page');

  // Step 6: Check silver badge players
  const silverPlayers = ['GhostByte', 'VortexPilot', 'CyberFox', 'LaserWolf', 'ShadowBit'];
  for (const player of silverPlayers) {
    const visible = await page.locator(`text=${player}`).isVisible().catch(() => false);
    if (!visible) errors.push(`[warn] Silver player ${player} not visible on /badges page`);
  }

  // Step 7: Check bronze badge players
  const bronzePlayers = ['QuantumAce', 'TurboHawk', 'BlinkDash', 'IronClad', 'StormRider', 'NovaStar', 'ZeroGrav', 'PulseMax'];
  for (const player of bronzePlayers) {
    const visible = await page.locator(`text=${player}`).isVisible().catch(() => false);
    if (!visible) errors.push(`[warn] Bronze player ${player} not visible on /badges page`);
  }

  // Step 8: Check VoltEdge is excluded
  const voltEdgeVisible = await page.locator('text=VoltEdge').isVisible().catch(() => false);
  if (voltEdgeVisible) errors.push('[warn] VoltEdge is visible on /badges page but should be excluded (score < 2000)');
  else errors.push('[info] VoltEdge correctly not shown on /badges page');

  // Screenshot showing gold badge players
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/03-gold-badge-players.png',
    fullPage: true
  });

  // Step 9: Check badge colors in CSS/styles
  // Check for gold color #FFD700
  const goldColorPresent = await page.evaluate(() => {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const style = window.getComputedStyle(el);
      const color = style.color || '';
      const bg = style.backgroundColor || '';
      const borderColor = style.borderColor || '';
      if (color.includes('255, 215, 0') || bg.includes('255, 215, 0') || borderColor.includes('255, 215, 0')) {
        return true;
      }
    }
    // Also check inline styles and class names
    const html = document.body.innerHTML;
    return html.includes('#FFD700') || html.includes('ffd700') || html.includes('FFD700');
  });
  if (!goldColorPresent) errors.push('[warn] Gold color #FFD700 not detected in page');
  else errors.push('[info] Gold color #FFD700 detected');

  // Check for silver color #C0C0C0
  const silverColorPresent = await page.evaluate(() => {
    const html = document.body.innerHTML;
    return html.includes('#C0C0C0') || html.includes('c0c0c0') || html.includes('C0C0C0') ||
           html.toLowerCase().includes('192, 192, 192');
  });
  if (!silverColorPresent) errors.push('[warn] Silver color #C0C0C0 not detected in page');
  else errors.push('[info] Silver color #C0C0C0 detected');

  // Check for bronze color #CD7F32
  const bronzeColorPresent = await page.evaluate(() => {
    const html = document.body.innerHTML;
    return html.includes('#CD7F32') || html.includes('cd7f32') || html.includes('CD7F32') ||
           html.toLowerCase().includes('205, 127, 50');
  });
  if (!bronzeColorPresent) errors.push('[warn] Bronze color #CD7F32 not detected in page');
  else errors.push('[info] Bronze color #CD7F32 detected');

  // Step 10: Check dark theme
  const bgColor = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);
    return style.backgroundColor;
  });
  errors.push(`[info] Body background color: ${bgColor}`);

  // Dark theme check — background should be dark
  const isDarkTheme = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);
    const bg = style.backgroundColor;
    // Parse rgb values
    const match = bg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      const r = parseInt(match[1]);
      const g = parseInt(match[2]);
      const b = parseInt(match[3]);
      // Dark theme means low RGB values
      return (r + g + b) < 200;
    }
    return false;
  });
  if (!isDarkTheme) errors.push('[warn] Page does not appear to use dark theme background');
  else errors.push('[info] Dark theme confirmed');

  // Step 11: Check badge grid structure
  const gridExists = await page.locator('.badge-grid, .grid, [class*="grid"], [class*="badge"]').first().isVisible().catch(() => false);
  if (!gridExists) errors.push('[warn] Badge grid container not found with expected class names');
  else errors.push('[info] Badge grid container found');

  // Screenshot of badge grid
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/04-badge-player-grid.png',
    fullPage: true
  });

  // Step 12: Scroll to bottom to capture all bronze players
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/05-badge-grid-bottom-bronze.png',
    fullPage: false
  });

  // Step 13: Scroll back to top and take final full-page screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/06-badges-full-page-final.png',
    fullPage: true
  });

  // Step 14: Check score values are displayed
  const score9800 = await page.locator('text=9800').isVisible().catch(() => false);
  const score8750 = await page.locator('text=8750').isVisible().catch(() => false);
  if (!score9800) errors.push('[warn] PixelKnight score 9800 not visible');
  if (!score8750) errors.push('[warn] NeonRacer score 8750 not visible');

  // Step 15: Structural assertions
  expect(apiStatus).toBe(200);

  if (badgesData.length > 0) {
    // Validate badge objects have required fields
    const sampleBadge = badgesData[0];
    expect(sampleBadge).toHaveProperty('player');
    expect(sampleBadge).toHaveProperty('badge');
    expect(sampleBadge).toHaveProperty('best_score');

    // Validate badge values are one of the expected types
    const validBadges = ['gold', 'silver', 'bronze'];
    for (const badge of badgesData) {
      expect(validBadges).toContain(badge.badge);
    }

    // Validate gold badge threshold (score >= 8000)
    const goldBadges = badgesData.filter((b: any) => b.badge === 'gold');
    for (const badge of goldBadges) {
      expect(badge.best_score).toBeGreaterThanOrEqual(8000);
    }

    // Validate silver badge threshold (5000-7999)
    const silverBadgeEntries = badgesData.filter((b: any) => b.badge === 'silver');
    for (const badge of silverBadgeEntries) {
      expect(badge.best_score).toBeGreaterThanOrEqual(5000);
      expect(badge.best_score).toBeLessThan(8000);
    }

    // Validate bronze badge threshold (2000-4999)
    const bronzeBadgeEntries = badgesData.filter((b: any) => b.badge === 'bronze');
    for (const badge of bronzeBadgeEntries) {
      expect(badge.best_score).toBeGreaterThanOrEqual(2000);
      expect(badge.best_score).toBeLessThan(5000);
    }

    // Validate expected counts
    expect(goldBadges.length).toBe(2);
    expect(silverBadgeEntries.length).toBe(5);
    expect(bronzeBadgeEntries.length).toBe(8);
  }

  // Verify /badges page loaded successfully (not 404 or error)
  expect(page.url()).toContain('/badges');

  // Write diagnostics
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-65/diagnostics.json',
    JSON.stringify({ errors, url: page.url(), badgeCount: badgesData.length }, null, 2)
  );
});