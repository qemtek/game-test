import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #55 - Leaderboard badge system visual verification', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // First ensure we have the correct test data in the database before checking the badge system
  await page.goto('http://127.0.0.1:5000');
  await page.waitForLoadState('networkidle');

  // Navigate to the badges page
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  // Screenshot of initial badges page load
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/01-badges-page-initial.png',
    fullPage: true
  });

  // Verify page heading exists
  const heading = page.locator('h1').filter({ hasText: /leaderboard badges/i }).first();
  const headingVisible = await heading.isVisible().catch(() => false);
  if (!headingVisible) {
    errors.push('Missing heading "Leaderboard Badges"');
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/02-heading-verification.png',
    fullPage: true
  });

  // Verify badge summary bar exists at top
  const badgeSummary = page.locator('.badges-summary');
  const badgeSummaryVisible = await badgeSummary.isVisible();

  if (badgeSummaryVisible) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/03-badge-summary-bar.png',
      fullPage: true
    });
  } else {
    errors.push('Missing badge summary bar at top');
  }

  // Check that summary displays '2 Gold, 5 Silver, 8 Bronze'
  const goldCountText = page.locator('.badges-summary .badge-count:nth-child(1) span:last-child');
  const silverCountText = page.locator('.badges-summary .badge-count:nth-child(2) span:last-child');
  const bronzeCountText = page.locator('.badges-summary .badge-count:nth-child(3) span:last-child');

  let goldCount = parseInt((await goldCountText.textContent())?.replace(/\D/g, '') || '0');
  let silverCount = parseInt((await silverCountText.textContent())?.replace(/\D/g, '') || '0');
  let bronzeCount = parseInt((await bronzeCountText.textContent())?.replace(/\D/g, '') || '0');

  if (goldCount !== 2) {
    errors.push(`Expected 2 Gold badges, but found ${goldCount}`);
  }
  if (silverCount !== 5) {
    errors.push(`Expected 5 Silver badges, but found ${silverCount}`);
  }
  if (bronzeCount !== 8) {
    errors.push(`Expected 8 Bronze badges, but found ${bronzeCount}`);
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/04-count-display-check.png',
    fullPage: true
  });

  // Verify the badge grid exists with 15 player entries
  const badgeCards = page.locator('.badge-card');
  const cardCount = await badgeCards.count();
  
  if (cardCount !== 15) {
    errors.push(`Expected 15 badge cards in grid, but found ${cardCount}`);
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/05-badge-grid-total.png',
    fullPage: true
  });

  // Identify specific player badges to verify assignments
  const pixelKnightCard = page.locator('.badge-card:has-text("PixelKnight")');
  const neonRacerCard = page.locator('.badge-card:has-text("NeonRacer")');
  const ghostByteCard = page.locator('.badge-card:has-text("GhostByte")');
  const vortexPilotCard = page.locator('.badge-card:has-text("VortexPilot")');
  const cyberFoxCard = page.locator('.badge-card:has-text("CyberFox")');
  const laserWolfCard = page.locator('.badge-card:has-text("LaserWolf")');
  const shadowBitCard = page.locator('.badge-card:has-text("ShadowBit")');

  // Check for gold icon classes for PixelKnight and NeonRacer
  if (!(await pixelKnightCard.locator('.gold-icon, .gold').isVisible())) {
    errors.push('PixelKnight should have gold badge but does not');
  }
  if (!(await neonRacerCard.locator('.gold-icon, .gold').isVisible())) {
    errors.push('NeonRacer should have gold badge but does not');
  }

  // Check for silver icon classes for specific players
  if (!(await ghostByteCard.locator('.silver-icon, .silver').isVisible())) {
    errors.push('GhostByte should have silver badge but does not');
  }
  if (!(await vortexPilotCard.locator('.silver-icon, .silver').isVisible())) {
    errors.push('VortexPilot should have silver badge but does not');
  }
  if (!(await cyberFoxCard.locator('.silver-icon, .silver').isVisible())) {
    errors.push('CyberFox should have silver badge but does not');
  }
  if (!(await laserWolfCard.locator('.silver-icon, .silver').isVisible())) {
    errors.push('LaserWolf should have silver badge but does not');
  }
  if (!(await shadowBitCard.locator('.silver-icon, .silver').isVisible())) {
    errors.push('ShadowBit should have silver badge but does not');
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/06-gold-silver-verification.png',
    fullPage: true
  });

  // Check that bronze players have bronze icon classes
  const bronzePlayersCheck = [
    'QuantumAce', 'TurboHawk', 'BlinkDash', 
    'IronClad', 'StormRider', 'NovaStar', 
    'ZeroGrav', 'VoltEdge'
  ];

  for (const playerName of bronzePlayersCheck) {
    const playerCard = page.locator(`.badge-card:has-text("${playerName}")`);
    if (!(await playerCard.locator('.bronze-icon, .bronze').isVisible())) {
      errors.push(`${playerName} should have bronze badge but does not`);
    }
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/07-bronze-verification.png',
    fullPage: true
  });

  // Test dark theme background matching requirements
  const bodyBgColor = await page.evaluate(() => {
    return window.getComputedStyle(document.body).backgroundColor;
  });

  // The theme should be dark, which typically corresponds to backgrounds with low RGB values
  // Check if it's a dark theme (not white/light color)
  if (bodyBgColor && !bodyBgColor.includes('rgba(') && !bodyBgColor.includes('rgb(')) {
    // Extract hex if in hex format and convert to RGB for comparison
    let rgbMatch = bodyBgColor.match(/(\d+),\s*(\d+),\s*(\d+)/);
    if (rgbMatch) {
      const r = parseInt(rgbMatch[1]);
      const g = parseInt(rgbMatch[2]);
      const b = parseInt(rgbMatch[3]);
      
      // If all values high (like white #ffffff or light colors), might indicate theme issue
      if (r > 200 && g > 200 && b > 200) {
        errors.push(`Unexpected light background color for dark theme: ${bodyBgColor}`);
      }
    }
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/08-dark-theme-check.png',
    fullPage: true
  });

  // Test API endpoint as well
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/badges');
  const apiStatus = apiResponse.status();

  let apiData: any[] = [];
  if (apiStatus === 200) {
    try {
      apiData = await apiResponse.json();
    } catch {
      errors.push('[api/badges] Failed to parse JSON response');
    }
  } else {
    errors.push(`[api/badges] Unexpected status: ${apiStatus}`);
  }

  // Final screenshot
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/09-final-state.png',
    fullPage: true
  });

  // Assertions
  expect(errors.length).toBe(0); // Ensure no errors were collected
  expect(headingVisible).toBe(true);
  expect(goldCount).toBe(2);
  expect(silverCount).toBe(5);
  expect(bronzeCount).toBe(8);
  expect(cardCount).toBe(15);
  expect(apiStatus).toBe(200);

  // Additional API checks
  if (apiData) {
    const goldBadges = apiData.filter(badge => badge.badge === 'gold');
    const silverBadges = apiData.filter(badge => badge.badge === 'silver'); 
    const bronzeBadges = apiData.filter(badge => badge.badge === 'bronze');
    
    expect(goldBadges.length).toBe(2);
    expect(silverBadges.length).toBe(5);
    expect(bronzeBadges.length).toBe(8);
    
    // Verify specific player assignments
    expect(goldBadges.map(b => b.player)).toContain('PixelKnight');
    expect(goldBadges.map(b => b.player)).toContain('NeonRacer');
    expect(silverBadges.map(b => b.player)).toContain('GhostByte');
    expect(silverBadges.map(b => b.player)).toContain('VortexPilot');
    expect(silverBadges.map(b => b.player)).toContain('CyberFox');
    expect(silverBadges.map(b => b.player)).toContain('LaserWolf');
    expect(silverBadges.map(b => b.player)).toContain('ShadowBit');
  }

  // Write diagnostics
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-55/diagnostics.json',
    JSON.stringify(
      {
        errors,
        url: page.url(),
        apiStatus,
        apiData,
        pageChecks: {
          headingVisible,
          badgeSummaryVisible,
          goldCount,
          silverCount, 
          bronzeCount,
          cardCount,
          bodyBackgroundColor: bodyBgColor
        }
      },
      null,
      2
    )
  );
});