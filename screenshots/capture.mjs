// Screenshots of the web client and PNG images of the architecture figures, for the delivery documents.
//
// It drives a running stack through the browser, the same way the end-to-end suite does, and writes:
//   orderflow-engine-docs/delivery/screenshots/<es|en>/01-store-picker.png ... 09-mobile-summary.png
//   orderflow-engine-docs/delivery/figures/<stem>.png, one per SVG of orderflow-engine-docs/diagrams/, at 2x on white
//
// It runs in the end-to-end runner image, which holds Node, Playwright and Chromium. Build it once from the
// workspace root (scripts/e2e.sh of orderflow-engine-infra builds the same image):
//   docker build --tag ofe-e2e-runner orderflow-engine-infra/e2e
// Then, with the full stack running (web client on port 8081 of the host), from the workspace root:
//   docker run --rm --init --ipc=host --add-host=host.docker.internal:host-gateway \
//     -v "$PWD/orderflow-engine-tools/screenshots:/e2e/screenshots:ro" \
//     -v "$PWD/orderflow-engine-docs:/docs" \
//     ofe-e2e-runner node /e2e/screenshots/capture.mjs
// The script is mounted under /e2e so that Node finds the image's /e2e/node_modules/playwright.
//
// Environment (all optional):
//   BASE_URL   the web client, default http://host.docker.internal:8081
//   DOCS_DIR   the mounted orderflow-engine-docs repository, default /docs
//   LANGUAGES  comma-separated, default es,en
//   ONLY       screens | figures | all (default all)
//   CONFIRM    1 (default) confirms one order per language for 06; 0 places no order, skips 06, and 07 shows the
//              orders already there
//
// Desktop screens use a 1280x800 viewport at device scale 1 and the light color scheme; the mobile summary uses
// 375x812 at device scale 2. Short screens are cropped to their content, and long ones are taken whole.
//
// The flow per language, in a fresh browser context (fresh storage, so the store is the first configured one,
// Tienda Norte of co-alpha, and ?lang= sets the language): catalog, store picker, cart, quote, summary, levers,
// mobile summary, confirmation, My orders, and last a problem: Tienda Sur, which has no credit account, asks for a
// quote on credit. Every confirmation uses credit of Tienda Norte; the script stops before confirming when the quote
// does not fit the available credit. Labels come from the client's own dictionaries, never from this file.

import { chromium } from 'playwright';
import { mkdirSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const BASE_URL = process.env.BASE_URL ?? 'http://host.docker.internal:8081';
const DOCS_DIR = process.env.DOCS_DIR ?? '/docs';
const LANGUAGES = (process.env.LANGUAGES ?? 'es,en').split(',').map((language) => language.trim()).filter(Boolean);
const ONLY = process.env.ONLY ?? 'all';
const CONFIRM = (process.env.CONFIRM ?? '1') !== '0';

const SCREENSHOTS_DIR = join(DOCS_DIR, 'delivery', 'screenshots');
const FIGURES_DIR = join(DOCS_DIR, 'delivery', 'figures');
const DIAGRAMS_DIR = join(DOCS_DIR, 'diagrams');

/** The cart that shows every lever of co-alpha: the combo, the tier discount on the colas left over, and the gift. */
const CART = [
  { sku: 'BEV-COLA-350', qty: 40 },
  { sku: 'SNK-CHIPS-45', qty: 10 },
];
/** The cart line of the problem screenshot. */
const PROBLEM_LINE = { sku: 'BEV-COLA-350', qty: 2 };

const DESKTOP = { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 };
const MOBILE = { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
/** Dates show in the time zone of the store's country (Colombia). */
const TIME_ZONE = 'America/Bogota';
const TIMEOUT_MS = 30_000;
const MARGIN = 16;

const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';

function log(message) {
  process.stdout.write(`${message}\n`);
}

/** The text of a dictionary key, with its {{parameters}} replaced, as the client renders it. */
function label(dictionary, key, parameters = {}) {
  let value = dictionary;
  for (const part of key.split('.')) {
    value = value && typeof value === 'object' ? value[part] : undefined;
  }
  if (typeof value !== 'string') {
    throw new Error(`The ${key} key has no text`);
  }
  return value.replace(/\{\{\s*(\w+)\s*\}\}/g, (placeholder, name) => parameters[name] ?? placeholder);
}

async function getJson(path) {
  const response = await fetch(new URL(path, BASE_URL));
  if (!response.ok) {
    throw new Error(`GET ${path} answered ${response.status}`);
  }
  return response.json();
}

/** Waits until the screen has no loading text, its images are decoded and its fonts are ready. */
async function settle(page) {
  await page.locator('.page-loading').waitFor({ state: 'detached', timeout: TIMEOUT_MS });
  await page.waitForLoadState('networkidle');
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      [...document.images].map((image) =>
        image.complete ? null : new Promise((resolve) => image.addEventListener('load', resolve, { once: true })),
      ),
    );
  });
}

