const { expect } = require('@playwright/test');
const { test } = require('./fixtures.cjs');

const open = async (page, url) => {
  const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
  expect(response.status(), url).toBe(200);
  await expect(page.locator('main h1')).toBeVisible();
};

async function capture(page, testInfo, name) {
  const path = testInfo.outputPath(name + '.png');
  await page.screenshot({ path, animations: 'disabled', timeout: 7000 });
  await testInfo.attach(name, { path, contentType: 'image/png' });
}

async function documentWidth(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const main = document.querySelector('main').getBoundingClientRect();
    return { client: root.clientWidth, scroll: root.scrollWidth, left: main.left, right: main.right };
  });
}

test('LAY-01 | Сетка, блоки, изображение и текст @compat', async ({ page, newPart }, info) => {
  await open(page, '/');
  const image = page.locator('.brand img');
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
  await expect(page.locator('.brand .slogan')).toBeVisible();
  const header = await page.locator('.site-header').boundingBox();
  const layout = await page.locator('main').boundingBox();
  const footer = await page.locator('.site-footer').boundingBox();
  expect.soft(header.y + header.height).toBeLessThanOrEqual(layout.y);
  expect.soft(layout.y + layout.height).toBeLessThanOrEqual(footer.y + 2);
  await capture(page, info, 'home');
  await open(page, '/parts/' + newPart.id + '/');
  const photo = page.locator('main img').first();
  await expect(photo).toBeVisible();
  await expect.poll(() => photo.evaluate(img => img.naturalWidth)).toBeGreaterThan(0);
  const overlap = await page.evaluate(() => {
    const img = document.querySelector('main img').getBoundingClientRect();
    const title = document.querySelector('main h1').getBoundingClientRect();
    return Math.min(img.right, title.right) > Math.max(img.left, title.left)
      && Math.min(img.bottom, title.bottom) > Math.max(img.top, title.top);
  });
  expect(overlap).toBe(false);
  await capture(page, info, 'part');
});

test('LAY-02 | Адаптивность по ширине и масштабу @compat', async ({ page }, info) => {
  const mobile = info.project.name === 'Chrome-mobile';
  const widths = mobile ? [393, 360] : [1440, 1024, 768, 390];
  const checks = [];
  await open(page, '/parts/');
  for (const width of widths) {
    await page.setViewportSize({ width, height: 950 });
    const dimensions = await documentWidth(page);
    checks.push({ width, zoom: 100, ...dimensions });
    expect.soft(dimensions.scroll, 'Ширина ' + width).toBeLessThanOrEqual(dimensions.client + 2);
    await capture(page, info, 'width-' + width);
  }
  await page.setViewportSize({ width: mobile ? 393 : 1024, height: 950 });
  for (const zoom of [125, 200]) {
    await page.evaluate(zoom => { document.documentElement.style.zoom = zoom / 100; }, zoom);
    const dimensions = await documentWidth(page);
    checks.push({ width: mobile ? 393 : 1024, zoom, ...dimensions });
    expect.soft(dimensions.scroll, 'Масштаб ' + zoom + '%').toBeLessThanOrEqual(dimensions.client + 2);
    await capture(page, info, 'zoom-' + zoom);
  }
  await info.attach('metrics', { body: JSON.stringify(checks, null, 2), contentType: 'application/json' });
});

test('LAY-03 | Ссылки, кнопки, фокус, hover, логотип и favicon @compat', async ({ page, newPart }, info) => {
  await open(page, '/parts/' + newPart.id + '/');
  const search = page.locator('#header-search-input');
  await search.click();
  await expect(search).toBeFocused();
  const link = page.locator('nav.nav-horizontal a[href="/parts/"]');
  if (info.project.name !== 'Chrome-mobile') {
    const style = () => link.evaluate(el => {
      const css = getComputedStyle(el);
      return [css.color, css.backgroundColor, css.textDecorationLine].join(' ');
    });
    const before = await style();
    await link.hover();
    await expect.poll(style).not.toBe(before);
  } else {
    expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
  }
  await link.click();
  await expect(page).toHaveURL(/\/parts\/$/);
  const favicon = await page.locator('link[rel~="icon"]').first().getAttribute('href');
  expect(favicon).toBeTruthy();
  expect((await page.request.get(favicon)).status()).toBe(200);
  await page.locator('.brand a').click();
  await expect(page).toHaveURL(/\/$/);
  await open(page, '/parts/' + newPart.id + '/');
  await page.locator('form[action*="/cart/add/"] button').click();
  await expect(page).toHaveURL(/\/cart\/$/);
  await capture(page, info, 'interactions');
});

