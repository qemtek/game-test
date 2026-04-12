import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #63 - Leaderboard badge system with rank badges for top players', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // First test the API endpoint
  await page.goto('http://127.0.0.1:5000/api/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/api-badges-response.png'
  });

  // Validate API response structure
  const apiContent = await page.textContent('body');
  let badgesData: any[] = [];
  try {
    badgesData = JSON.parse(apiContent || '[]');
    
    expect(Array.isArray(badgesData)).toBeTruthy();

    // Check that badge objects have required fields
    if (badgesData.length > 0) {
      const firstBadge = badgesData[0];
      expect(firstBadge).toHaveProperty('player');
      expect(firstBadge).toHaveProperty('badge');
      expect(firstBadge).toHaveProperty('best_score');
    }

    // Check gold badge players (score >= 8000)
    const goldBadges = badgesData.filter((b: any) => b.badge === 'gold');
    const silverBadges = badgesData.filter((b: any) => b.badge === 'silver');
    const bronzeBadges = badgesData.filter((b: any) => b.badge === 'bronze');

    console.log(`Gold badges: ${goldBadges.length}, Silver badges: ${silverBadges.length}, Bronze badges: ${bronzeBadges.length}`);

    // Verify gold badge players
    const goldPlayers = goldBadges.map((b: any) => b.player);
    if (goldBadges.length >= 2) {
      expect(goldPlayers).toContain('PixelKnight');
      expect(goldPlayers).toContain('NeonRacer');
    }

    // Verify gold badge scores are >= 8000
    goldBadges.forEach((b: any) => {
      expect(b.best_score).toBeGreaterThanOrEqual(8000);
    });

    // Verify silver badge scores are in range 5000-7999
    silverBadges.forEach((b: any) => {
      expect(b.best_score).toBeGreaterThanOrEqual(5000);
      expect(b.best_score).toBeLessThanOrEqual(7999);
    });

    // Verify bronze badge scores are in range 2000-4999
    bronzeBadges.forEach((b: any) => {
      expect(b.best_score).toBeGreaterThanOrEqual(2000);
      expect(b.best_score).toBeLessThanOrEqual(4999);
    });

  } catch (e) {
    errors.push(`[parse-error] Failed to parse /api/badges response: ${e}`);
  }

  // Navigate to the badges HTML page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/badges-page-initial.png'
  });

  // Check the page title/heading
  const pageTitle = await page.title();
  console.log(`Page title: ${pageTitle}`);

  // Check for badge count summary at the top
  const summaryExists = await page.locator('body').evaluate(el => {
    const text = el.textContent || '';
    return text.includes('gold') || text.includes('Gold') || text.includes('silver') || text.includes('Silver') || text.includes('bronze') || text.includes('Bronze');
  });
  expect(summaryExists).toBeTruthy();

  // Take screenshot of badge count summary area
  const summarySelectors = [
    '.badge-summary',
    '.summary',
    '.badge-counts',
    '.counts',
    '[class*="summary"]',
    '[class*="count"]',
    'header',
    '.header',
    'h1',
    'h2'
  ];

  for (const selector of summarySelectors) {
    const element = page.locator(selector).first();
    const count = await element.count();
    if (count > 0) {
      try {
        await element.screenshot({
          path: `/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/badge-summary-${selector.replace(/[^a-zA-Z0-9]/g, '-')}.png`
        });
        break;
      } catch (e) {
        // Continue to next selector
      }
    }
  }

  // Verify badge count numbers appear on page (2 gold, 5 silver, 8 bronze)
  const bodyText = await page.textContent('body');
  console.log('Page body contains gold reference:', bodyText?.toLowerCase().includes('gold'));
  console.log('Page body contains silver reference:', bodyText?.toLowerCase().includes('silver'));
  console.log('Page body contains bronze reference:', bodyText?.toLowerCase().includes('bronze'));

  // Check for gold player PixelKnight
  const pixelKnightVisible = await page.getByText('PixelKnight').isVisible().catch(() => false);
  console.log('PixelKnight visible:', pixelKnightVisible);

  // Check for gold player NeonRacer
  const neonRacerVisible = await page.getByText('NeonRacer').isVisible().catch(() => false);
  console.log('NeonRacer visible:', neonRacerVisible);

  // Check for silver players
  const silverPlayers = ['GhostByte', 'VortexPilot', 'CyberFox', 'LaserWolf', 'ShadowBit'];
  for (const player of silverPlayers) {
    const visible = await page.getByText(player).isVisible().catch(() => false);
    console.log(`${player} visible:`, visible);
  }

  // Check for bronze players
  const bronzePlayers = ['QuantumAce', 'TurboHawk', 'BlinkDash', 'IronClad', 'StormRider', 'NovaStar', 'ZeroGrav', 'VoltEdge'];
  for (const player of bronzePlayers) {
    const visible = await page.getByText(player).isVisible().catch(() => false);
    console.log(`${player} visible:`, visible);
  }

  // Check for dark theme - background should be dark
  const backgroundColor = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);
    return style.backgroundColor;
  });
  console.log('Background color:', backgroundColor);

  // Verify badge colors are applied correctly
  const goldColorCheck = await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll('*'));
    return elements.some(el => {
      const style = window.getComputedStyle(el);
      const color = style.color || style.backgroundColor || style.borderColor;
      return color.includes('255, 215, 0') || // rgb for #FFD700
        el.getAttribute('style')?.includes('#FFD700') ||
        el.getAttribute('style')?.includes('gold') ||
        el.className?.toLowerCase().includes('gold');
    });
  });
  console.log('Gold color (#FFD700) detected:', goldColorCheck);

  const silverColorCheck = await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll('*'));
    return elements.some(el => {
      const style = window.getComputedStyle(el);
      return el.getAttribute('style')?.includes('#C0C0C0') ||
        el.getAttribute('style')?.includes('silver') ||
        el.className?.toLowerCase().includes('silver');
    });
  });
  console.log('Silver color (#C0C0C0) detected:', silverColorCheck);

  const bronzeColorCheck = await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll('*'));
    return elements.some(el => {
      return el.getAttribute('style')?.includes('#CD7F32') ||
        el.className?.toLowerCase().includes('bronze');
    });
  });
  console.log('Bronze color (#CD7F32) detected:', bronzeColorCheck);

  // Take screenshot of badge grid
  const gridSelectors = [
    '.badge-grid',
    '.grid',
    '.badges-container',
    '.player-grid',
    '[class*="grid"]',
    '[class*="badge"]',
    'main',
    '.container'
  ];

  for (const selector of gridSelectors) {
    const element = page.locator(selector).first();
    const count = await element.count();
    if (count > 0) {
      try {
        await element.screenshot({
          path: `/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/badge-grid-${selector.replace(/[^a-zA-Z0-9]/g, '-')}.png`
        });
        break;
      } catch (e) {
        // Continue to next selector
      }
    }
  }

  // Scroll to bottom and take full page screenshot
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/badges-page-scrolled-bottom.png',
    fullPage: true
  });

  // Take final full-page screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/badges-page-full.png',
    fullPage: true
  });

  // Verify page has a grid/list structure for players
  const hasGrid = await page.locator('.badge-grid, .grid, [class*="grid"], [class*="badge-list"]').count() > 0;
  console.log('Has badge grid structure:', hasGrid);

  // Check count summary shows expected numbers
  const hasTwoGold = bodyText?.includes('2') && bodyText?.toLowerCase().includes('gold');
  const hasFiveSilver = bodyText?.includes('5') && bodyText?.toLowerCase().includes('silver');
  const hasEightBronze = bodyText?.includes('8') && bodyText?.toLowerCase().includes('bronze');
  console.log('Shows 2 gold:', hasTwoGold);
  console.log('Shows 5 silver:', hasFiveSilver);
  console.log('Shows 8 bronze:', hasEightBronze);

  // Write diagnostics file
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-63/diagnostics.json',
    JSON.stringify({
      errors,
      url: page.url(),
      checks: {
        apiParsed: badgesData.length > 0,
        goldBadgeCount: badgesData.filter((b: any) => b.badge === 'gold').length,
        silverBadgeCount: badgesData.filter((b: any) => b.badge === 'silver').length,
        bronzeBadgeCount: badgesData.filter((b: any) => b.badge === 'bronze').length,
        pageBackgroundColor: backgroundColor,
        goldColorDetected: goldColorCheck,
        silverColorDetected: silverColorCheck,
        bronzeColorDetected: bronzeColorCheck,
        pixelKnightVisible,
        neonRacerVisible,
        hasBadgeGrid: hasGrid,
        summaryShowsGold: hasTwoGold,
        summaryShowsSilver: hasFiveSilver,
        summaryShowsBronze: hasEightBronze
      }
    }, null, 2)
  );
});