/**
 * The rectangle that holds every given element, widened by a margin and kept inside the viewport. It is measured at
 * the top of the page, where the screenshot is taken.
 */
async function regionOf(page, locators, { fullWidth = false } = {}) {
  const boxes = [];
  for (const locator of locators) {
    const box = await locator.boundingBox();
    if (!box) {
      throw new Error(`Nothing to frame: ${locator}`);
    }
    boxes.push(box);
  }
  const { width, height } = page.viewportSize();
  const left = fullWidth ? 0 : Math.max(0, Math.min(...boxes.map((box) => box.x)) - MARGIN);
  const top = Math.max(0, Math.min(...boxes.map((box) => box.y)) - MARGIN);
  const right = fullWidth ? width : Math.min(width, Math.max(...boxes.map((box) => box.x + box.width)) + MARGIN);
  const bottom = Math.min(height, Math.max(...boxes.map((box) => box.y + box.height)) + MARGIN);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/** Grows the viewport to the height of the whole page, so the sticky action bar is drawn at its end, not over it. */
async function growToPage(page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const { width, height } = page.viewportSize();
    const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    if (pageHeight <= height) {
      return;
    }
    await page.setViewportSize({ width, height: pageHeight });
  }
}

/** Shrinks the viewport to end just below the given element, so a short screen is not mostly empty space. */
async function shrinkTo(page, locator) {
  await page.evaluate(() => window.scrollTo(0, 0));
  const { width, height } = page.viewportSize();
  const content = await locator.boundingBox();
  const bar = await page.locator('ui-action-bar').boundingBox();
  const needed = Math.ceil(content.y + content.height + 2 * MARGIN + (bar?.height ?? 0));
  if (needed < height) {
    await page.setViewportSize({ width, height: needed });
  }
}

/**
 * One screenshot. `whole` takes the whole page; `frame` takes the region of the given elements (`fullWidth` keeps the
 * page's width); `shrink` ends the viewport below the given element; with none, the viewport as the user sees it.
 */
async function shoot(page, language, name, { whole = false, frame = null, fullWidth = false, shrink = null } = {}) {
  const path = join(SCREENSHOTS_DIR, language, `${name}.png`);
  const viewport = page.viewportSize();
  if (whole || frame) {
    await growToPage(page);
  }
  if (shrink) {
    await shrinkTo(page, shrink);
  }
  // No focus ring of the last control the script used, and the top of the page.
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  const clip = frame ? await regionOf(page, frame, { fullWidth }) : undefined;
  await page.screenshot({ path, clip, animations: 'disabled', caret: 'hide' });
  await page.setViewportSize(viewport);
  log(`  ${language}/${name}.png`);
}

function newContext(browser, language, device) {
  return browser.newContext({
    ...device,
    baseURL: BASE_URL,
    colorScheme: 'light',
    reducedMotion: 'reduce',
    timezoneId: TIME_ZONE,
    locale: language === 'es' ? 'es-CO' : 'en-US',
  });
}

/** Fails on any browser error, so no screenshot shows a broken screen. */
function watchErrors(page, errors) {
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
}

