#!/usr/bin/env python3
"""Приводит сайты к требованиям 152-ФЗ.

Для каждого сайта из registry.json:
  1. создаёт страницу privacy/ — «Политика обработки персональных данных»,
     оформленную в палитре и шрифтах самого сайта;
  2. патчит index.html:
     — ссылка на политику в подвале;
     — чекбокс согласия в форме (не отмечен по умолчанию, кнопка заблокирована);
     — отдельный необязательный чекбокс на рекламные сообщения;
     — баннер о cookie с равноправными «Принять» и «Отклонить»;
     — карта Яндекса грузится только после согласия или по клику.

Скрипт идемпотентен: повторный запуск ничего не дублирует.

Реквизиты оператора берутся из поля "operator" в registry.json:
    "operator": {"name": "ООО «Ромашка»", "inn": "5400000000",
                 "ogrn": "1145400000000", "address": "630000, Новосибирск, ...",
                 "email": "privacy@example.ru"}
Если поля нет, в политике остаются прочерки и служебная плашка о том,
что реквизиты вписываются при передаче сайта владельцу.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

MARK_STYLE = "/* --- 152-ФЗ --- */"
MARK_FOOT = 'href="privacy/"'
MARK_COOKIE = 'id="ck"'


# ---------------------------------------------------------------- разбор темы

def theme(html: str) -> dict:
    """Достаёт из сайта его собственные цвета и шрифты."""
    root = re.search(r":root\s*\{(.*?)\}", html, re.S)
    varmap = {}
    if root:
        for name, val in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", root.group(1)):
            varmap[name] = val.strip()

    def resolve(value: str, depth: int = 0) -> str:
        value = value.strip()
        m = re.fullmatch(r"var\(--([\w-]+)\)", value)
        if m and depth < 5:
            return resolve(varmap.get(m.group(1), "#111"), depth + 1)
        return value

    body = re.search(r"\bbody\s*\{(.*?)\}", html, re.S)
    body_css = body.group(1) if body else ""
    bg = re.search(r"background\s*:\s*([^;]+);", body_css)
    fg = re.search(r"color\s*:\s*([^;]+);", body_css)
    font = re.search(r"font\s*:\s*[^;]*?/[\d.]+\s+([^;]+);", body_css)

    head = re.search(r"h1,h2,h3\s*\{[^}]*?font-family\s*:\s*([^;}]+)", html) \
        or re.search(r"h1,h2\s*\{[^}]*?font-family\s*:\s*([^;}]+)", html)

    acc = re.search(r"\.(?:tag|eyebrow)\s*\{[^}]*?color\s*:\s*([^;}]+)", html)

    fonts = re.findall(r'<link rel="stylesheet" href="\.\./fonts/([\w-]+)\.css">', html)

    return {
        "bg": resolve(bg.group(1)) if bg else "#ffffff",
        "fg": resolve(fg.group(1)) if fg else "#111111",
        "acc": resolve(acc.group(1)) if acc else "#333333",
        "body_font": (font.group(1).strip() if font else "system-ui, sans-serif"),
        "head_font": (head.group(1).strip() if head else "Georgia, serif"),
        "fonts": fonts,
    }


def mix(color: str, ratio: float, toward: str) -> str:
    """Приблизительное смешивание hex-цвета с белым или чёрным."""
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", color.strip())
    if not m:
        return color
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    t = 255 if toward == "light" else 0
    r, g, b = (round(c + (t - c) * ratio) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


# ------------------------------------------------------------------ политика

SECTIONS = [
    ("Общие положения", """Настоящая Политика определяет порядок обработки персональных данных
и меры по обеспечению их безопасности при использовании сайта {host}. Политика составлена
в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных»
и применяется ко всем сведениям, которые Оператор может получить о посетителях сайта."""),

    ("Оператор персональных данных", "__OPERATOR__"),

    ("Основные понятия", """Персональные данные — любая информация, относящаяся к прямо или
косвенно определённому физическому лицу. Обработка персональных данных — любое действие
с ними: сбор, запись, хранение, уточнение, использование, передача, удаление.
Субъект персональных данных — посетитель сайта, оставивший свои данные."""),

    ("Какие данные мы обрабатываем", """Через форму записи на сайте: имя, номер телефона,
