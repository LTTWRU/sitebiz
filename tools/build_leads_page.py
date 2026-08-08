#!/usr/bin/env python3
"""Собрать из результатов сканирования страницу выбора лидов для GitHub Pages.

    python tools/build_leads_page.py leads.json --city Новосибирск --slug nsk-auto

На выходе docs/<slug>/index.html — список со всеми найденными бизнесами,
фильтрами и галочками. Отмечаешь нужных, жмёшь «Скопировать выбранные» и
присылаешь мне — я делаю по ним сайты.
"""

import argparse
import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Что показываем в фильтрах. Порядок = порядок кнопок.
REGISTRY = ROOT / "registry.json"


def done_map():
    """{ссылка на карточку 2ГИС: slug} — по кому сайт уже сделан."""
    if not REGISTRY.exists():
        return {}
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {s["url2gis"]: s["slug"] for s in data.get("sites", [])}


BUCKETS = [
    ("none", "Сайта нет вообще", "Ни ссылки, ни соцсетей в карточке"),
    ("broken", "Сайт битый", "Не открывается, заглушка или домен припаркован"),
    ("social", "Только соцсети", "Вместо сайта Telegram, ВК, WhatsApp или конструктор"),
    ("unknown", "Проверить вручную", "Автопроверка не смогла достучаться — открой глазами"),
    ("live", "Рабочий сайт есть", "Сайт открывается и наполнен — скорее всего мимо"),
]


def bucket_of(lead):
    live = lead.get("live_status") or ""
    if live in ("dead", "stub", "parked"):
        return "broken"
    if live == "unknown":
        return "unknown"
    if live == "live":
        return "live"
    if lead["website_status"] == "none":
        return "none"
    return "social"


def compact(lead, done=None):
    done = done or {}
    return {
        "done": done.get(lead["url_2gis"], ""),
        "n": lead["name"],
        "c": lead["categories"][:70],
        "a": lead["address"],
        "p": [p.strip() for p in lead["phones"].split(",") if p.strip()],
        "e": lead["emails"],
        "r": lead["rating"] or "",
        "v": lead["reviews_count"],
        "s": lead["score"],
        "b": bucket_of(lead),
        "d": lead["website_note"],
        "u": lead["url_2gis"],
        "w": lead["sites"].split(",")[0].strip(),
        "h": lead["schedule"][:60],
    }


PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Лиды: {title}</title>
<meta name="robots" content="noindex">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230f172a'/><text x='16' y='23' font-size='18' font-family='Georgia' text-anchor='middle' fill='%2360a5fa'>L</text></svg>">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{color-scheme:light dark;
 --bg:#f5f7fa;--card:#fff;--line:#e2e7ef;--fg:#0f1729;--mut:#5c6a82;--acc:#2563eb;
 --bad:#dc2626;--warn:#b45309;--ok:#16a34a;--soft:#7c3aed}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0b0e14;--card:#141922;--line:#232b39;
 --fg:#e8edf6;--mut:#93a1b8;--acc:#60a5fa;--bad:#f87171;--warn:#fbbf24;--ok:#4ade80;--soft:#a78bfa}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1240px;margin:0 auto;padding:36px 18px 140px}}
h1{{font-size:clamp(24px,4vw,34px);letter-spacing:-.025em;margin-bottom:8px}}
.sub{{color:var(--mut);margin-bottom:26px;max-width:80ch}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:18px;position:sticky;top:12px;z-index:20}}
.row{{display:flex;gap:9px;flex-wrap:wrap;align-items:center}}
.row+.row{{margin-top:11px}}
input[type=search],input[type=number]{{background:var(--bg);border:1.5px solid var(--line);color:var(--fg);
 padding:10px 13px;border-radius:10px;font:inherit;font-size:14.5px}}
input[type=search]{{flex:1;min-width:200px}}
input[type=number]{{width:82px}}
.chip{{border:1.5px solid var(--line);background:transparent;color:var(--fg);padding:8px 14px;
 border-radius:999px;font:inherit;font-size:13.5px;font-weight:650;cursor:pointer;transition:.15s}}
