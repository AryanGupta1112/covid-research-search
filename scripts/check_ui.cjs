const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const out = path.join(process.cwd(), 'artifacts', 'ui');
  fs.mkdirSync(out, { recursive: true });
  let browser;
  try { browser = await chromium.launch({ channel: 'chrome', headless: true }); }
  catch { browser = await chromium.launch({ channel: 'msedge', headless: true }); }
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:5173');
    await page.locator('.result').first().waitFor({ timeout: 120000 });
    await page.getByText('50/50 queries · original qrels').waitFor({ timeout: 120000 });
    await page.locator('.recharts-line-curve').nth(3).waitFor();
    assert.equal(await page.locator('.recharts-line-curve').count(), 4);
    const status = await (await page.request.get('/api/status')).json();
    assert.equal(status.assignmentReady, true);
    assert.equal(status.denseSearchScope, 'all indexed documents');
    const evaluation = await (await page.request.get('/api/evaluation')).json();
    assert.equal(evaluation.evaluatedQueries, evaluation.totalQueries);
    assert.equal(evaluation.precisionRecall[0].recall, 0);
    assert.equal(evaluation.precisionRecall.at(-1).recall, 1);
    assert.match(evaluation.mapScope, /Full returned rankings/);
    for (const [name, width, height] of [
      ['desktop', 1440, 1000], ['wide', 1920, 1080], ['tablet', 768, 1024],
      ['mobile', 390, 844], ['small', 320, 780],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
      const layout = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        searchBottom: document.querySelector('.search-box').getBoundingClientRect().bottom,
        headings: document.querySelectorAll('h1').length,
      }));
      assert.equal(layout.overflow, false, `${name}: page overflow`);
      assert.ok(layout.searchBottom < height, `${name}: search below fold`);
      assert.equal(layout.headings, 1);
      await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: name === 'mobile' });
      console.log(`PASS ${name} layout`);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    for (const name of ['BM25', 'TF-IDF', 'Dense (MiniLM)', 'Hybrid RRF']) {
      const response = page.waitForResponse(r => r.url().endsWith('/api/search') && r.request().method() === 'POST');
      await page.getByRole('button', { name, exact: true }).click();
      const data = await (await response).json();
      assert.equal(data.results.length, 10);
      await page.locator('.result').first().waitFor();
      assert.equal(await page.getByRole('button', { name, exact: true }).getAttribute('aria-pressed'), 'true');
      console.log(`PASS ${name} live retrieval`);
    }
    await page.getByLabel('Number of results').selectOption('20');
    await page.waitForFunction(() => document.querySelectorAll('.result').length === 20);
    console.log('PASS result count');
    const input = page.locator('#search-input');
    await input.fill('neutralizing antibodies vaccine response');
    const submitted = page.waitForResponse(r => r.url().endsWith('/api/search') && r.request().method() === 'POST');
    await input.press('Enter');
    assert.equal((await (await submitted).json()).query, 'neutralizing antibodies vaccine response');
    await page.locator('.result').first().waitFor();
    console.log('PASS keyboard query submission');
    await page.locator('.sample-list button').first().click();
    await page.locator('.result').first().waitFor();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Download scores', exact: true }).click();
    const download = await downloadPromise;
    assert.match(download.suggestedFilename(), /project7-.*-csv\.csv/);
    const csv = await (await page.request.get('/api/evaluation/export?format=csv')).text();
    assert.equal(csv.trim().split(/\r?\n/).length, 5);
    const exported = await (await page.request.get('/api/evaluation/export?format=json')).json();
    assert.equal(exported.experimentId, evaluation.experimentId);
    console.log('PASS CSV and JSON exports');
    await input.fill('x');
    await page.getByRole('button', { name: 'Search papers', exact: true }).click();
    await page.getByText('Enter a research query between 2 and 500 characters.').waitFor();
    console.log('PASS invalid query');
    await page.route('**/api/search', route => route.fulfill({ json: { query: 'empty topic', method: 'hybrid', results: [] } }));
    await input.fill('empty topic');
    await page.getByRole('button', { name: 'Search papers', exact: true }).click();
    await page.getByRole('heading', { name: 'No papers found' }).waitFor();
    console.log('PASS empty results');
    await page.route('**/api/**', route => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }));
    await page.reload();
    await page.getByRole('button', { name: 'Retry connection' }).waitFor();
    await page.getByRole('heading', { name: 'Search is unavailable' }).waitFor();
    await page.unrouteAll();
    await page.getByRole('button', { name: 'Retry connection' }).click();
    await page.getByText('50/50 queries · original qrels').waitFor();
    await page.locator('.result').first().waitFor();
    console.log('PASS service error and retry recovery');
    assert.deepEqual(errors, []);
    console.log('PASS no uncaught browser errors');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