test('LAY-04 | Длинные и короткие строки, пустой список и 66 записей @compat', async ({ page, manyParts }, info) => {
  await open(page, '/parts/?q=QA_NO_MATCH_0192837465');
  await expect(page.locator('main')).toContainText(/не найден|нет товаров|ничего не найден/i);
  await capture(page, info, 'empty');
  await open(page, '/parts/?type=' + manyParts.typeId);
  const catalog = page.locator('#catalog-table tbody');
  await expect(catalog.locator('tr')).toHaveCount(manyParts.count);
  await expect(catalog.getByText('Я', { exact: true })).toHaveCount(1);
  await expect(catalog.getByText(manyParts.longName, { exact: true })).toHaveCount(1);
  const listSize = page.locator('#catalog-page-size');
  await expect(listSize).toBeVisible();
  const visibleFirst = await catalog.locator('tr:visible td[headers="c-name"]').allTextContents();
  await page.locator('#catalog-pagination').getByRole('button', { name: '2', exact: true }).click();
  await expect.poll(() => catalog.locator('tr:visible td[headers="c-name"]').allTextContents()).not.toEqual(visibleFirst);
  await capture(page, info, 'page-2');
  const dimensions = await documentWidth(page);
  await info.attach('data-width', { body: JSON.stringify(dimensions), contentType: 'application/json' });
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 2);
});

test('LAY-05 | Network и Console на маршрутах основного сценария @compat', async ({ page, baseURL }, info) => {
  const own404 = new Set();
  const ownFailures = new Set();
  const consoleErrors = new Set();
  const exceptions = new Set();
  const external = new Set();
  const browserDiagnostics = new Set();
  page.on('response', r => {
    if (r.status() !== 404) return;
    if (r.url().startsWith(baseURL)) own404.add(r.url());
    else external.add('HTTP 404 ' + r.url());
  });
  page.on('requestfailed', r => {
    const error = r.failure().errorText;
    if (/ERR_ABORTED|NS_BINDING_ABORTED|cancelled/i.test(error)) return;
    const originAndPath = new URL(r.url());
    const entry = error + ' ' + originAndPath.origin + originAndPath.pathname;
    if (r.url().startsWith(baseURL)) ownFailures.add(entry);
    else external.add(entry);
  });
  page.on('console', m => {
    if (m.type() !== 'error') return;
    const url = m.location().url;
    const diagnostic = { text: m.text(), source: url || null };
    if (/chrome:\/\/juggler|devtools:\/\//i.test(url + ' ' + m.text())) {
      browserDiagnostics.add(JSON.stringify(diagnostic));
    } else if (url && !url.startsWith(baseURL)) {
      external.add(JSON.stringify(diagnostic));
    } else {
      consoleErrors.add(JSON.stringify(diagnostic));
    }
  });
  page.on('pageerror', e => exceptions.add(e.message));
  for (const route of ['/', '/parts/', '/cart/', '/login/', '/register/', '/reviews/', '/contacts/', '/employees/']) {
    await open(page, route);
    await page.waitForLoadState('load', { timeout: 7000 }).catch(error => external.add('Загрузка не завершена: ' + route + ' (' + error.name + ')'));
    if (route === '/employees/') {
      await expect.soft(page.locator('#employees-table tbody tr').first()).toBeVisible();
    }
  }
  const evidence = {
    own404: [...own404], ownFailures: [...ownFailures],
    consoleErrors: [...consoleErrors], exceptions: [...exceptions], external: [...external], browserDiagnostics: [...browserDiagnostics],
  };
  await info.attach('network-console', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' });
  await capture(page, info, 'employees');
  expect.soft(evidence.own404, 'Локальные HTTP 404').toEqual([]);
  expect.soft(evidence.ownFailures, 'Локальные сетевые ошибки').toEqual([]);
  expect.soft(evidence.consoleErrors, 'Ошибки Console').toEqual([]);
  expect.soft(evidence.exceptions, 'Исключения JS').toEqual([]);
  expect.soft(evidence.external, 'Ошибки внешних ресурсов в Network/Console').toEqual([]);
});