.chip:hover{{border-color:var(--acc)}}
.chip.on{{background:var(--acc);border-color:var(--acc);color:#fff}}
.chip small{{opacity:.72;font-weight:600;margin-left:5px}}
.lbl{{color:var(--mut);font-size:13.5px;font-weight:600}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
th,td{{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:rgba(127,127,127,.07);font-size:12.5px;color:var(--mut);white-space:nowrap;cursor:pointer;user-select:none;font-weight:700}}
th.nos{{cursor:default}}
tr:last-child td{{border-bottom:0}}
tr.sel td{{background:rgba(37,99,235,.07)}}
tr.isdone td{{background:rgba(22,163,74,.06)}}
.ready{{margin-top:6px;font-size:12.5px;font-weight:700;color:var(--ok)}}
.ready a{{color:var(--ok)}}
td.c{{width:38px;text-align:center}}
input[type=checkbox]{{width:18px;height:18px;accent-color:var(--acc);cursor:pointer}}
.nm{{font-weight:700;font-size:15px}}
.nm a{{color:inherit;text-decoration:none}}
.nm a:hover{{color:var(--acc)}}
.sm{{color:var(--mut);font-size:12.5px;margin-top:3px}}
.sc{{font-weight:800;font-size:17px;color:var(--acc);text-align:center;width:52px}}
.tag{{display:inline-block;font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}}
.t-none{{background:rgba(220,38,38,.13);color:var(--bad)}}
.t-broken{{background:rgba(180,83,9,.15);color:var(--warn)}}
.t-social{{background:rgba(124,58,237,.14);color:var(--soft)}}
.t-unknown{{background:rgba(127,127,127,.16);color:var(--mut)}}
.t-live{{background:rgba(22,163,74,.14);color:var(--ok)}}
a.ph{{color:var(--acc);text-decoration:none;display:block;white-space:nowrap}}
a.ph:hover{{text-decoration:underline}}
.dock{{position:fixed;left:0;right:0;bottom:0;z-index:40;background:var(--card);border-top:1px solid var(--line);
 padding:13px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;transform:translateY(120%);transition:transform .25s cubic-bezier(.4,0,.2,1)}}
.dock.on{{transform:none}}
.dock b{{font-size:16px}}
.btn{{border:0;background:var(--acc);color:#fff;padding:12px 20px;border-radius:10px;font:inherit;font-weight:700;cursor:pointer;transition:.15s}}
.btn:hover{{opacity:.88}}
.btn.g{{background:transparent;color:var(--fg);border:1.5px solid var(--line)}}
.btn.done{{background:var(--ok)}}
.empty{{padding:44px;text-align:center;color:var(--mut)}}
.hint{{margin-top:22px;padding:18px 20px;background:var(--card);border:1px solid var(--line);border-radius:14px;color:var(--mut);font-size:14px}}
.hint h3{{color:var(--fg);font-size:16px;margin-bottom:8px}}
.hint ol{{margin:8px 0 0 19px;display:grid;gap:6px}}
@media(max-width:860px){{.hide{{display:none}}.panel{{position:static}}}}
</style>
</head>
<body><div class="wrap">
<h1>{title}</h1>
<p class="sub">Найдено <b>{total}</b> организаций. У каждой проверено, есть ли сайт и открывается ли он на самом деле.
Отметь галочками тех, кому хочешь сделать сайт, и нажми «Скопировать выбранные» — пришлёшь мне список, я соберу демо.
Сайтов уже сделано: <b>{made}</b> — они помечены зелёным и опущены в конец списка. Сканирование от {when}.</p>

<div class="panel">
  <div class="row">
    <input type="search" id="q" placeholder="Поиск по названию, категории или адресу…">
    <span class="lbl">Отзывов от</span><input type="number" id="minv" value="10" min="0" step="5">
    <span class="lbl">скор от</span><input type="number" id="mins" value="0" min="0" max="100" step="5">
  </div>
  <div class="row" id="chips"></div>
</div>

<table id="t">
  <thead><tr>
    <th class="nos"><input type="checkbox" id="all" title="Выбрать всё видимое"></th>
    <th data-k="s">Скор</th><th data-k="n">Бизнес</th><th data-k="b">Сайт</th>
    <th data-k="v">Отзывы</th><th>Контакты</th><th class="hide nos">Адрес и режим</th>
  </tr></thead>
  <tbody id="tb"></tbody>
</table>
<div class="empty" id="empty" hidden>Под фильтры никто не подошёл. Ослабь условия выше.</div>

<div class="hint">
  <h3>Что значат метки</h3>
  <ol>
    <li><b>Сайта нет вообще</b> — в карточке 2ГИС нет ни ссылки, ни соцсетей. Самый простой разговор.</li>
    <li><b>Сайт битый</b> — ссылка есть, но домен не открывается, там заглушка или парковка. Такой клиент уже платил за сайт и остался ни с чем.</li>
    <li><b>Только соцсети</b> — вместо сайта Telegram, ВК, WhatsApp или бесплатный конструктор.</li>
    <li><b>Проверить вручную</b> — сайт закрыт от автопроверки или нарисован скриптом. Открой ссылку сам, прежде чем звонить.</li>
    <li><b>Рабочий сайт есть</b> — открывается и наполнен. Показан для полноты, обычно мимо.</li>
  </ol>
</div>
</div>

<div class="dock" id="dock">
  <b><span id="cnt">0</span> выбрано</b>
  <button class="btn" id="copy">Скопировать выбранные</button>
  <button class="btn g" id="clear">Снять всё</button>
  <span class="lbl" id="tip">Список ляжет в буфер — вставь его мне в чат</span>
</div>

<script>
const DATA = {data};
const BUCKETS = {buckets};
const sel = new Set();
let sortKey = 's', sortDir = -1;
const active = new Set(['none','broken','social','unknown']);
let hideDone = false;

const chips = document.getElementById('chips');
BUCKETS.forEach(([k,label,hintText])=>{{
  const n = DATA.filter(d=>d.b===k).length;
  const b = document.createElement('button');
  b.className = 'chip' + (active.has(k)?' on':''); b.title = hintText;
  b.innerHTML = label + '<small>' + n + '</small>';
  b.onclick = ()=>{{ active.has(k)?active.delete(k):active.add(k); b.classList.toggle('on'); render(); }};
  chips.appendChild(b);
}});
const dn = DATA.filter(d=>d.done).length;
if(dn){{
  const b = document.createElement('button');
  b.className='chip'; b.title='Спрятать тех, по кому сайт уже сделан';
  b.innerHTML='Скрыть готовые<small>'+dn+'</small>';
  b.onclick=()=>{{ hideDone=!hideDone; b.classList.toggle('on',hideDone); render(); }};
  chips.appendChild(b);
}}

function visible(){{
  const q = document.getElementById('q').value.trim().toLowerCase();
  const minv = +document.getElementById('minv').value || 0;
  const mins = +document.getElementById('mins').value || 0;
  let rows = DATA.filter(d=>active.has(d.b) && d.v>=minv && d.s>=mins);
  if(hideDone) rows = rows.filter(d=>!d.done);
  if(q) rows = rows.filter(d=>(d.n+' '+d.c+' '+d.a).toLowerCase().includes(q));
  rows.sort((a,b)=>{{
    const x=a[sortKey], y=b[sortKey];
    const v = typeof x==='number' ? x-y : String(x).localeCompare(String(y),'ru');
    return sortDir*v;
  }});
  return rows;
}}

function render(){{
  const rows = visible(), tb = document.getElementById('tb');
  tb.innerHTML = rows.map(d=>{{
    const label = (BUCKETS.find(b=>b[0]===d.b)||[])[1] || d.b;
    const phones = d.p.map(p=>`<a class="ph" href="tel:${{p.replace(/[^+0-9]/g,'')}}">${{p}}</a>`).join('');
    const site = d.w ? `<div class="sm"><a class="ph" href="${{d.w}}" target="_blank" rel="noopener">${{d.w.replace(/^https?:\\/\\//,'').slice(0,34)}}</a></div>` : '';
    const done = d.done ? `<div class="ready">✓ сайт готов · <a href="../${{d.done}}/" target="_blank" rel="noopener">открыть</a></div>` : '';
    return `<tr data-u="${{d.u}}" class="${{sel.has(d.u)?'sel':''}}${{d.done?' isdone':''}}">
      <td class="c"><input type="checkbox" ${{sel.has(d.u)?'checked':''}}></td>
      <td class="sc">${{d.s}}</td>
      <td><div class="nm"><a href="${{d.u}}" target="_blank" rel="noopener">${{d.n}}</a></div><div class="sm">${{d.c}}</div></td>
      <td><span class="tag t-${{d.b}}">${{label}}</span><div class="sm">${{d.d}}</div>${{site}}${{done}}</td>
      <td><b>${{d.r||'—'}}</b> ★<div class="sm">${{d.v}} отз.</div></td>
      <td>${{phones}}<div class="sm">${{d.e||''}}</div></td>
      <td class="hide">${{d.a}}<div class="sm">${{d.h}}</div></td>
    </tr>`;
  }}).join('');
  document.getElementById('empty').hidden = rows.length>0;
  document.getElementById('all').checked = rows.length>0 && rows.every(d=>sel.has(d.u));
  updateDock();
}}

function updateDock(){{
  document.getElementById('cnt').textContent = sel.size;
  document.getElementById('dock').classList.toggle('on', sel.size>0);
}}

document.getElementById('tb').addEventListener('change', e=>{{
  if(e.target.type!=='checkbox') return;
  const tr = e.target.closest('tr'), u = tr.dataset.u;
  e.target.checked ? sel.add(u) : sel.delete(u);
  tr.classList.toggle('sel', e.target.checked);
  document.getElementById('all').checked = visible().every(d=>sel.has(d.u));
  updateDock();
}});

document.getElementById('all').addEventListener('change', e=>{{
  visible().forEach(d=> e.target.checked ? sel.add(d.u) : sel.delete(d.u));
  render();
}});

document.querySelectorAll('th[data-k]').forEach(th=>{{
  th.onclick = ()=>{{
    const k = th.dataset.k;
    sortDir = (k===sortKey) ? -sortDir : (k==='n'?1:-1);
    sortKey = k; render();
  }};
}});

['q','minv','mins'].forEach(id=>{{
  const el = document.getElementById(id);
  el.addEventListener(id==='q'?'input':'change', render);
}});

document.getElementById('clear').onclick = ()=>{{ sel.clear(); render(); }};

document.getElementById('copy').onclick = ()=>{{
  const picked = DATA.filter(d=>sel.has(d.u));
  const text = 'Сделай сайты по этим бизнесам:\\n\\n' + picked.map((d,i)=>
    `${{i+1}}. ${{d.n}} — ${{d.a}}\\n   ${{d.u}}\\n   ${{d.p.join(', ')}} · ${{d.r}}★ ${{d.v}} отз. · ${{d.d}}`
  ).join('\\n\\n');
  navigator.clipboard.writeText(text);
  const b = document.getElementById('copy');
  b.textContent = 'Скопировано — вставляй в чат'; b.classList.add('done');
  setTimeout(()=>{{ b.textContent='Скопировать выбранные'; b.classList.remove('done'); }}, 2200);
}};

render();
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="JSON с результатами sitebiz scan")
    ap.add_argument("--slug", required=True, help="папка внутри docs/, например nsk-auto")
    ap.add_argument("--title", required=True, help="заголовок страницы")
    args = ap.parse_args()

    leads = json.loads(Path(args.source).read_text(encoding="utf-8"))
    made = done_map()
    rows = [compact(x, made) for x in leads]
    # сделанные — вниз: они уже отработаны
    rows.sort(key=lambda x: (bool(x["done"]), -x["s"], -x["v"]))

    out_dir = ROOT / "docs" / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    page = PAGE.format(
        title=html.escape(args.title), total=len(rows),
        made=sum(1 for r in rows if r["done"]),
        when=f"{date.today():%d.%m.%Y}",
        data=json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        buckets=json.dumps(BUCKETS, ensure_ascii=False),
    )
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"{out_dir / 'index.html'}  {len(page) // 1024} КБ  ({len(rows)} лидов)")


if __name__ == "__main__":
    main()
