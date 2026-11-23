const { expect } = require('@playwright/test');

class AccountPage {
  constructor(page) {
    this.page = page;
    this.form = page.locator('main form');
  }

  async register(username) {
    await this.page.goto('/register/', { waitUntil: 'domcontentloaded' });
    const values = {
      username, first_name: 'Иван', last_name: 'Тестов',
      birth_date: '1990-01-01', phone: '+375 (29) 123-45-67',
      email: username + '@example.test', address: 'Минск, ул. Тестовая, 1',
      password1: 'DemoQA!926432', password2: 'DemoQA!926432',
    };
    for (const [key, value] of Object.entries(values)) {
      await this.form.locator(`[name="${key}"]`).fill(value);
    }
    await this.form.locator('button[type=submit]').click();
    await expect(this.page).toHaveURL(/\/profile\/$/);
  }
}

class CatalogPage {
  constructor(page) {
    this.page = page;
    this.form = page.locator('form.toolbar');
    this.rows = page.locator('#catalog-table tbody tr');
  }

  async find(name) {
    await this.page.goto('/parts/', { waitUntil: 'domcontentloaded' });
    await this.form.locator('#catalog-q').fill(name);
    await this.form.locator('button[type=submit]').click();
    await expect(this.page.getByRole('link', { name, exact: true })).toBeVisible();
  }

  async add(item, quantity) {
    await this.page.goto(`/parts/${item.id}/`, { waitUntil: 'domcontentloaded' });
    await expect(this.page.getByRole('heading', { name: item.name, exact: true })).toBeVisible();
    await this.page.locator('#buy-quantity').fill(String(quantity));
    await this.page.locator('main form[action*="/cart/add/"] button[type=submit]').click();
    await expect(this.page).toHaveURL(/\/cart\/$/);
  }
}

class CartPage {
  constructor(page) {
    this.page = page;
    this.main = page.locator('main');
  }

  async increment() {
    await this.main.getByTitle('Увеличить количество').click();
    await expect(this.page).toHaveURL(/\/cart\/$/);
  }

  async clear() {
    await this.main.locator('form[action="/cart/clear/"] button').click();
    await expect(this.main.getByRole('heading', { name: 'Корзина пуста' })).toBeVisible();
  }

  async checkout() {
    await this.main.locator('form[action="/checkout/"] input[type=submit]').click();
    await expect(this.page).toHaveURL(/\/checkout\/\??$/);
  }
}

class CheckoutPage {
  constructor(page) {
    this.page = page;
    this.form = page.locator('form.checkout-form');
  }

  async submit(method) {
    await this.form.locator('[name=delivery_method][value=pickup]').check();
    const payment = this.form.locator('[name=payment_method]');
    if (await payment.first().evaluate(node => node.tagName) === 'SELECT') {
      await payment.selectOption(method);
    } else {
      await this.form.locator(`[name=payment_method][value=${method}]`).check();
    }
    if (method === 'card') {
      const month = new Date().getUTCFullYear() + 2 + '-01';
      for (const [key, value] of Object.entries({
        card_number: '4111 1111 1111 1111', card_holder: 'IVAN TESTOV',
        card_expiry: month, card_cvc: '123',
      })) {
        await this.form.locator(`[name="${key}"]`).fill(value);
      }
    }
    await this.form.locator('[name=agree]').check();
    await this.form.locator('button[type=submit]').click();
  }
}

class ProfilePage {
  constructor(page) {
    this.page = page;
    this.orders = page.locator('#orders');
  }

  async verifyPending() {
    await expect(this.page).toHaveURL(/\/profile\/$/);
    await expect(this.orders.getByText('Ожидает оплаты', { exact: true })).toBeVisible();
  }

  async pay() {
    await this.orders.getByRole('button', { name: 'Оплатить', exact: true }).click();
    await expect(this.page).toHaveURL(/\/checkout\/success\/\d+\/$/);
  }

  async cancel() {
    await this.orders.getByRole('button', { name: 'Отменить', exact: true }).click();
    await expect(this.orders.getByText('Отменен', { exact: true })).toBeVisible();
  }
}

module.exports = { AccountPage, CatalogPage, CartPage, CheckoutPage, ProfilePage };
