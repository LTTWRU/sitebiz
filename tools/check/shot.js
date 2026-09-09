// Снимки страниц — чтобы смотреть на результат, а не на исходник.
//
//   node tools/check/shot.js hero startshina black-auto      # первый экран
//   node tools/check/shot.js full startshina                 # страница целиком
//   node tools/check/shot.js sec startshina sklad uslugi     # отдельные секции
//   node tools/check/shot.js hero startshina --w 390         # на телефоне
//
// Кладёт в out/. Каталог out/ в .gitignore, в репозиторий снимки не попадают.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ROOT = path.resolve(__dirname, '..', '..');
const OUT = path.join(ROOT, 'out');

(async () => {
  const argv = process.argv.slice(2);
  const mode = argv.shift();
  if (!['hero', 'full', 'sec'].includes(mode)) {
    console.log('режимы: hero | full | sec');
    process.exit(1);
  }
  let width = 1440;
  const wi = argv.indexOf('--w');
  if (wi !== -1) { width = parseInt(argv[wi + 1], 10); argv.splice(wi, 2); }

  const slug = mode === 'sec' ? argv.shift() : null;
  const targets = mode === 'sec' ? [slug] : argv;
  const sections = mode === 'sec' ? argv : [];
  if (!targets.length) { console.log('не указан слаг'); process.exit(1); }

  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  // Без согласия cookie-баннер закрывает низ кадра.
  await ctx.addInitScript(() => { try { localStorage.setItem('ck-choice', 'y'); } catch (e) {} });

  for (const s of targets) {
    const file = path.join(ROOT, 'docs', s, 'index.html');
    if (!fs.existsSync(file)) { console.log(`нет docs/${s}/index.html`); continue; }
    const page = await ctx.newPage();
    await page.goto('file://' + file, { waitUntil: 'load' });
    await page.waitForTimeout(1200);

    if (mode === 'sec') {
      for (const id of sections) {
        const el = await page.$('#' + id);
        if (!el) { console.log(`  ${s}: нет секции #${id}`); continue; }
        const out = path.join(OUT, `${s}-${id}.png`);
        await el.screenshot({ path: out });
        console.log(out);
      }
    } else {
      const out = path.join(OUT, `${mode}-${s}${width !== 1440 ? '-' + width : ''}.png`);
      await page.screenshot({ path: out, fullPage: mode === 'full' });
      console.log(out);
    }
    await page.close();
  }

  await browser.close();
})();
