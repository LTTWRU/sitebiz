#!/usr/bin/env python3
"""Собрать docs/index.html — каталог сделанных демо — из registry.json.

    python tools/build_catalog.py

Каталог всегда показывает ровно то, что перечислено в реестре, поэтому
«какие сайты сделаны» не расходится с реальностью.
"""

import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"
OUT = ROOT / "docs" / "index.html"

# Как подсвечиваем статус работы с клиентом.
STATUS = {
    "новый": ("new", "не звонил"),
    "позвонил": ("call", "позвонил, ждём ответа"),
    "думает": ("call", "думает"),
    "перезвонить": ("call", "перезвонить"),
    "согласовал": ("call", "согласовал, ждём оплату"),
    "продан": ("sold", "продан"),
    "отказ": ("no", "отказался"),
}

MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря")

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Готовые демо-сайты</title>
<meta name="robots" content="noindex">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230f172a'/><text x='16' y='23' font-size='18' font-family='Georgia' text-anchor='middle' fill='%2360a5fa'>S</text></svg>">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{color-scheme:light dark;
  --bg:#f6f7fa;--card:#fff;--line:#e3e7ee;--fg:#0f1729;--mut:#5c6a82;--acc:#2563eb;
  --ok:#16a34a;--warn:#b45309}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0c0f16;--card:#141922;--line:#242c3a;
  --fg:#e8edf6;--mut:#93a1b8;--acc:#60a5fa;--ok:#4ade80;--warn:#fbbf24}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;padding:44px 20px 96px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:clamp(27px,5vw,40px);letter-spacing:-.025em;margin-bottom:10px}}
.sub{{color:var(--mut);margin-bottom:30px;max-width:72ch}}
a{{color:var(--acc);text-decoration:none}}
a:hover{{text-decoration:underline}}
.list{{display:grid;gap:16px}}
.item{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;
  display:grid;grid-template-columns:1fr auto;gap:18px;align-items:start}}
