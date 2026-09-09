// Проверяет 152-ФЗ на всех сайтах из registry.json: согласие на обработку
// персональных данных, заблокированная до согласия кнопка отправки,
// cookie-баннер и отложенная карта.
//
//   node tools/check/legal.js            # все сайты
//   node tools/check/legal.js startshina # выборочно
//
// Главная ловушка, ради которой это написано: карта «Яндекса» в <iframe>
// ставит свои cookie ещё до того, как посетитель что-то нажал. Поэтому
// карта должна подставляться только после согласия — tools/build_legal.py
// заменяет iframe заглушкой, а здесь мы проверяем, что замена сработала.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ROOT = path.resolve(__dirname, '..', '..');

(async () => {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry.json'), 'utf8'));
  const args = process.argv.slice(2);
  const sites = args.length ? reg.sites.filter(s => args.includes(s.slug)) : reg.sites;

  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const problems = [];

  for (const site of sites) {
    const file = path.join(ROOT, 'docs', site.slug, 'index.html');
    const priv = path.join(ROOT, 'docs', site.slug, 'privacy', 'index.html');
    if (!fs.existsSync(file)) { problems.push(`${site.slug}: нет index.html`); continue; }
    if (!fs.existsSync(priv)) { problems.push(`${site.slug}: нет privacy/index.html`); continue; }

    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    await page.goto('file://' + file, { waitUntil: 'load' });
    await page.waitForTimeout(400);

    const before = await page.evaluate(() => {
      const ag = document.querySelector('input#ag, input[name=consent]');
      const sb = document.querySelector('#sb, form button[type=submit]');
      const ck = document.getElementById('ck');
      return {
        agree: !!ag,
        submit: !!sb,
        submitDisabled: sb ? sb.disabled : null,
        cookieBanner: !!ck,
        cookieShown: ck ? getComputedStyle(ck).display !== 'none' : false,
        mapStub: document.querySelectorAll('.mapstub[data-src]').length,
        iframes: document.querySelectorAll('iframe').length,
        privacyLink: !!document.querySelector('a[href^="privacy/"], a[href*="/privacy/"]'),
      };
    });

    const bad = [];
    if (!before.agree) bad.push('нет чекбокса согласия на обработку ПДн');
    if (!before.submit) bad.push('не найдена кнопка отправки формы');
    else if (before.submitDisabled !== true) bad.push('кнопка отправки активна до согласия');
    if (!before.cookieBanner) bad.push('нет cookie-баннера');
    else if (!before.cookieShown) bad.push('cookie-баннер не показывается при первом визите');
    if (!before.privacyLink) bad.push('нет ссылки на политику обработки ПДн');
    if (before.iframes > 0) bad.push(`карта грузится до согласия (iframe: ${before.iframes})`);
    if (before.mapStub === 0 && before.iframes === 0) bad.push('на странице вообще нет карты');

    // Ставим галочку — кнопка должна разблокироваться.
    if (before.agree && before.submit) {
      await page.click('input#ag, input[name=consent]');
      await page.waitForTimeout(150);
      const stillDisabled = await page.evaluate(() => {
        const sb = document.querySelector('#sb, form button[type=submit]');
        return sb ? sb.disabled : null;
      });
      if (stillDisabled === true) bad.push('после согласия кнопка осталась заблокированной');
    }

    // Принимаем cookie — карта должна появиться.
    if (before.cookieBanner) {
      await page.click('#ck [data-ck="y"]').catch(() => {});
      await page.waitForTimeout(400);
      const after = await page.evaluate(() => document.querySelectorAll('iframe').length);
      if (before.mapStub > 0 && after === 0) bad.push('после согласия карта так и не подставилась');
    }

    if (bad.length) problems.push(`${site.slug}: ${bad.join('; ')}`);
    await ctx.close();
  }

  await browser.close();
  if (problems.length) {
    console.log('ПРОБЛЕМЫ:');
    problems.forEach(p => console.log('  ' + p));
    process.exit(1);
  }
  console.log(`✓ все ${sites.length} сайтов и политик прошли проверку`);
})();