async function captureLanguage(browser, language, stores) {
  log(`Screens in ${language}`);
  mkdirSync(join(SCREENSHOTS_DIR, language), { recursive: true });
  const text = await getJson(`/i18n/${language}.json`);
  const exact = (key, parameters) => ({ name: label(text, key, parameters), exact: true });
  const [creditStore, cashStore] = stores;
  const facts = { language };

  const context = await newContext(browser, language, DESKTOP);
  const page = await context.newPage();
  page.setDefaultTimeout(TIMEOUT_MS);
  const errors = [];
  watchErrors(page, errors);

  // 02 Catalog: the products of the first store, nothing in the cart yet
  await page.goto(`/cart?lang=${language}`);
  await page.waitForFunction((lang) => document.documentElement.lang === lang, language);
  await page.locator('.product-card').first().waitFor();
  await settle(page);
  await shoot(page, language, '02-catalog', { whole: true });

  // 01 Store picker: the disclosure open, the stores grouped by tenant
  const picker = page.locator('details.store-picker');
  await picker.locator('summary').click();
  const panel = picker.locator('.store-picker__panel');
  await panel.waitFor();
  await shoot(page, language, '01-store-picker', { frame: [page.locator('app-shell-header'), panel], fullWidth: true });
  await picker.locator('summary').click();
  await panel.waitFor({ state: 'hidden' });

  // 03 Cart: the quantities of CART, paid on credit
  for (const line of CART) {
    const input = page.locator(`input[data-sku="${line.sku}"]`);
    await input.fill(String(line.qty));
    await input.blur();
  }
  await page.getByRole('radio', exact('paymentMethod.CREDIT')).check();
  await settle(page);
  await shoot(page, language, '03-cart', { whole: true });

  // 04 and 05: the quote of that cart
  const quoteAnswer = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/quotes') && response.request().method() === 'POST',
  );
  await page.getByRole('button', exact('cart.actions.quote')).click();
  const quote = await (await quoteAnswer).json();
  await page.waitForURL(new RegExp(`/quotes/${UUID}$`));
  await page.locator('section[aria-labelledby="totals-title"]').waitFor();
  await settle(page);
  facts.quote = {
    quoteId: quote.quoteId,
    currency: quote.currency,
    lines: quote.lines.map((line) => ({
      sku: line.sku,
      description: line.description,
      qty: line.qty,
      isGift: line.isGift,
      gross: line.gross,
      discounts: line.discounts,
      comboAllocations: line.comboAllocations,
      net: line.net,
      referenceValue: line.referenceValue,
      taxableBase: line.taxableBase,
      taxRate: line.taxRate,
      tax: line.tax,
    })),
    totals: quote.totals,
    credit: quote.credit,
  };
  await shoot(page, language, '04-quote-summary', { frame: [page.locator('.summary-column')] });
  await shoot(page, language, '05-quote-levers', { frame: [page.locator('section[aria-labelledby="lines-title"]')] });

  // 09 Mobile summary: the same quote on a phone, before it is confirmed
  const mobile = await newContext(browser, language, MOBILE);
  const phone = await mobile.newPage();
  phone.setDefaultTimeout(TIMEOUT_MS);
  watchErrors(phone, errors);
  await phone.goto(`/quotes/${quote.quoteId}?lang=${language}`);
  await phone.locator('section[aria-labelledby="totals-title"]').waitFor();
  await settle(phone);
  await shoot(phone, language, '09-mobile-summary');
  await mobile.close();

  if (CONFIRM) {
    if (!quote.credit?.fits) {
      throw new Error(
        `The quote does not fit the credit of ${creditStore.name}: available ${quote.credit?.available}, ` +
          `total ${quote.totals.total}. Confirming would fail, so 06 is not taken.`,
      );
    }
    // 06 Order confirmed
    const orderAnswer = page.waitForResponse(
      (response) => new RegExp(`/api/v1/orders/${UUID}$`).test(response.url()) && response.request().method() === 'GET',
    );
    await page.getByRole('button', exact('orderSummary.actions.confirm')).click();
    await page.waitForURL(new RegExp(`/orders/${UUID}$`));
    const order = await (await orderAnswer).json();
    await page.locator('.order-outcome').waitFor();
    await settle(page);
    facts.order = { orderId: order.orderId, orderNumber: order.orderNumber, status: order.status, total: order.totals.total };
    await shoot(page, language, '06-order-confirmed');
  } else {
    log('  CONFIRM=0: 06 skipped, no order placed');
  }

  // 07 My orders: from the order's "View my orders" link, or straight from the URL when no order was placed
  const historyAnswer = page.waitForResponse(
    (response) => response.url().includes('/api/v1/orders?') && response.request().method() === 'GET',
  );
  if (CONFIRM) {
    await page.getByRole('link', exact('order.actions.history')).click();
  } else {
    await page.goto(`/orders?lang=${language}`);
  }
  await page.waitForURL(/\/orders(\?.*)?$/);
  const history = await (await historyAnswer).json();
  await page.locator('.order-list').waitFor();
  await settle(page);
  facts.history = {
    count: history.items.length,
    first: history.items.slice(0, 3).map((item) => ({ orderNumber: item.orderNumber, confirmedAt: item.confirmedAt, total: item.total })),
  };
  await shoot(page, language, '07-my-orders', { shrink: page.locator('.order-list') });

  // 08 Problem: the cash-only store asks for a quote on credit; the API answers 422 CREDIT_NOT_ENABLED
  await page.goto(`/cart?lang=${language}`);
  await page.locator('.product-card').first().waitFor();
  await picker.locator('summary').click();
  await panel.getByRole('button', { name: cashStore.name, exact: true }).click();
  await page.waitForURL(/\/cart/);
  await page.locator('.store-picker__value', { hasText: cashStore.name }).waitFor();
  await page.locator('.product-card').first().waitFor();
  await settle(page);
  const problemLine = page.locator(`input[data-sku="${PROBLEM_LINE.sku}"]`);
  await problemLine.fill(String(PROBLEM_LINE.qty));
  await problemLine.blur();
  await page.getByRole('radio', exact('paymentMethod.CREDIT')).check();
  const problemAnswer = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/quotes') && response.request().method() === 'POST',
  );
  await page.getByRole('button', exact('cart.actions.quote')).click();
  const problemResponse = await problemAnswer;
  const problem = await problemResponse.json();
  const notice = page.locator('ui-problem-notice [role="alert"]');
  await notice.waitFor();
  await settle(page);
  facts.problem = { status: problemResponse.status(), code: problem.code, title: problem.title, detail: problem.detail };
  await shoot(page, language, '08-error-message', { frame: [page.locator('app-shell-header'), notice], fullWidth: true });
  await context.close();

  // A browser error is a broken screen. A failed load with a 4xx status is not: 08 asks for a 422 on purpose.
  const real = errors.filter((message) => !/Failed to load resource: the server responded with a status of 4\d\d/.test(message));
  if (real.length) {
    throw new Error(`Browser errors in ${language}:\n${real.join('\n')}`);
  }
  if (problemResponse.status() !== 422 || problem.code !== 'CREDIT_NOT_ENABLED') {
    throw new Error(`The problem screenshot expected 422 CREDIT_NOT_ENABLED, got ${problemResponse.status()} ${problem.code}`);
  }
  log(`FACTS ${JSON.stringify(facts)}`);
}