адрес электронной почты (если вы его указали), марка и модель автомобиля, текст обращения.
Автоматически при посещении сайта: обезличенные технические данные — IP-адрес, тип браузера
и устройства, дата и время обращения. Мы не обрабатываем специальные категории персональных
данных и биометрические персональные данные."""),

    ("Цели обработки", """Обработка производится исключительно для того, чтобы связаться с вами
по оставленной заявке, согласовать время визита, состав и стоимость работ, а также ответить
на ваш вопрос. С вашего отдельного согласия — для направления сообщений об акциях
и напоминаний о плановом обслуживании."""),

    ("Правовые основания обработки", """Согласие субъекта персональных данных на обработку своих
персональных данных (пункт 1 части 1 статьи 6 Федерального закона № 152-ФЗ), а также договор,
стороной которого является субъект персональных данных. Согласие даётся путём проставления
отметки в форме на сайте и может быть отозвано в любой момент."""),

    ("Порядок и сроки обработки", """Обработка ведётся с использованием средств автоматизации
и без них. Персональные данные хранятся не дольше, чем этого требуют цели их обработки,
но не более трёх лет с момента последнего обращения, если иной срок не установлен законом.
Базы данных, содержащие персональные данные граждан Российской Федерации, размещаются
на территории Российской Федерации."""),

    ("Передача третьим лицам", """Оператор не продаёт и не передаёт персональные данные третьим
лицам, кроме случаев, прямо предусмотренных законодательством Российской Федерации,
и кроме привлечённых по поручению Оператора лиц, обеспечивающих работу сайта и приём заявок
(хостинг-провайдер, сервис приёма заявок), которые обязаны соблюдать конфиденциальность."""),

    ("Трансграничная передача", """Трансграничная передача персональных данных не осуществляется.
На сайте не используются иностранные сервисы веб-аналитики и рекламные счётчики.
Шрифты размещены на том же сервере, что и сайт, и не загружаются со сторонних ресурсов."""),

    ("Файлы cookie", """Сайт использует технически необходимые файлы cookie, без которых
невозможна корректная работа страницы, а также cookie, которые устанавливает виджет карты
«Яндекс.Карты». Виджет карты загружается только после вашего согласия или по вашему явному
действию. Вы можете отказаться от необязательных cookie в баннере при первом посещении,
а также очистить или запретить cookie в настройках браузера."""),

    ("Меры по защите данных", """Оператор принимает правовые, организационные и технические меры
для защиты персональных данных от неправомерного доступа, уничтожения, изменения,
блокирования и распространения: доступ к данным имеют только уполномоченные сотрудники,
передача данных с сайта осуществляется по защищённому протоколу HTTPS."""),

    ("Права субъекта персональных данных", """Вы вправе получить сведения об обработке ваших
персональных данных, потребовать уточнения, блокирования или уничтожения данных, если они
неполны, устарели, неточны или получены незаконно, а также отозвать согласие на обработку.
Для этого направьте обращение по адресу, указанному в разделе «Оператор персональных данных».
Ответ будет дан в срок, установленный законодательством."""),

    ("Отзыв согласия", """Согласие на обработку персональных данных может быть отозвано в любой
момент письменным обращением к Оператору. После отзыва согласия Оператор прекращает обработку
и уничтожает персональные данные в срок, не превышающий тридцати дней, за исключением случаев,
когда закон обязывает продолжить хранение."""),

    ("Действия при утечке", """В случае неправомерной передачи персональных данных Оператор
уведомляет уполномоченный орган по защите прав субъектов персональных данных в течение
двадцати четырёх часов с момента выявления инцидента и принимает меры по устранению
его последствий."""),

    ("Обращения и жалобы", """По всем вопросам, связанным с обработкой персональных данных,
обращайтесь к Оператору по контактам, указанным выше. Вы также вправе обратиться
в Роскомнадзор — уполномоченный орган по защите прав субъектов персональных данных."""),

    ("Изменения Политики", """Оператор вправе вносить изменения в настоящую Политику.