@media(max-width:720px){{.item{{grid-template-columns:1fr}}}}
.item h2{{font-size:20px;letter-spacing:-.015em;margin-bottom:6px}}
.meta{{color:var(--mut);font-size:14px;margin-bottom:12px}}
.tags{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}}
.tag{{font-size:12.5px;font-weight:600;padding:4px 11px;border-radius:999px;background:rgba(37,99,235,.1);color:var(--acc)}}
.tag.st-new{{background:rgba(127,127,127,.16);color:var(--mut)}}
.tag.st-call{{background:rgba(180,83,9,.15);color:var(--warn)}}
.tag.st-sold{{background:rgba(22,163,74,.14);color:var(--ok)}}
.tag.st-no{{background:rgba(220,38,38,.12);color:#dc2626}}
.tag.money{{background:rgba(22,163,74,.14);color:var(--ok)}}
.tag.due{{background:rgba(220,38,38,.14);color:#dc2626}}
.tag.later{{background:rgba(127,127,127,.16);color:var(--mut)}}
.today{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--warn);
  border-radius:16px;padding:18px 24px;margin-bottom:24px}}
.today b{{display:block;font-size:12.5px;color:var(--warn);text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:10px}}
.today ul{{list-style:none;display:grid;gap:7px}}
.today li{{display:flex;gap:12px;justify-content:space-between;align-items:baseline;
  border-bottom:1px solid var(--line);padding-bottom:7px}}
.today li:last-child{{border-bottom:0;padding-bottom:0}}
.today a{{font-weight:600}}
.today span{{color:var(--mut);font-size:13.5px;white-space:nowrap}}
.today li.hot span{{color:#dc2626;font-weight:700}}
.item .note{{margin:0 0 12px;padding:0;background:none;border:0;border-radius:0;
  font-size:14px;color:var(--mut)}}
.money-bar{{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:20px 24px;margin-bottom:24px;display:flex;gap:32px;flex-wrap:wrap}}
.money-bar div b{{display:block;font-size:26px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
.money-bar div span{{display:block;font-size:13px;color:var(--mut);margin-top:3px}}
.msg{{background:rgba(127,127,127,.07);border-left:3px solid var(--acc);border-radius:0 10px 10px 0;
  padding:13px 16px;font-size:14.5px;line-height:1.55}}
.msg b{{display:block;font-size:12.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-weight:700}}
.side{{display:flex;flex-direction:column;gap:9px;min-width:186px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:12px 18px;
  border-radius:10px;font-weight:700;font-size:14.5px;border:1.5px solid var(--line);color:var(--fg);
  transition:border-color .18s,color .18s;white-space:nowrap;cursor:pointer;font-family:inherit}}
.btn:hover{{border-color:var(--acc);color:var(--acc);text-decoration:none}}
.btn.p{{background:var(--acc);color:#fff;border-color:var(--acc)}}
.btn.p:hover{{opacity:.88;color:#fff}}
.btn.done{{border-color:var(--ok);color:var(--ok)}}
.note{{margin-top:36px;padding:22px 24px;background:var(--card);border:1px solid var(--line);
  border-radius:16px;font-size:15px;color:var(--mut)}}
.note h3{{color:var(--fg);font-size:17px;margin-bottom:10px}}
.note ol{{margin:10px 0 0 20px;display:grid;gap:7px}}
</style>
</head>
<body><div class="wrap">
<h1>Готовые демо-сайты</h1>
<p class="sub">Сделано сайтов: <b>{count}</b>. Каждый собран по карточке 2ГИС — настоящие услуги,
режим работы, отзывы и фото. Кнопка «Скопировать сообщение» подставит правильную ссылку
и положит текст в буфер: остаётся вставить в WhatsApp или Telegram владельцу.</p>

{today}
{money}
<div class="list">
{items}
</div>

<div class="note">
  <h3>Порядок работы</h3>
  <ol>
    <li>Открой сайт и посмотри сам — обязательно с телефона, владелец откроет с него же.</li>
    <li>Позвони или напиши, сразу дав ссылку.</li>
    <li>Спросят цену — назови свою. Сайт готов, остаётся только передать.</li>
    <li>Согласились — скажи мне, я подключу приём заявок и, если нужно, их домен.</li>
  </ol>
</div>
</div>
<script>
const base = location.href.replace(/index\\.html?$/, '').replace(/\\/?$/, '/');
document.querySelectorAll('.t').forEach(t=>t.textContent = t.textContent.replace('{{URL}}', base));
document.querySelectorAll('.copy').forEach(b=>{{
  b.onclick = ()=>{{
    navigator.clipboard.writeText(b.closest('.item').querySelector('.t').textContent.trim());
    b.textContent='Скопировано'; b.classList.add('done');
    setTimeout(()=>{{b.textContent='Скопировать сообщение'; b.classList.remove('done');}}, 1800);
  }};
}});
</script>
</body>
</html>
"""

ITEM = """<article class="item">
  <div>
    <h2>{headline}</h2>
    <div class="meta">{meta}{contacts}</div>
    <div class="tags">{tags}{money}</div>
    {note}
    <div class="msg"><b>Сообщение владельцу</b><span class="t">{message}</span></div>
  </div>
  <div class="side">
    <a class="btn p" href="{slug}/">Открыть сайт</a>
    <button class="btn copy">Скопировать сообщение</button>
    {call}
    <a class="btn" href="{url2gis}" target="_blank" rel="noopener">Карточка 2ГИС</a>
  </div>
</article>"""


def main():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sites = data.get("sites", [])

    def rub(v):
        """Разряды пробелами: 14900 -> 14 900."""
        return f"{v:,}".replace(",", "\u00a0")

    def plural(n, one, few, many):
        """«1 клиента», «2 клиентов», «5 клиентов» — иначе сводка выглядит неряшливо."""
        n10, n100 = n % 10, n % 100
        if n10 == 1 and n100 != 11:
            return one
        if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
            return few
        return many

    # Считаем только то, за что уже договорились: «согласовал» и «продан».
    paid = [x for x in sites if x.get("status") in ("согласовал", "продан")]
    once = sum(int(x.get("price_site", 0)) + int(x.get("price_extra", 0)) for x in paid)
    monthly = sum(int(x.get("price_month", 0)) for x in paid)
    word = plural(len(paid), "клиента", "клиентов", "клиентов")
    money = ""
    if paid:
        money = ('<div class="money-bar">'
                 f'<div><b>{rub(monthly)}\u00a0₽</b><span>в месяц с {len(paid)} {word}</span></div>'
                 f'<div><b>{rub(once)}\u00a0₽</b><span>разовыми за сайты и логотипы</span></div>'
                 f'<div><b>{rub(monthly*12)}\u00a0₽</b><span>обслуживание за год, если никто не уйдёт</span></div>'
                 '</div>')

    # Кого набирать сегодня — самое важное, поэтому наверх и отдельной плашкой.
    today = date.today()

    def due(s):
        """Дата, к которой обещали перезвонить (или None)."""
        try:
            return date.fromisoformat(s["followup"])
        except (KeyError, ValueError):
            return None

    def order(s):
        """Сверху — просроченные звонки, снизу — отказы."""
        d, st = due(s), s.get("status", "новый")
        if d and d <= today:
            return (0, d.toordinal())
        if st in ("согласовал", "продан"):
            return (1, 0)
        if d:
            return (2, d.toordinal())
        return ({"позвонил": 3, "думает": 3, "перезвонить": 3,
                 "новый": 4, "отказ": 5}.get(st, 4), 0)

    sites = sorted(sites, key=order)

    # Кому и когда обещали перезвонить. Держать это в голове — верный способ
    # потерять клиента, который сказал «наберите через две недели».
    planned = [s for s in sites if due(s)]
    todo = ""
    if planned:
        rows = []
        for s in planned:
            d = due(s)
            phone = "".join(c for c in (s.get("phones") or [""])[0] if c.isdigit() or c == "+")
            when = "сегодня" if d == today else ("просрочено" if d < today
                                                 else f"{d.day} {MONTHS[d.month - 1]}")
            cl = ' class="hot"' if d <= today else ""
            rows.append(f'<li{cl}><a href="tel:{phone}">{html.escape(s["name"])}</a>'
                        f'<span>{when}</span></li>')
        hot = sum(1 for s in planned if due(s) <= today)
        head = f"Звонить сегодня — {hot}" if hot else "Ближайшие звонки"
        todo = f'<div class="today"><b>{head}</b><ul>{"".join(rows)}</ul></div>'

    blocks = []
    for s in sites:
        cls, label = STATUS.get(s.get("status", "новый"), STATUS["новый"])
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in s.get("tags", []))
        tags += f'<span class="tag st-{cls}">{html.escape(label)}</span>'
        if (d := due(s)):
            when = f"{d.day} {MONTHS[d.month - 1]}"
            cl = "due" if d <= today else "later"
            word = "звонить" if d <= today else "созвон"
            tags += f'<span class="tag {cl}">{word} {when}</span>'
        contacts = " · " + " · ".join(s.get("phones", []))
        if s.get("email"):
            contacts += " · " + s["email"]
        phone = "".join(c for c in (s.get("phones") or [""])[0] if c.isdigit() or c == "+")
        call = f'<a class="btn" href="tel:{phone}">Позвонить</a>' if phone else ""
        deal = []
        if s.get("price_site"):  deal.append(f'сайт {rub(int(s["price_site"]))}\u00a0₽')
        if s.get("price_extra"): deal.append(f'логотип {rub(int(s["price_extra"]))}\u00a0₽')
        if s.get("price_month"): deal.append(f'{rub(int(s["price_month"]))}\u00a0₽/мес')
        money_tag = f'<span class="tag money">{html.escape(" · ".join(deal))}</span>' if deal else ""
        blocks.append(ITEM.format(
            headline=html.escape(s["headline"]), meta=html.escape(s["meta"]),
            contacts=html.escape(contacts), tags=tags,
            message=html.escape(s["message"]), slug=s["slug"],
            url2gis=s["url2gis"], call=call, money=money_tag,
            note=(f'<p class="note">{html.escape(s["note"])}</p>' if s.get("note") else ""),
        ))

    OUT.write_text(PAGE.format(count=len(sites), items="\n".join(blocks), money=money,
                               today=todo),
                   encoding="utf-8")
    print(f"{OUT}  ({len(sites)} сайтов)")


if __name__ == "__main__":
    main()
