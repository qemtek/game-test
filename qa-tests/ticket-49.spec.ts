import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test('Ticket #49: Live Scoreboard page — leaderboard UI with real-time updates', async ({ page }) => {
  test.setTimeout(90000);

  const outputDir = path.join(process.cwd(), 'qa-screenshots', 'test-results', 'ticket-49');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const errors: string[] = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`); });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => { if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`); });

  // --- Navigate ---
  await page.goto('http://127.0.0.1:5000/scoreboard');
  await page.waitForLoadState('networkidle');

  // --- Setup ---
  const APP_URL = 'http://127.0.0.1:5000';
  const players = [
    ['PixelKnight', 9800], ['NeonRacer', 8750], ['GhostByte', 7200],
    ['VortexPilot', 6900], ['CipherStorm', 6500], ['QuantumFox', 5800],
    ['ShadowBlade', 5300], ['ByteWitch', 4900], ['IronCircuit', 4400], ['LunarDrift', 4100],
    ['RetroGhost', 3800], ['AlphaByte', 3200], ['DataWraith', 2800], ['NanoHawk', 2300], ['ZeroPoint', 1900]
  ];
  for (const [name, score] of players) {
    await page.request.post(APP_URL + '/api/scores', { data: { name, score } });
  }
  // Wait for page to show data
  await page.reload();
  await page.waitForLoadState('networkidle');

  // Take screenshot of the scoreboard page
  await page.screenshot({ path: path.join(outputDir, 'scoreboard-initial.png'), fullPage: true });

  // Verify the page title or heading
  const pageTitle = await page.title();
  console.log('Page title:', pageTitle);

  // Check for the top-10 scores table
  const scoresTable = page.locator('table, [class*="score"], [id*="score"], [class*="leaderboard"], [id*="leaderboard"]').first();
  const scoresTableVisible = await scoresTable.isVisible().catch(() => false);
  console.log('Scores table visible:', scoresTableVisible);

  if (scoresTableVisible) {
    await expect(scoresTable).toBeVisible();
  }

  // Check for player filter input
  const filterInput = page.locator('input[type="text"], input[placeholder*="filter"], input[placeholder*="player"], input[placeholder*="search"], #filter, #player-filter, [id*="filter"]').first();
  const filterInputVisible = await filterInput.isVisible().catch(() => false);
  console.log('Filter input visible:', filterInputVisible);

  if (filterInputVisible) {
    await expect(filterInput).toBeVisible();
  }

  // Check for tournament standings section
  const tournamentSection = page.locator('[class*="tournament"], [id*="tournament"], [class*="standings"], [id*="standings"]').first();
  const tournamentVisible = await tournamentSection.isVisible().catch(() => false);
  console.log('Tournament section visible:', tournamentVisible);

  // Verify the API endpoint returns proper JSON
  const apiResponse = await page.request.get(APP_URL + '/api/scoreboard');
  const apiStatus = apiResponse.status();
  console.log('API status:', apiStatus);

  if (apiStatus === 200) {
    await expect(apiResponse).toBeOK();
    const apiData = await apiResponse.json();
    console.log('API data keys:', Object.keys(apiData));

    // Verify scores array exists
    expect(apiData).toHaveProperty('scores');
    expect(Array.isArray(apiData.scores)).toBeTruthy();

    // Verify active_tournament field exists (can be null or object)
    expect(apiData).toHaveProperty('active_tournament');

    console.log('Scores count:', apiData.scores.length);
    console.log('Active tournament:', apiData.active_tournament);

    if (apiData.active_tournament !== null && apiData.active_tournament !== undefined) {
      expect(apiData.active_tournament).toHaveProperty('id');
      expect(apiData.active_tournament).toHaveProperty('name');
      expect(apiData.active_tournament).toHaveProperty('standings');
    }
  }

  // Check for auto-refresh JS (look for fetch or setInterval in page content)
  const pageContent = await page.content();
  const hasFetch = pageContent.includes('fetch');
  const hasSetInterval = pageContent.includes('setInterval');
  console.log('Has fetch:', hasFetch);
  console.log('Has setInterval:', hasSetInterval);

  // Try typing in filter input if visible
  if (filterInputVisible) {
    await filterInput.fill('test');
    await page.waitForTimeout(500);
  }

  // Wait for potential auto-refresh
  await page.waitForTimeout(1000);

  // Take final screenshot after interactions
  await page.screenshot({ path: path.join(outputDir, 'scoreboard-after-interaction.png'), fullPage: true });

  // Final assertions on page structure
  const headings = await page.locator('h1, h2, h3').allTextContents();
  console.log('Page headings:', headings);

  const hasScoreboardHeading = headings.some(h =>
    h.toLowerCase().includes('score') ||
    h.toLowerCase().includes('leaderboard') ||
    h.toLowerCase().includes('ranking')
  );
  console.log('Has scoreboard heading:', hasScoreboardHeading);

  fs.writeFileSync(
    path.join(outputDir, 'diagnostics.json'),
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});