Действующая редакция всегда размещена на этой странице. Существенные изменения
доводятся до сведения посетителей сайта."""),
]


def operator_block(op: dict | None, site: dict) -> str:
    if op:
        rows = [
            ("Наименование", op.get("name", "—")),
            ("ИНН", op.get("inn", "—")),
            ("ОГРН / ОГРНИП", op.get("ogrn", "—")),
            ("Адрес", op.get("address", "—")),
            ("Телефон", " · ".join(site.get("phones", [])) or "—"),
            ("Электронная почта для обращений", op.get("email") or site.get("email") or "—"),
        ]
    else:
        rows = [
            ("Наименование", "—"),
            ("ИНН", "—"),
            ("ОГРН / ОГРНИП", "—"),
            ("Адрес", "—"),
            ("Телефон", " · ".join(site.get("phones", [])) or "—"),
            ("Электронная почта для обращений", site.get("email") or "—"),
        ]
    body = "".join(
        f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows
    )
    return f'<dl class="req">{body}</dl>'


PRIVACY_TPL = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Политика обработки персональных данных — {name}</title>
<meta name="description" content="Политика обработки персональных данных сайта {name}, {addr}.">
<meta name="robots" content="noindex,nofollow">
{fontlinks}
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:{bg};--fg:{fg};--fg2:{fg2};--fg3:{fg3};--acc:{acc};--line:{line};--card:{card}}}
html{{-webkit-text-size-adjust:100%}}
body{{background:var(--bg);color:var(--fg);font:400 16.5px/1.75 {body_font};
  -webkit-font-smoothing:antialiased}}
a{{color:inherit}}
.w{{max-width:800px;margin:0 auto;padding:0 26px}}
header{{padding:34px 0;border-bottom:1px solid var(--line)}}
.back{{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--acc);
  text-decoration:none}}
.back:hover{{text-decoration:underline}}
h1{{font-family:{head_font};font-weight:600;font-size:clamp(27px,4vw,44px);line-height:1.14;
  letter-spacing:-.02em;margin:44px 0 14px;text-wrap:balance}}
h2{{font-family:{head_font};font-weight:600;font-size:clamp(19px,2.2vw,25px);line-height:1.26;
  letter-spacing:-.015em;margin:38px 0 12px}}
p{{margin-bottom:14px;color:var(--fg2)}}
.meta{{font-size:14px;color:var(--fg3)}}
.draft{{margin:26px 0 0;padding:15px 18px;border:1px dashed var(--acc);font-size:14.5px;
  line-height:1.6;color:var(--fg2)}}
.num{{counter-reset:s}}
.num section{{counter-increment:s}}
.num h2::before{{content:counter(s) ". ";color:var(--acc)}}
.req{{margin:8px 0 6px;border-top:1px solid var(--line)}}
.req>div{{display:grid;grid-template-columns:290px 1fr;gap:16px;padding:12px 0;
  border-bottom:1px solid var(--line);font-size:15.5px}}
.req dt{{color:var(--fg3);font-size:13.5px;padding-top:3px}}
@media(max-width:600px){{.req>div{{grid-template-columns:1fr;gap:3px}}}}
footer{{margin-top:56px;padding:26px 0 60px;border-top:1px solid var(--line);
  font-size:14px;color:var(--fg3)}}
footer a{{color:var(--acc)}}
:focus-visible{{outline:2px solid var(--acc);outline-offset:3px}}
</style>
</head>
<body>
<header><div class="w"><a class="back" href="../">← {name}</a></div></header>
<main class="w">
  <h1>Политика обработки персональных данных</h1>
  <p class="meta">Редакция от {date} · сайт {host}</p>
  {draft}
  <div class="num">
{sections}
  </div>
</main>
<footer><div class="w">
  {name} · {addr}<br>
  <a href="../">Вернуться на сайт</a>
</div></footer>
</body>
</html>
"""

DRAFT_NOTE = """<p class="draft"><b>Черновик.</b> Реквизиты оператора — наименование юридического
лица или ИП, ИНН, ОГРН и юридический адрес — вписываются при передаче сайта владельцу.
До этого момента документ носит демонстрационный характер.</p>"""


def build_privacy(site: dict, html: str, date: str) -> str:
    t = theme(html)
    host = f"lttwru.github.io/sitebiz/{site['slug']}/"
    op = site.get("operator")
    parts = []
    for title, text in SECTIONS:
        if text == "__OPERATOR__":
            inner = operator_block(op, site)
        else:
            body = text.format(host=host).replace("\n", " ")
            body = re.sub(r"\s+", " ", body).strip()
            inner = f"<p>{body}</p>"
        parts.append(f"    <section>\n      <h2>{title}</h2>\n      {inner}\n    </section>")

    light = _is_light(t["bg"])
    return PRIVACY_TPL.format(
        name=site["name"],
        addr=site.get("meta", ""),
        host=host,
        date=date,
        bg=t["bg"], fg=t["fg"],
        fg2=mix(t["fg"], .26, "light" if not light else "light"),
        fg3=mix(t["fg"], .48, "light"),
        acc=t["acc"],
        line=mix(t["fg"], .84, "light") if light else mix(t["fg"], .80, "dark"),
        card=mix(t["bg"], .04, "dark" if light else "light"),
        body_font=t["body_font"],
        head_font=t["head_font"],
        fontlinks="\n".join(
            f'<link rel="stylesheet" href="../../fonts/{f}.css">' for f in t["fonts"]),
        draft="" if op else DRAFT_NOTE,
        sections="\n".join(parts),
    )


