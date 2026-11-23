const { expect } = require('@playwright/test');
const { test } = require('./fixtures.cjs');
const { AccountPage, CatalogPage, CartPage, CheckoutPage, ProfilePage } = require('./pages.cjs');

test('UI-01 | Регистрация создаёт профиль клиента', async ({ page, username }) => {
  await new AccountPage(page).register(username);
  await expect(page.locator('#client-profile')).toContainText(username + '@example.test');
});

test('UI-02 | Поиск, изменение количества и очистка корзины', async ({ page, newPart }) => {
  const catalog = new CatalogPage(page);
  const cart = new CartPage(page);
  await catalog.find(newPart.name);
  await catalog.add(newPart, 2);
  await expect(cart.main).toContainText('200,00');
  await cart.increment();
  await expect(cart.main).toContainText('300,00');
  await cart.clear();
});

test('UI-03 | Заказ ЕРИП оплачивается из профиля', async ({ page, username, newPart }) => {
  const profile = new ProfilePage(page);
  await new AccountPage(page).register(username);
  await new CatalogPage(page).add(newPart, 2);
  await new CartPage(page).checkout();
  await new CheckoutPage(page).submit('erip');
  await profile.verifyPending();
  await profile.pay();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('оплачен');
  await expect(page.locator('main')).toContainText('200,00');
});

test('UI-04 | Заказ по счёту отменяется из профиля', async ({ page, username, newPart }) => {
  const profile = new ProfilePage(page);
  await new AccountPage(page).register(username);
  await new CatalogPage(page).add(newPart, 1);
  await new CartPage(page).checkout();
  await new CheckoutPage(page).submit('invoice');
  await profile.verifyPending();
  await profile.cancel();
  await expect(profile.orders.getByRole('button', { name: 'Оплатить', exact: true })).toHaveCount(0);
});

test('UI-05 | Гость перенаправляется на вход при прямом переходе к оформлению', async ({ page, newPart }) => {
  await new CatalogPage(page).add(newPart, 1);
  await page.goto('/checkout/', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/login\/\?next=\/checkout\//);
  await expect(page.locator('main input[name=username]')).toBeVisible();
});
