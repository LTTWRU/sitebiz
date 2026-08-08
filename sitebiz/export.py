"""Выгрузка списка лидов: CSV, JSON, Markdown, HTML-отчёт."""

import csv
import html
import json
from datetime import datetime
from pathlib import Path

from .leads import COLUMNS


def write(leads: list, path: str, title: str = "") -> str:
    """Записать лиды в файл, формат определяется расширением."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()

    if suffix == ".json":
        target.write_text(
            json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    elif suffix in (".md", ".markdown"):
        target.write_text(to_markdown(leads, title), encoding="utf-8")
    elif suffix in (".html", ".htm"):
        target.write_text(to_html(leads, title), encoding="utf-8")
    else:
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow([label for _, label in COLUMNS])
            for lead in leads:
                writer.writerow([lead.get(key, "") for key, _ in COLUMNS])

    return str(target)


def to_markdown(leads: list, title: str = "") -> str:
    keys = ["score", "name", "categories", "website_status_label", "rating",
            "reviews_count", "phones", "address", "url_2gis"]
    labels = dict(COLUMNS)
    lines = [f"# {title or 'Бизнесы без сайта'}", "",
             f"Найдено: **{len(leads)}** · {datetime.now():%d.%m.%Y %H:%M}", ""]
    lines.append("| " + " | ".join(labels[k] for k in keys) + " |")
    lines.append("|" + "---|" * len(keys))
    for lead in leads:
        cells = [str(lead.get(k, "")).replace("|", "/") for k in keys]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


_STATUS_CLASS = {"нет сайта": "bad", "нет нормального сайта": "warn", "сайт есть": "ok"}


def _short_schedule(schedule: str, limit: int = 90) -> str:
    """Обрезать расписание по границе дня, а не посреди «Сб: 10:00»."""
    if len(schedule) <= limit:
        return schedule
    cut = schedule[:limit].rsplit(";", 1)[0]
    return cut + " …"


def to_html(leads: list, title: str = "") -> str:
    rows = []
    for lead in leads:
        status = lead.get("website_status_label", "")
        badge = _STATUS_CLASS.get(status, "warn")
        phones = html.escape(lead.get("phones", ""))
        tel = phones.split(",")[0].strip()
        phone_cell = f"<a href='tel:{tel}'>{phones}</a>" if tel else ""
        rows.append(
            "<tr>"
            f"<td class='score'><b>{lead.get('score', 0)}</b></td>"
            f"<td><a href='{html.escape(lead.get('url_2gis', ''))}' target='_blank' rel='noopener'>"
            f"{html.escape(lead.get('name', ''))}</a>"
            f"<div class='sub'>{html.escape(lead.get('categories', ''))}</div></td>"
            f"<td><span class='badge {badge}'>{html.escape(status)}</span>"
            f"<div class='sub'>{html.escape(lead.get('website_note', ''))}</div></td>"
            f"<td>{html.escape(str(lead.get('rating', '')))}<div class='sub'>"
            f"{html.escape(str(lead.get('reviews_count', 0)))} отз.</div></td>"
            f"<td>{phone_cell}"
            f"<div class='sub'>{html.escape(lead.get('emails', ''))}</div></td>"
            f"<td>{html.escape(lead.get('address', ''))}"
            f"<div class='sub'>{html.escape(_short_schedule(lead.get('schedule', '')))}</div></td>"
            f"<td><button class='copy' data-url='{html.escape(lead.get('url_2gis', ''))}'>"
            "промпт</button></td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title or 'Лиды без сайта')}</title>
<style>
:root{{color-scheme:light dark;--bg:#0f1115;--card:#171a21;--line:#252a33;--fg:#e7eaf0;--mut:#9aa4b2;--acc:#5b8cff}}
:root{{--bad-bg:#3a1620;--bad-fg:#ff8ba0;--warn-bg:#3a2f14;--warn-fg:#ffcc66;--ok-bg:#14301f;--ok-fg:#6ee7a0}}
@media (prefers-color-scheme:light){{:root{{--bg:#f6f7f9;--card:#fff;--line:#e6e8ec;--fg:#12151a;--mut:#697386;
--bad-bg:#fde8ec;--bad-fg:#a11133;--warn-bg:#fdf1d6;--warn-fg:#8a5a00;--ok-bg:#e2f6ea;--ok-fg:#0f6b3c}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:32px 20px;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,Segoe UI,Roboto,Inter,sans-serif}}
.wrap{{max-width:1400px;margin:0 auto}}
h1{{font-size:26px;margin:0 0 6px}} .meta{{color:var(--mut);margin-bottom:20px}}
.tools{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}}
input,select{{background:var(--card);border:1px solid var(--line);color:var(--fg);
padding:10px 12px;border-radius:10px;font-size:14px}}
input{{flex:1;min-width:220px}}
table{{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:14px;overflow:hidden}}
th,td{{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:rgba(127,127,127,.08);font-size:13px;color:var(--mut);cursor:pointer;user-select:none;white-space:nowrap}}
tr:last-child td{{border-bottom:0}}
a{{color:var(--acc);text-decoration:none}} a:hover{{text-decoration:underline}}
.sub{{color:var(--mut);font-size:12.5px;margin-top:3px}}
.score{{font-size:17px;color:var(--acc)}}
.badge{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:600}}
.badge.bad{{background:var(--bad-bg);color:var(--bad-fg)}}
.badge.warn{{background:var(--warn-bg);color:var(--warn-fg)}}
.badge.ok{{background:var(--ok-bg);color:var(--ok-fg)}}
button.copy{{background:var(--acc);border:0;color:#fff;padding:8px 12px;border-radius:9px;
cursor:pointer;font-size:13px;white-space:nowrap}}
button.copy.done{{background:#2f9e63}}
</style></head><body><div class="wrap">
<h1>{html.escape(title or 'Лиды без сайта')}</h1>
<div class="meta">Найдено: <b>{len(leads)}</b> · {datetime.now():%d.%m.%Y %H:%M} ·
кнопка «промпт» копирует готовую команду для генерации сайта</div>
<div class="tools">
<input id="q" placeholder="Поиск по названию, категории, адресу…">
<select id="st"><option value="">Все статусы</option>
<option>нет сайта</option><option>нет нормального сайта</option><option>сайт есть</option></select>
</div>
<table id="t"><thead><tr>
<th data-n="1">Скор</th><th>Название</th><th>Сайт</th><th data-n="1">Рейтинг</th>
<th>Контакты</th><th>Адрес и режим</th><th></th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
</div>
<script>
const tb=document.querySelector('#t tbody');
const rows=[...tb.rows];
function apply(){{
  const q=document.getElementById('q').value.toLowerCase();
  const s=document.getElementById('st').value;
  rows.forEach(r=>{{
    const t=r.innerText.toLowerCase();
    const okQ=!q||t.includes(q);
    const okS=!s||r.cells[2].innerText.includes(s);
    r.style.display=okQ&&okS?'':'none';
  }});
}}
document.getElementById('q').oninput=apply;
document.getElementById('st').onchange=apply;
document.querySelectorAll('#t th').forEach((th,i)=>{{
  let asc=false;
  th.onclick=()=>{{
    asc=!asc;const num=th.dataset.n==='1';
    rows.sort((a,b)=>{{
      const x=a.cells[i].innerText.trim(),y=b.cells[i].innerText.trim();
      const v=num?(parseFloat(x)||0)-(parseFloat(y)||0):x.localeCompare(y,'ru');
      return asc?v:-v;
    }}).forEach(r=>tb.appendChild(r));
  }};
}});
document.querySelectorAll('button.copy').forEach(b=>{{
  b.onclick=()=>{{
    navigator.clipboard.writeText('python -m sitebiz prompt '+b.dataset.url);
    b.textContent='скопировано';b.classList.add('done');
    setTimeout(()=>{{b.textContent='промпт';b.classList.remove('done')}},1500);
  }};
}});
</script></body></html>
"""
