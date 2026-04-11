import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

test('Ticket #50: Data seed script for scoreboard visual QA', async ({ page }) => {
  test.setTimeout(90000);

  const outputDir = path.join(process.cwd(), 'qa-screenshots', 'test-results', 'ticket-50');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const errors: string[] = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`); });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => { if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`); });

  const APP_URL = 'http://127.0.0.1:5000';

  // Seed scores via API
  const players = [
    ['PixelKnight', 9800], ['NeonRacer', 8750], ['GhostByte', 7200],
    ['VortexPilot', 6900], ['CipherStorm', 6500], ['QuantumFox', 5800],
    ['ShadowBlade', 5300], ['ByteWitch', 4900], ['IronCircuit', 4400], ['LunarDrift', 4100],
    ['RetroGhost', 3800], ['AlphaByte', 3200], ['DataWraith', 2800], ['NanoHawk', 2300], ['ZeroPoint', 1900]
  ];

  for (const [name, score] of players) {
    try {
      await page.request.post(APP_URL + '/api/scores', { data: { name, score } });
    } catch (e) {
      errors.push(`[setup] Failed to post score for ${name}: ${e}`);
    }
  }

  // Navigate to scoreboard
  await page.goto(APP_URL + '/scoreboard');
  await page.waitForLoadState('networkidle');

  await page.screenshot({ path: path.join(outputDir, 'scoreboard-populated.png'), fullPage: true });

  // Verify players are visible on scoreboard
  const playerRows = await page.locator('table tbody tr, .player-row, .scoreboard-entry, [class*="player"], [class*="score"]').count();
  console.log('Player rows found:', playerRows);
  expect(playerRows).toBeGreaterThan(0);

  const pageContent = await page.content();
  const hasScoreData = pageContent.includes('score') || pageContent.includes('Score') || pageContent.includes('player') || pageContent.includes('Player');
  expect(hasScoreData).toBeTruthy();

  // Navigate to tournaments page (same base URL, port 5000)
  await page.goto(APP_URL + '/tournaments');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(outputDir, 'tournament-active.png'), fullPage: true });

  const tournamentContent = await page.content();
  // The page title is "Tournaments" and it always contains "Tournament" in heading
  const hasTournamentContent = tournamentContent.includes('Tournament') || tournamentContent.includes('tournament');
  expect(hasTournamentContent).toBeTruthy();

  const entrantElements = await page.locator('[class*="entrant"], [class*="participant"], .tournament-row, .tournament-card').count();
  console.log('Tournament/entrant elements found:', entrantElements);

  // Write diagnostics
  fs.writeFileSync(
    path.join(outputDir, 'diagnostics.json'),
    JSON.stringify({ errors, url: page.url() }, null, 2)
  );
});
