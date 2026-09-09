// Проверяет готовые страницы на то, что ломается чаще всего и незаметно:
// горизонтальное переполнение на узком экране, незагрузившиеся фотографии,
// ошибки JS и отсутствие кликабельного телефона.
//
//   node tools/check/render.js startshina black-auto
//   node tools/check/render.js --all          # все сайты из registry.json
//
// Ширины: 1440 (десктоп), 390 (iPhone), 360 (самый узкий Android).
// 360 не для красоты: именно на нём вылезает вёрстка, которая на 390 держится.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ROOT = path.resolve(__dirname, '..', '..');
const WIDTHS = [1440, 390, 360];

function slugs() {
  const args = process.argv.slice(2);
  if (args.length && args[0] !== '--all') return args;
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry.json'), 'utf8'));
  return reg.sites.map(s => s.slug);
}

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const list = slugs();
  let bad = 0, warn = 0;

  for (const slug of list) {
    const file = path.join(ROOT, 'docs', slug, 'index.html');
    if (!fs.existsSync(file)) { console.log(`✗ ${slug}: нет docs/${slug}/index.html`); bad++; continue; }

    const ctx = await browser.newContext({ viewport: { width: WIDTHS[0], height: 900 } });
    // Соглашаемся с cookie заранее, иначе баннер перекрывает низ страницы.
    await ctx.addInitScript(() => { try { localStorage.setItem('ck-choice', 'y'); } catch (e) {} });
    const page = await ctx.newPage();

    const errs = [];
    page.on('pageerror', e => errs.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });

    await page.goto('file://' + file, { waitUntil: 'load' });

    // Прокручиваем страницу до низа: фотографии ниже сгиба стоят с
    // loading="lazy" и без прокрутки просто не начнут грузиться. Без этого
    // шага проверка объявляет битыми совершенно здоровые снимки.
    await page.evaluate(async () => {
      // На страницах включён scroll-behavior:smooth — прокрутка анимируется,
      // и цикл убегает вперёд, так и не дойдя до низа. Отключаем на время.
      const prev = document.documentElement.style.scrollBehavior;
      document.documentElement.style.scrollBehavior = 'auto';
      const step = window.innerHeight * 0.8;
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise(r => setTimeout(r, 60));
      }
      window.scrollTo(0, 0);
      document.documentElement.style.scrollBehavior = prev;
      await Promise.all([...document.images]
        .filter(i => !i.complete)
        .map(i => new Promise(r => {
          i.addEventListener('load', r, { once: true });
          i.addEventListener('error', r, { once: true });
          setTimeout(r, 3000);
        })));
    });
    await page.waitForTimeout(300);

    const info = await page.evaluate(() => {
      const broken = [...document.images]
        .filter(i => !i.complete || i.naturalWidth === 0)
        .map(i => i.getAttribute('src'));
      const noAlt = [...document.images].filter(i => !i.alt).map(i => i.getAttribute('src'));
      const h1 = document.querySelector('h1');
      return {
        broken, noAlt,
        tel: document.querySelectorAll('a[href^="tel:"]').length,
        h1Font: h1 ? getComputedStyle(h1).fontFamily.split(',')[0].replace(/["']/g, '') : '—',
        bodyFont: getComputedStyle(document.body).fontFamily.split(',')[0].replace(/["']/g, ''),
        title: document.title.length,
        desc: (document.querySelector('meta[name=description]') || {}).content?.length || 0,
      };
    });

    const overflow = [];
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.waitForTimeout(220);
      const over = await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (over > 1) overflow.push(`${w}px: +${over}`);
    }

    // Поломки: страница выглядит сломанной у посетителя.
    const problems = [];
    if (info.broken.length) problems.push(`битые фото: ${info.broken.join(', ')}`);
    if (info.noAlt.length) problems.push(`без alt: ${info.noAlt.join(', ')}`);
    if (overflow.length) problems.push(`переполнение — ${overflow.join('; ')}`);
    if (errs.length) problems.push(`ошибки JS: ${errs.slice(0, 3).join(' | ')}`);
    if (!info.tel) problems.push('нет ни одной ссылки tel:');

    // Замечания: на демо-сайте под noindex не горит, но перед публикацией
    // поисковик обрежет длинный заголовок и описание на полуслове.
    const notes = [];
    if (info.title > 70) notes.push(`<title> ${info.title} знаков, поиск покажет ~70`);
    if (info.desc < 70 || info.desc > 320) notes.push(`description ${info.desc} знаков (норма 70–320)`);

    if (problems.length) { bad++; console.log(`✗ ${slug}\n    ${problems.join('\n    ')}`); }
    else console.log(`✓ ${slug} | h1: ${info.h1Font} | текст: ${info.bodyFont} | tel-ссылок: ${info.tel}`);
    if (notes.length) { warn++; notes.forEach(n => console.log(`    · ${n}`)); }

    await ctx.close();
  }

  await browser.close();
  console.log(bad
    ? `\nполомки на ${bad} из ${list.length}`
    : `\nвсе ${list.length} чистые: нет переполнения, битых фото и ошибок JS`);
  if (warn) console.log(`замечаний к заголовкам и описаниям: ${warn} (не поломка, но поправить перед публикацией)`);
  process.exit(bad ? 1 : 0);
})();