def _is_light(hexcolor: str) -> bool:
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", hexcolor.strip())
    if not m:
        return True
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) > 128


# -------------------------------------------------------------------- патчи

CSS = """
/* --- 152-ФЗ: согласие, cookie, отложенная карта --- */
.agree{display:grid;grid-template-columns:19px 1fr;gap:12px;align-items:start;
  font:400 13.5px/1.55 inherit;font-family:inherit;letter-spacing:normal;text-transform:none;
  color:inherit;margin:0;cursor:pointer;max-width:52ch}
.agree span{display:block;letter-spacing:normal;text-transform:none}
.agree input{width:19px;height:19px;margin:2px 0 0;accent-color:currentColor;cursor:pointer;flex:none}
.agree a{color:inherit;text-decoration:underline;text-underline-offset:2px}
.agree.opt{opacity:.8}
button[disabled],.btn[disabled]{opacity:.4;cursor:not-allowed}
.mapstub{position:absolute;inset:0;display:flex;flex-direction:column;gap:12px;
  align-items:center;justify-content:center;text-align:center;padding:22px;
  font-size:13.5px;line-height:1.5;background:rgba(127,127,127,.10)}
.mapstub button{font:inherit;font-size:13px;padding:11px 20px;cursor:pointer;
  border:1px solid currentColor;background:transparent;color:inherit;border-radius:3px}
.mapstub button:hover{opacity:.72}
.map{position:relative}
#ck{position:fixed;left:16px;right:16px;bottom:16px;z-index:95;display:none;max-width:440px;
  padding:18px 20px;background:#101114;color:#F2F0EC;font-size:13.5px;line-height:1.6;
  border:1px solid rgba(255,255,255,.14);border-radius:6px;
  box-shadow:0 18px 48px rgba(0,0,0,.45)}
#ck.on{display:block}
#ck a{color:#fff;text-decoration:underline;text-underline-offset:2px}
#ck .ckb{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
#ck button{font:inherit;font-size:12.5px;font-weight:600;letter-spacing:.04em;padding:11px 20px;
  cursor:pointer;border-radius:4px;border:1px solid rgba(255,255,255,.3);
  background:transparent;color:#F2F0EC}
#ck button.y{background:#F2F0EC;color:#101114;border-color:#F2F0EC}
#ck button:hover{opacity:.85}
@media(max-width:760px){#ck{bottom:84px;left:10px;right:10px}}
"""

COOKIE_HTML = """
<div id="ck" role="dialog" aria-label="Файлы cookie">
  Мы используем файлы cookie: технически необходимые для работы страницы и те, что
  устанавливает виджет «Яндекс.Карт». Аналитику и рекламные счётчики без вашего согласия
  не подключаем. Подробности — в <a href="privacy/">Политике обработки персональных данных</a>.
  <div class="ckb">
    <button class="y" type="button" data-ck="y">Принять</button>
    <button type="button" data-ck="n">Отклонить</button>
  </div>
</div>
"""

COOKIE_JS = """
(function(){
  var K='ck-choice', box=document.getElementById('ck');
  function loadMap(){
    document.querySelectorAll('.mapstub[data-src]').forEach(function(s){
      var f=document.createElement('iframe');
      f.loading='lazy'; f.title=s.dataset.title||'Карта проезда'; f.src=s.dataset.src;
      f.style.width='100%'; f.style.height='100%'; f.style.border='0';
      s.parentNode.appendChild(f); s.remove();
    });
  }
  var saved=null; try{saved=localStorage.getItem(K)}catch(e){}
  if(saved==='y'){loadMap()} else if(!saved && box){box.classList.add('on')}
  if(box) box.addEventListener('click',function(e){
    var b=e.target.closest('[data-ck]'); if(!b)return;
    try{localStorage.setItem(K,b.dataset.ck)}catch(e){}
    box.classList.remove('on'); if(b.dataset.ck==='y') loadMap();
  });
  document.addEventListener('click',function(e){
    if(e.target.closest('.mapstub button')) loadMap();
  });
  var ag=document.getElementById('ag'), sb=document.getElementById('sb');
  if(ag&&sb){ var sync=function(){sb.disabled=!ag.checked}; sync();
    ag.addEventListener('change',sync); }
})();
"""

