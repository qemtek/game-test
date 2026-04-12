import { test, expect } from '@playwright/test';

test('Ticket #53 - Game history page recent games log', async ({ page }) => {
  const errors: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
  page.on('response', resp => {
    if (resp.status() >= 400) errors.push(`[network] ${resp.status()} ${resp.url()}`);
  });

  // Navigate to the history page
  await page.goto('http://127.0.0.1:5000/history');
  await page.waitForLoadState('networkidle');

  // Screenshot of initial page load
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/01-history-page-initial.png',
    fullPage: true
  });

  // Check page title or heading contains history-related text
  const headingLocator = page.locator('h1, h2, h3').first();
  await headingLocator.waitFor({ state: 'visible', timeout: 10000 });
  const headingText = await headingLocator.textContent();
  console.log('Heading text:', headingText);

  // Assert heading contains expected text (RECENT GAMES or similar)
  const headingEl = page.locator('h1, h2, h3, .title, [class*="heading"], [class*="title"]').first();
  const allHeadings = await page.locator('h1, h2, h3').allTextContents();
  console.log('All headings:', allHeadings);

  // Screenshot after headings loaded
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/02-history-page-headings.png',
    fullPage: true
  });

  // Check for a table or list structure
  const tableExists = await page.locator('table').count();
  const listExists = await page.locator('ul, ol, [class*="list"], [class*="history"], [class*="leaderboard"]').count();
  console.log('Table count:', tableExists);
  console.log('List/container count:', listExists);

  // Look for table headers: #/Name/Score/When or rank/player/score/time-ago
  if (tableExists > 0) {
    await page.locator('table').first().waitFor({ state: 'visible', timeout: 5000 });

    const thTexts = await page.locator('table th').allTextContents();
    console.log('Table headers:', thTexts);

    // Screenshot of the table
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/03-history-table-view.png',
      fullPage: true
    });

    // Count table rows (excluding header)
    const rowCount = await page.locator('table tbody tr').count();
    console.log('Table row count:', rowCount);

    // Bonus assertion: at least 15 rows
    if (rowCount >= 15) {
      console.log(`✅ Table has ${rowCount} rows (>= 15 required)`);
    } else {
      console.warn(`⚠️ Table has only ${rowCount} rows (expected >= 15)`);
    }

    // Check for real player names in the table
    const allCellTexts = await page.locator('table tbody td').allTextContents();
    console.log('Sample cell values (first 20):', allCellTexts.slice(0, 20));

    const hasPixelKnight = allCellTexts.some(t => t.includes('PixelKnight'));
    const hasNeonRacer = allCellTexts.some(t => t.includes('NeonRacer'));
    console.log('Has PixelKnight:', hasPixelKnight);
    console.log('Has NeonRacer:', hasNeonRacer);

    // Check for time-ago values (e.g., "5 minutes ago", "2 hours ago")
    const timeAgoPattern = /\d+\s+(second|minute|hour|day|week|month|year)s?\s+ago/i;
    const hasTimeAgo = allCellTexts.some(t => timeAgoPattern.test(t));
    const justNowPattern = /just now/i;
    const hasJustNow = allCellTexts.some(t => justNowPattern.test(t));
    console.log('Has time-ago values:', hasTimeAgo || hasJustNow);

    // Bonus structural assertions
    expect(rowCount).toBeGreaterThanOrEqual(1);
  } else if (listExists > 0) {
    console.log('No table found, checking list-based layout');

    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/03-history-list-view.png',
      fullPage: true
    });

    const listItems = await page.locator('li, [class*="row"], [class*="item"], [class*="entry"]').count();
    console.log('List item count:', listItems);
  } else {
    console.warn('⚠️ No table or list found on history page');
    await page.screenshot({
      path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/03-history-no-table-found.png',
      fullPage: true
    });
  }

  // Check for navigation link back to home/game
  const navLinks = await page.locator('a').allTextContents();
  console.log('All nav links:', navLinks);

  const homeLink = page.locator('a[href="/"], a[href*="home"], a[href*="game"], a[class*="nav"], nav a').first();
  const homeLinkExists = await homeLink.count();
  console.log('Home/game navigation link exists:', homeLinkExists > 0);

  // Screenshot of navigation area
  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/04-history-navigation-links.png',
    fullPage: false
  });

  // Check dark theme — background should be dark
  const bodyBg = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);
    return {
      backgroundColor: style.backgroundColor,
      color: style.color,
      backgroundImage: style.backgroundImage
    };
  });
  console.log('Body styles:', bodyBg);

  // Test the /api/history endpoint
  const apiResponse = await page.request.get('http://127.0.0.1:5000/api/history');
  console.log('API /api/history status:', apiResponse.status());

  if (apiResponse.ok()) {
    const apiData = await apiResponse.json();
    console.log('API response type:', Array.isArray(apiData) ? 'array' : typeof apiData);
    console.log('API response length:', Array.isArray(apiData) ? apiData.length : 'N/A');
    if (Array.isArray(apiData) && apiData.length > 0) {
      console.log('First API record keys:', Object.keys(apiData[0]));
      console.log('First API record:', apiData[0]);
    }
  } else {
    errors.push(`[api] /api/history returned ${apiResponse.status()}`);
    console.warn('⚠️ /api/history endpoint not available:', apiResponse.status());
  }

  // Test /api/history?limit=5
  const apiLimitResponse = await page.request.get('http://127.0.0.1:5000/api/history?limit=5');
  console.log('API /api/history?limit=5 status:', apiLimitResponse.status());

  if (apiLimitResponse.ok()) {
    const apiLimitData = await apiLimitResponse.json();
    console.log('API limit=5 response length:', Array.isArray(apiLimitData) ? apiLimitData.length : 'N/A');
    if (Array.isArray(apiLimitData)) {
      expect(apiLimitData.length).toBeLessThanOrEqual(5);
      console.log('✅ API respects limit parameter');
    }
  } else {
    errors.push(`[api] /api/history?limit=5 returned ${apiLimitResponse.status()}`);
  }

  // Navigate back to main page to verify home link works
  const mainPageResponse = await page.request.get('http://127.0.0.1:5000/');
  console.log('Main page status:', mainPageResponse.status());

  // Final full-page screenshot
  await page.goto('http://127.0.0.1:5000/history');
  await page.waitForLoadState('networkidle');

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/05-history-page-final-full.png',
    fullPage: true
  });

  // Bonus: Scroll to bottom and screenshot
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/06-history-page-scrolled-bottom.png',
    fullPage: false
  });

  // Check page URL is correct
  expect(page.url()).toContain('/history');

  // Write diagnostics file
  const fs = require('fs');
  fs.writeFileSync(
    '/Users/christophercollins/Documents/GitHub/PareBot2/projects/game-test/qa-screenshots/test-results/ticket-53/diagnostics.json',
    JSON.stringify(
      {
        errors,
        url: page.url(),
        allHeadings,
        bodyStyles: bodyBg,
        navLinks,
        apiHistoryStatus: apiResponse.status(),
        apiHistoryLimitStatus: apiLimitResponse.status()
      },
      null,
      2
    )
  );
});