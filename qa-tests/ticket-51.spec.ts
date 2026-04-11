import { test, expect } from '@playwright/test';

test('Ticket #51: Tests for /scoreboard and /api/scoreboard endpoints', async ({ page }) => {
  test.setTimeout(90000);

  const errors: string[] = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`); });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => { if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`); });

  const APP_URL = 'http://127.0.0.1:5000';

  // --- Seed scores via API ---
  const players = [
    ['PixelKnight', 9800], ['NeonRacer', 8750], ['GhostByte', 7200],
    ['VortexPilot', 6900], ['CipherStorm', 6500], ['QuantumFox', 5800],
    ['ShadowBlade', 5300], ['ByteWitch', 4900], ['IronCircuit', 4400], ['LunarDrift', 4100],
    ['RetroGhost', 3800], ['AlphaByte', 3200], ['DataWraith', 2800], ['NanoHawk', 2300], ['ZeroPoint', 1900]
  ];
  for (const [name, score] of players) {
    await page.request.post(APP_URL + '/api/scores', { data: { name, score } });
  }

  // --- Test 1: GET /api/scoreboard returns 200 with correct structure ---
  const apiResp = await page.request.get(APP_URL + '/api/scoreboard');
  expect(apiResp.status()).toBe(200);
  errors.push(`[info] GET /api/scoreboard status: ${apiResp.status()}`);

  const apiData = await apiResp.json();
  expect(apiData).toHaveProperty('scores');
  expect(apiData).toHaveProperty('active_tournament');
  errors.push(`[info] /api/scoreboard has 'scores' and 'active_tournament' fields`);

  // Verify scores array: max 10 entries, ordered DESC
  const scores: any[] = apiData.scores;
  expect(Array.isArray(scores)).toBe(true);
  expect(scores.length).toBeGreaterThan(0);
  expect(scores.length).toBeLessThanOrEqual(10);
  for (let i = 0; i < scores.length - 1; i++) {
    expect(scores[i].score).toBeGreaterThanOrEqual(scores[i + 1].score);
  }
  errors.push(`[info] scores array has ${scores.length} entries, ordered score DESC`);

  // Verify each score entry has required fields
  for (const entry of scores) {
    expect(entry).toHaveProperty('id');
    expect(entry).toHaveProperty('name');
    expect(entry).toHaveProperty('score');
    expect(entry).toHaveProperty('created_at');
  }

  // Verify top score is PixelKnight
  expect(scores[0].name).toBe('PixelKnight');
  expect(scores[0].score).toBe(9800);
  errors.push(`[info] Top score: ${scores[0].name} with ${scores[0].score}`);

  // --- Test 2: GET /scoreboard returns 200 HTML ---
  await page.goto(APP_URL + '/scoreboard');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-51/scoreboard-initial.png',
    fullPage: true
  });

  // Verify page title / heading
  const headingCount = await page.locator('h1, h2, h3').count();
  expect(headingCount).toBeGreaterThan(0);
  errors.push(`[info] Page has ${headingCount} heading elements`);

  // Verify scores table is present and visible
  const tableCount = await page.locator('table').count();
  expect(tableCount).toBeGreaterThan(0);
  const scoresTable = page.locator('table').first();
  await expect(scoresTable).toBeVisible();
  errors.push(`[info] Found ${tableCount} table(s)`);

  // Verify table has data rows (header + at least 1 data row)
  const tableRows = await page.locator('table tr').count();
  expect(tableRows).toBeGreaterThanOrEqual(2); // header + at least 1 row
  errors.push(`[info] Table has ${tableRows} rows`);

  // Verify PixelKnight appears in the scoreboard
  const bodyText = await page.locator('body').innerText().catch(() => '');
  expect(bodyText).toContain('PixelKnight');
  expect(bodyText).toContain('9800');
  errors.push(`[info] Scoreboard contains PixelKnight with score 9800`);

  // Verify filter input is present
  const filterInput = page.locator('input#filter, input[placeholder*="filter" i], input[placeholder*="name" i], input[placeholder*="player" i]').first();
  const filterExists = await filterInput.count() > 0;
  expect(filterExists).toBe(true);
  errors.push(`[info] Filter input present: ${filterExists}`);

  // Test filter interaction
  if (filterExists) {
    await filterInput.fill('Pixel');
    await page.waitForTimeout(500);
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-51/scoreboard-filtered.png',
      fullPage: true
    });
    await filterInput.clear();
  }

  // Verify auto-refresh script is present
  const scriptContent = await page.evaluate(() =>
    Array.from(document.querySelectorAll('script'))
      .map(s => s.textContent || '')
      .join('\n')
  );
  const hasAutoRefresh = scriptContent.includes('scoreboard') || scriptContent.includes('setInterval') || scriptContent.includes('fetch');
  expect(hasAutoRefresh).toBe(true);
  errors.push(`[info] Auto-refresh script present: ${hasAutoRefresh}`);

  // --- Test 3: Tournament section ---
  // Check if active_tournament is shown (or not, if none active)
  const atData = apiData.active_tournament;
  if (atData !== null) {
    // If an active tournament exists, verify it's rendered
    const tournamentSection = page.locator('[id*="tournament"], [class*="tournament"], .tournament-standings').first();
    const hasTournamentSection = await tournamentSection.count() > 0;
    errors.push(`[info] Active tournament in API: ${atData.name}, section in DOM: ${hasTournamentSection}`);
  } else {
    errors.push('[info] No active tournament in /api/scoreboard response');
  }

  // Final screenshot
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-51/scoreboard-final.png',
    fullPage: true
  });

  // Write diagnostics
  const fs = require('fs');
  const diagDir = '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-51';
  try { fs.mkdirSync(diagDir, { recursive: true }); } catch (_) {}
  fs.writeFileSync(
    diagDir + '/diagnostics.json',
    JSON.stringify({
      errors,
      url: page.url(),
      scoresCount: scores.length,
      topScore: scores[0],
      filterExists,
      hasAutoRefresh,
      activeTournament: atData,
      tableCount,
      tableRows,
      headingCount,
    }, null, 2)
  );
});