/** The size an SVG declares: its width and height attributes, else its viewBox. */
function svgSize(svg) {
  const root = svg.match(/<svg\b[^>]*>/)?.[0] ?? '';
  const width = Number(root.match(/\bwidth="([\d.]+)"/)?.[1]);
  const height = Number(root.match(/\bheight="([\d.]+)"/)?.[1]);
  if (width && height) {
    return { width: Math.ceil(width), height: Math.ceil(height) };
  }
  const box = root.match(/\bviewBox="[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)"/);
  if (!box) {
    throw new Error('The SVG declares no size');
  }
  return { width: Math.ceil(Number(box[1])), height: Math.ceil(Number(box[2])) };
}

async function captureFigures(browser) {
  log('Figures');
  mkdirSync(FIGURES_DIR, { recursive: true });
  const files = readdirSync(DIAGRAMS_DIR).filter((file) => file.endsWith('.svg')).sort();
  for (const file of files) {
    const svg = readFileSync(join(DIAGRAMS_DIR, file), 'utf8');
    const size = svgSize(svg);
    const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, colorScheme: 'light' });
    const page = await context.newPage();
    await page.setContent(
      `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}` +
        `svg{display:block}</style></head><body>${svg}</body></html>`,
    );
    await page.evaluate(() => document.fonts.ready);
    const stem = file.replace(/\.svg$/, '');
    await page.locator('svg').first().screenshot({ path: join(FIGURES_DIR, `${stem}.png`), omitBackground: false });
    await context.close();
    log(`  figures/${stem}.png (${size.width * 2}x${size.height * 2})`);
  }
}

async function main() {
  const browser = await chromium.launch();
  try {
    if (ONLY === 'all' || ONLY === 'figures') {
      await captureFigures(browser);
    }
    if (ONLY === 'all' || ONLY === 'screens') {
      const stores = await getJson('/config/stores.json');
      if (stores.length < 2 || stores[0].tenantId !== stores[1].tenantId) {
        throw new Error('The first two configured stores must be the credit and the cash store of one tenant');
      }
      for (const language of LANGUAGES) {
        await captureLanguage(browser, language, stores);
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exit(1);
});