AGREE_HTML = """        <label class="agree"><input type="checkbox" id="ag" name="consent" required>
          <span>Я даю согласие на обработку моих персональных данных в соответствии
          с <a href="privacy/" target="_blank" rel="noopener">Политикой обработки персональных данных</a></span></label>
        <label class="agree opt"><input type="checkbox" id="adv" name="ads">
          <span>Хочу получать напоминания о плановом обслуживании и сообщения об акциях
          (необязательно)</span></label>
"""

FINE_NEW = """<p class="fine">Заявку обрабатываем только для того, чтобы перезвонить
          и записать вас на удобное время. Согласие можно отозвать в любой момент —
          порядок описан в <a href="privacy/">политике</a>.</p>"""


def patch(html: str) -> tuple[str, list[str]]:
    done = []

    # 1. стили
    if MARK_STYLE not in html:
        html = html.replace("</style>", MARK_STYLE + CSS + "</style>", 1)
        done.append("css")

    # 2. ссылка в подвале
    if MARK_FOOT not in html.split("<footer")[-1]:
        idx = html.rfind(">2ГИС</a>")
        if idx != -1:
            end = idx + len(">2ГИС</a>")
            html = (html[:end]
                    + '\n    <a href="privacy/">Политика обработки персональных данных</a>'
                    + html[end:])
            done.append("footer")

    # 3. чекбоксы + блокировка кнопки (кнопка бывает .btn или .act, с id и без)
    if 'id="ag"' not in html:
        m = re.search(
            r'([ \t]*)(<button [^>]*class="(?:btn|act)"[^>]*type="submit"[^>]*>)', html)
        if m:
            indent, tag = m.group(1), m.group(2)
            newtag = tag
            if 'id="sb"' not in newtag:
                newtag = newtag.replace("<button ", '<button id="sb" ', 1)
            if "disabled" not in newtag:
                newtag = newtag[:-1] + " disabled>"
            html = html.replace(m.group(0), AGREE_HTML + indent + newtag, 1)
            done.append("consent")

    # 4. новая формулировка под формой (текст на разных сайтах свой)
    m = re.search(r'<p class="fine">(?!Заявку обрабатываем).*?</p>', html, re.S)
    if m:
        html = html.replace(m.group(0), FINE_NEW, 1)
        done.append("fine")

    # 5. отложенная карта
    m = re.search(r'<iframe loading="lazy" title="([^"]+)"\s*\n?\s*src="([^"]+)"></iframe>', html)
    if m:
        title, src = m.group(1), m.group(2)
        stub = (f'<div class="mapstub" data-src="{src}" data-title="{title}">'
                f'\n          <span>Карта загружается с сервера «Яндекса» и устанавливает свои cookie.</span>'
                f'\n          <button type="button">Показать карту</button>\n        </div>')
        html = html.replace(m.group(0), stub, 1)
        done.append("map")

    # 6. баннер и скрипт
    if MARK_COOKIE not in html:
        html = html.replace("</main>", "</main>\n" + COOKIE_HTML, 1)
        html = html.replace("</body>", f"<script>{COOKIE_JS}</script>\n</body>", 1)
        done.append("cookie")

    return html, done


# --------------------------------------------------------------------- main

def main() -> None:
    reg = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    from datetime import date
    today = date.today().strftime("%d.%m.%Y")

    changed = 0
    for site in reg["sites"]:
        page = DOCS / site["slug"] / "index.html"
        if not page.exists():
            print(f"  ! нет файла: {site['slug']}")
            continue
        html = page.read_text(encoding="utf-8")

        pdir = page.parent / "privacy"
        pdir.mkdir(exist_ok=True)
        (pdir / "index.html").write_text(build_privacy(site, html, today), encoding="utf-8")

        new, done = patch(html)
        if new != html:
            page.write_text(new, encoding="utf-8")
            changed += 1
        print(f"  {site['slug']:32} политика + {', '.join(done) if done else 'уже было'}")

    print(f"\nобновлено страниц: {changed}, политик: {len(reg['sites'])}")


if __name__ == "__main__":
    main()
