import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #60 - Leaderboard badge system with colored icons and count summary', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // ── 1. /api/badges JSON endpoint ────────────────────────────────────────
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/badges');
  const apiStatus = apiResponse.status();

  let apiJson: Record<string, unknown>[] = [];
  if (apiStatus === 200) {
    try {
      apiJson = await apiResponse.json();
    } catch {
      errors.push('[api/badges] Failed to parse JSON response');
    }
  } else {
    errors.push(`[api/badges] Unexpected status: ${apiStatus}`);
  }

  // ── 2. Navigate to /badges HTML page ────────────────────────────────────
  await page.goto('http://127.0.0.1:5000/badges');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/01-badges-page-initial.png',
    fullPage: true
  });

  // ── 3. Page heading ──────────────────────────────────────────────────────
  const heading = page.locator('h1, h2').filter({ hasText: /badge/i }).first();
  const headingVisible = await heading.isVisible().catch(() => false);

  // ── 4. Back navigation link ──────────────────────────────────────────────
  const backLink = page.locator('a').filter({ hasText: /back to game/i }).first();
  const backLinkVisible = await backLink.isVisible().catch(() => false);

  // ── 5. Badge count summary ───────────────────────────────────────────────
  // Expect "2 Gold", "5 Silver", "8 Bronze" (case-insensitive)
  const bodyText = await page.locator('body').innerText().catch(() => '');

  const goldSummaryVisible = /2\s*gold/i.test(bodyText);
  const silverSummaryVisible = /5\s*silver/i.test(bodyText);
  const bronzeSummaryVisible = /8\s*bronze/i.test(bodyText);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/02-badge-summary.png',
    fullPage: true
  });

  // ── 6. Badge grid cards ──────────────────────────────────────────────────
  const badgeCards = page.locator('.badge-card');
  const badgeCardCount = await badgeCards.count().catch(() => 0);

  // ── 7. Gold badge cards (PixelKnight, NeonRacer) ─────────────────────────
  const goldCards = page.locator('.badge-card.gold');
  const goldCardCount = await goldCards.count().catch(() => 0);

  const pixelKnightVisible = await page.locator('.badge-card.gold').filter({ hasText: /PixelKnight/i }).isVisible().catch(() => false);
  const neonRacerVisible = await page.locator('.badge-card.gold').filter({ hasText: /NeonRacer/i }).isVisible().catch(() => false);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/03-gold-badges.png',
    fullPage: true
  });

  // ── 8. Silver badge cards ─────────────────────────────────────────────────
  const silverCards = page.locator('.badge-card.silver');
  const silverCardCount = await silverCards.count().catch(() => 0);

  // ── 9. Bronze badge cards ─────────────────────────────────────────────────
  const bronzeCards = page.locator('.badge-card.bronze');
  const bronzeCardCount = await bronzeCards.count().catch(() => 0);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/04-badge-grid.png',
    fullPage: true
  });

  // ── 10. Badge icon colors ─────────────────────────────────────────────────
  const goldIconColor = await page.evaluate(() => {
    const icon = document.querySelector('.badge-icon.gold');
    return icon ? window.getComputedStyle(icon).backgroundColor : 'not found';
  });

  const silverIconColor = await page.evaluate(() => {
    const icon = document.querySelector('.badge-icon.silver');
    return icon ? window.getComputedStyle(icon).backgroundColor : 'not found';
  });

  const bronzeIconColor = await page.evaluate(() => {
    const icon = document.querySelector('.badge-icon.bronze');
    return icon ? window.getComputedStyle(icon).backgroundColor : 'not found';
  });

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/05-badge-icon-colors.png',
    fullPage: true
  });

  // ── 11. Dark theme ─────────────────────────────────────────────────────────
  const bgColor = await page.evaluate(() => {
    return window.getComputedStyle(document.body).backgroundColor;
  });

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/06-dark-theme.png',
    fullPage: true
  });

  // ── 12. Final state ───────────────────────────────────────────────────────
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/07-final-state.png',
    fullPage: true
  });

  // ── Write diagnostics ─────────────────────────────────────────────────────
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-60/diagnostics.json',
    JSON.stringify(
      {
        errors,
        url: page.url(),
        apiStatus,
        apiJson,
        pageChecks: {
          headingVisible,
          backLinkVisible,
          goldSummaryVisible,
          silverSummaryVisible,
          bronzeSummaryVisible,
          badgeCardCount,
          goldCardCount,
          silverCardCount,
          bronzeCardCount,
          pixelKnightVisible,
          neonRacerVisible,
          goldIconColor,
          silverIconColor,
          bronzeIconColor,
          bgColor,
        }
      },
      null,
      2
    )
  );

  // ── Assertions ────────────────────────────────────────────────────────────
  // API endpoint
  expect(apiStatus).toBe(200);
  expect(Array.isArray(apiJson)).toBe(true);

  // Page structure
  expect(page.url()).toContain('/badges');
  expect(headingVisible).toBe(true);
  expect(backLinkVisible).toBe(true);

  // Badge count summary
  expect(goldSummaryVisible).toBe(true);
  expect(silverSummaryVisible).toBe(true);
  expect(bronzeSummaryVisible).toBe(true);

  // Badge grid card counts
  expect(goldCardCount).toBe(2);
  expect(silverCardCount).toBe(5);
  expect(bronzeCardCount).toBe(8);
  expect(badgeCardCount).toBe(15);

  // Specific gold players
  expect(pixelKnightVisible).toBe(true);
  expect(neonRacerVisible).toBe(true);

  // Badge icon colors — gold=#FFD700, silver=#C0C0C0, bronze=#CD7F32
  // Browsers render hex as rgb(); accept both rgb and original hex forms
  expect(goldIconColor).toMatch(/rgb\(255,\s*215,\s*0\)|#FFD700/i);
  expect(silverIconColor).toMatch(/rgb\(192,\s*192,\s*192\)|#C0C0C0/i);
  expect(bronzeIconColor).toMatch(/rgb\(205,\s*127,\s*50\)|#CD7F32/i);

  // Dark theme: body background should be dark (not white)
  expect(bgColor).not.toBe('rgb(255, 255, 255)');
  expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
});
