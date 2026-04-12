import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test('Ticket #54 - About page with app version and stats', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Navigate to the about page
  await page.goto('http://127.0.0.1:5000/about');
  await page.waitForLoadState('networkidle');

  // Screenshot of initial page load
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/01-about-page-initial.png',
    fullPage: true
  });

  // Check page title / heading
  const heading = page.locator('h1, h2').filter({ hasText: /about/i }).first();
  const headingVisible = await heading.isVisible().catch(() => false);

  if (headingVisible) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/02-about-heading-visible.png',
      fullPage: true
    });
  }

  // Check for back navigation link
  const backLink = page.locator('a').filter({ hasText: /back to game/i }).first();
  const backLinkVisible = await backLink.isVisible().catch(() => false);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/03-back-link-check.png',
    fullPage: true
  });

  // Check APP INFO section
  const appInfoSection = page.locator('text=/app info/i').first();
  const appInfoVisible = await appInfoSection.isVisible().catch(() => false);

  if (appInfoVisible) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/04-app-info-section.png',
      fullPage: true
    });
  }

  // Check for App Name value
  const appName = page.locator('text=/game score tracker/i').first();
  const appNameVisible = await appName.isVisible().catch(() => false);

  // Check for Version value
  const version = page.locator('text=/1\.0\.0/').first();
  const versionVisible = await version.isVisible().catch(() => false);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/05-app-name-version-check.png',
    fullPage: true
  });

  // Check STATS section
  const statsSection = page.locator('text=/stats/i').first();
  const statsVisible = await statsSection.isVisible().catch(() => false);

  if (statsVisible) {
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/06-stats-section.png',
      fullPage: true
    });
  }

  // Check for Total Unique Players label
  const playersLabel = page.locator('text=/total unique players/i').first();
  const playersLabelVisible = await playersLabel.isVisible().catch(() => false);

  // Check for Total Scores Submitted label
  const scoresLabel = page.locator('text=/total scores submitted/i').first();
  const scoresLabelVisible = await scoresLabel.isVisible().catch(() => false);

  // Check for Total Tournaments Created label
  const tournamentsLabel = page.locator('text=/total tournaments created/i').first();
  const tournamentsLabelVisible = await tournamentsLabel.isVisible().catch(() => false);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/07-stats-labels-check.png',
    fullPage: true
  });

  // Check for stat values (15, 26, 1)
  const bodyText = await page.locator('body').innerText().catch(() => '');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/08-full-page-content.png',
    fullPage: true
  });

  // Now test the /api/about JSON endpoint
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/about');
  const apiStatus = apiResponse.status();

  let apiJson: Record<string, unknown> = {};
  if (apiStatus === 200) {
    try {
      apiJson = await apiResponse.json();
    } catch {
      errors.push('[api/about] Failed to parse JSON response');
    }
  } else {
    errors.push(`[api/about] Unexpected status: ${apiStatus}`);
  }

  // Navigate back to /about to check dark theme styling
  await page.goto('http://127.0.0.1:5000/about');
  await page.waitForLoadState('networkidle');

  // Check dark background color via computed style
  const bgColor = await page.evaluate(() => {
    return window.getComputedStyle(document.body).backgroundColor;
  });

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/09-dark-theme-check.png',
    fullPage: true
  });

  // Check green heading color
  const headingColor = await page.evaluate(() => {
    const h = document.querySelector('h1, h2');
    return h ? window.getComputedStyle(h).color : 'not found';
  });

  // Check section headings color (APP INFO, STATS)
  const sectionHeadingColors = await page.evaluate(() => {
    const headings = Array.from(document.querySelectorAll('h2, h3, th, .section-title'));
    return headings.map(h => ({
      text: h.textContent?.trim(),
      color: window.getComputedStyle(h).color
    }));
  });

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/10-section-headings-style.png',
    fullPage: true
  });

  // Click the back link if visible
  if (backLinkVisible) {
    await backLink.click();
    await page.waitForLoadState('networkidle');
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/11-after-back-navigation.png',
      fullPage: true
    });
    // Navigate back to about page
    await page.goto('http://127.0.0.1:5000/about');
    await page.waitForLoadState('networkidle');
  }

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/12-final-state.png',
    fullPage: true
  });

  // Structural assertions
  expect(page.url()).toContain('/about');
  expect(headingVisible).toBe(true);
  expect(backLinkVisible).toBe(true);
  expect(appInfoVisible).toBe(true);
  expect(appNameVisible).toBe(true);
  expect(versionVisible).toBe(true);
  expect(statsVisible).toBe(true);
  expect(playersLabelVisible).toBe(true);
  expect(scoresLabelVisible).toBe(true);
  expect(tournamentsLabelVisible).toBe(true);
  expect(apiStatus).toBe(200);

  // Assert API JSON structure
  expect(apiJson).toHaveProperty('version', '1.0.0');

  // Assert stat values in body text
  expect(bodyText).toMatch(/15/);
  expect(bodyText).toMatch(/26/);

  // Write diagnostics
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-54/diagnostics.json',
    JSON.stringify(
      {
        errors,
        url: page.url(),
        apiStatus,
        apiJson,
        pageChecks: {
          headingVisible,
          backLinkVisible,
          appInfoVisible,
          appNameVisible,
          versionVisible,
          statsVisible,
          playersLabelVisible,
          scoresLabelVisible,
          tournamentsLabelVisible,
          bgColor,
          headingColor,
          sectionHeadingColors
        }
      },
      null,
      2
    )
  );
});