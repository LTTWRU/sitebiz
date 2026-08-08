#!/usr/bin/env python3
"""Сборщик демо-сайтов из описания бизнеса.

Один шаблон, разные палитры и наполнение — так делается поток демо.
Каждый бизнес описывается словарём SITES; на выходе — самодостаточный index.html.

    python tools/build_sites.py

Палитра подбирается под нишу: мойка и детейлинг — холодная и «глянцевая»,
техцентр — светлая и техничная, семейный автокомплекс — тёплая.
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# --------------------------------------------------------------------- палитры

THEMES = {
    "navy": {  # премиальная мойка / детейлинг
        "dark": True,
        "bg": "#080f1a", "bg2": "#0e1826", "bg3": "#152233", "line": "#22334a",
        "fg": "#e9f1fb", "mut": "#8fa3bd", "acc": "#22d3ee", "acc2": "#0891b2",
        "on_acc": "#04222b", "grad": "linear-gradient(135deg,#22d3ee,#3b82f6)",
    },
    "graphite": {  # автотехцентр, сильный и плотный
        "dark": True,
        "bg": "#101215", "bg2": "#181b20", "bg3": "#20242b", "line": "#2e343d",
        "fg": "#eceff3", "mut": "#98a1ad", "acc": "#ff6b1a", "acc2": "#e05500",
        "on_acc": "#fff4ec", "grad": "linear-gradient(135deg,#ff6b1a,#ff9500)",
    },
    "blueprint": {  # светлый техничный
        "dark": False,
        "bg": "#ffffff", "bg2": "#f4f6fa", "bg3": "#eaeef5", "line": "#dde3ec",
        "fg": "#0f1729", "mut": "#5b6880", "acc": "#1d4ed8", "acc2": "#1739a8",
        "on_acc": "#ffffff", "grad": "linear-gradient(135deg,#1d4ed8,#0ea5e9)",
    },
    "aqua": {  # светлый, свежий — вода и чистота
        "dark": False,
        "bg": "#ffffff", "bg2": "#f2f9fb", "bg3": "#e6f3f7", "line": "#d3e6ec",
        "fg": "#0c2028", "mut": "#4f6b76", "acc": "#0891b2", "acc2": "#0a7490",
        "on_acc": "#ffffff", "grad": "linear-gradient(135deg,#0891b2,#22c55e)",
    },
}

ICONS = {
    "wash": '<path d="M12 2s6 7.2 6 11a6 6 0 0 1-12 0c0-3.8 6-11 6-11Z"/>',
    "sparkle": '<path d="m12 2 2.2 6.4L21 11l-6.8 2.6L12 20l-2.2-6.4L3 11l6.8-2.6z"/>',
    "wheel": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v6m0 6v6M3 12h6m6 0h6"/>',
    "engine": '<path d="M4 9h3l2-3h6l2 3h3v7h-3l-2 3H9l-2-3H4z"/><circle cx="12" cy="12.5" r="2"/>',
    "scan": '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
    "shield": '<path d="M12 2 4 6v6c0 5 3.4 9.2 8 10 4.6-.8 8-5 8-10V6z"/><path d="m9 12 2 2 4-4"/>',
    "oil": '<path d="M5 20h14M7 20V9l5-5 5 5v11"/><path d="M10 13h4"/>',
    "brake": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.2"/><path d="M12 4v3m0 10v3M4 12h3m10 0h3"/>',
    "suspension": '<path d="M6 3v4M18 3v4M6 21v-4M18 21v-4"/><path d="M6 7c4 0 4 3 0 3s-4 3 0 3 4 3 0 3M18 7c-4 0-4 3 0 3s4 3 0 3-4 3 0 3"/>',
    "seat": '<path d="M6 20v-3h9v3M7 17V7a3 3 0 0 1 3-3h1a3 3 0 0 1 3 3v10M15 12h2a2 2 0 0 1 2 2v3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "coffee": '<path d="M17 8h2a3 3 0 0 1 0 6h-2"/><path d="M3 8h14v6a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5z"/><path d="M6 2v3M10 2v3M14 2v3"/>',
    "truck": '<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    "award": '<circle cx="12" cy="8" r="6"/><path d="m8.2 13.4-1.4 7.4L12 18l5.2 2.8-1.4-7.4"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9l-3.8 3.8Z"/>',
    "snow": '<path d="M12 2v20M4.2 7l15.6 10M19.8 7 4.2 17"/><path d="m9 4 3 2 3-2M9 20l3-2 3 2"/>',
}

TPL = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='{fav_bg}'/><text x='16' y='23' font-size='18' font-family='Georgia' text-anchor='middle' fill='{fav_fg}'>{letter}</text></svg>">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:{bg};--bg2:{bg2};--bg3:{bg3};--line:{line};--fg:{fg};--mut:{mut};
  --acc:{acc};--acc2:{acc2};--on-acc:{on_acc};--grad:{grad};
  --r:14px;--wrap:1180px;--ease:cubic-bezier(.4,0,.2,1);
  --s3:24px;--s4:40px;--s5:64px;--s6:96px}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;-webkit-font-smoothing:antialiased;overflow-x:hidden}}
img{{max-width:100%;display:block;height:auto}}
a{{color:inherit;text-decoration:none}}
.wrap{{max-width:var(--wrap);margin:0 auto;padding:0 20px}}
h1,h2,h3{{line-height:1.12;letter-spacing:-.022em;font-weight:800}}
h1{{font-size:clamp(32px,5.6vw,58px)}}
h2{{font-size:clamp(26px,4vw,40px);margin-bottom:var(--s3)}}
h3{{font-size:19px}}
section{{padding:var(--s6) 0}}
.lead{{color:var(--mut);font-size:clamp(16px,2vw,19px);max-width:62ch}}
.btn{{display:inline-flex;align-items:center;gap:9px;padding:15px 26px;border-radius:999px;font-weight:700;font-size:16px;border:1.5px solid transparent;cursor:pointer;transition:transform .18s var(--ease),background .18s,border-color .18s,color .18s}}
.btn:hover{{transform:translateY(-2px)}}
.btn-a{{background:var(--acc);color:var(--on-acc)}}
.btn-a:hover{{background:var(--acc2)}}
.btn-b{{border-color:var(--line);color:var(--fg)}}
.btn-b:hover{{border-color:var(--acc);color:var(--acc)}}
.ic{{width:19px;height:19px;flex:none;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}}
header{{position:sticky;top:0;z-index:60;background:{hdr_bg};backdrop-filter:blur(14px);border-bottom:1px solid transparent;transition:border-color .25s}}
header.on{{border-bottom-color:var(--line)}}
.nav{{display:flex;align-items:center;gap:var(--s3);padding:16px 0}}
.logo{{font-weight:800;font-size:18px;letter-spacing:-.02em;margin-right:auto;display:flex;align-items:center;gap:10px}}
.logo span{{color:var(--acc)}}
.dot{{width:9px;height:9px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.16);animation:pulse 2.4s infinite}}
@keyframes pulse{{50%{{box-shadow:0 0 0 8px rgba(34,197,94,0)}}}}
.nav a.lnk{{color:var(--mut);font-size:15px;font-weight:600;transition:color .18s}}
.nav a.lnk:hover{{color:var(--fg)}}
@media(max-width:900px){{.nav a.lnk{{display:none}}}}
.hero{{position:relative;min-height:min(86vh,760px);display:flex;align-items:center;padding:var(--s6) 0 var(--s5);overflow:hidden}}
.hero-bg{{position:absolute;inset:0;z-index:0}}
.hero-bg img{{width:100%;height:100%;object-fit:cover;{hero_filter}}}
.hero-bg::after{{content:"";position:absolute;inset:0;background:{hero_veil}}}
.hero .wrap{{position:relative;z-index:1}}
/* светлая тема: фото не фоном, а карточкой рядом — так оно читается, а не выцветает */
.hero.split{{min-height:0;padding:var(--s5) 0}}
.hero.split .hero-bg{{display:none}}
.hero.split .wrap{{display:grid;grid-template-columns:1.05fr .95fr;gap:var(--s5);align-items:center}}
.hero.split h1{{max-width:14ch}}
.shot{{position:relative;border-radius:22px;overflow:hidden;border:1px solid var(--line);
  box-shadow:0 26px 60px -22px rgba(15,23,41,.32);aspect-ratio:4/5}}
.shot img{{width:100%;height:100%;object-fit:cover}}
.shot figcaption{{position:absolute;left:14px;right:14px;bottom:14px;padding:11px 15px;border-radius:13px;
  background:rgba(255,255,255,.93);backdrop-filter:blur(8px);font-size:13.5px;color:var(--mut);font-weight:600}}
@media(max-width:900px){{.hero.split .wrap{{grid-template-columns:1fr;gap:var(--s4)}}
  .hero.split .stats{{order:3}} .shot{{aspect-ratio:16/10;order:2}}}}
.badge{{display:inline-flex;align-items:center;gap:9px;padding:8px 16px;border-radius:999px;background:{badge_bg};border:1px solid {badge_bd};color:var(--acc);font-size:14px;font-weight:700;margin-bottom:var(--s3)}}
.hero h1{{max-width:17ch;margin-bottom:var(--s3)}}
.hero h1 em{{font-style:normal;color:var(--acc)}}
.hero .lead{{margin-bottom:var(--s4)}}
.cta{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:var(--s5)}}
.stats{{display:flex;gap:var(--s4);flex-wrap:wrap;padding-top:var(--s3);border-top:1px solid var(--line)}}
.stat b{{display:block;font-size:clamp(23px,3.2vw,32px);font-weight:800;letter-spacing:-.03em;line-height:1.1}}
.stat span{{font-size:13.5px;color:var(--mut)}}
.stars{{color:var(--acc);letter-spacing:2px}}
.grid{{display:grid;gap:14px}}
.g3{{grid-template-columns:repeat(auto-fit,minmax(285px,1fr))}}
.g2{{grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}}
.card{{background:var(--bg2);border:1px solid var(--line);border-radius:var(--r);padding:26px;transition:transform .22s var(--ease),border-color .22s,box-shadow .22s}}
.card:hover{{transform:translateY(-3px);border-color:var(--acc);box-shadow:{card_shadow}}}
.card h3{{margin-bottom:9px}}
.card p{{color:var(--mut);font-size:15px}}
.ico{{width:42px;height:42px;border-radius:11px;background:{badge_bg};display:grid;place-items:center;margin-bottom:16px;color:var(--acc)}}
.ico svg{{width:21px;height:21px}}
.alt{{background:var(--bg2);border-block:1px solid var(--line)}}
.alt .card{{background:var(--bg3)}}
.rev{{background:var(--bg2);border:1px solid var(--line);border-radius:var(--r);padding:26px;display:flex;flex-direction:column;gap:14px}}
.rev p{{font-size:15.5px}}
.rev .who{{display:flex;align-items:center;gap:12px;margin-top:auto;padding-top:14px;border-top:1px solid var(--line)}}
.av{{width:38px;height:38px;border-radius:50%;background:var(--grad);display:grid;place-items:center;font-weight:800;color:#fff;flex:none;font-size:15px}}
.who b{{font-size:14.5px;display:block}}
.who small{{color:var(--mut);font-size:12.5px}}
.rating-box{{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;background:{badge_bg};border:1px solid {badge_bd};border-radius:var(--r);padding:22px 26px;margin-bottom:var(--s4)}}
.rating-box .big{{font-size:44px;font-weight:800;letter-spacing:-.03em;line-height:1;color:var(--acc)}}
.contact{{display:grid;grid-template-columns:1fr 1fr;gap:var(--s4);align-items:start}}
@media(max-width:860px){{.contact{{grid-template-columns:1fr}}}}
.info li{{list-style:none;display:flex;gap:14px;padding:16px 0;border-bottom:1px solid var(--line)}}
.info li:last-child{{border-bottom:0}}
.info .k{{color:var(--mut);font-size:13.5px;margin-bottom:3px}}
.info .v{{font-weight:600}}
.info .ic{{color:var(--acc);margin-top:3px}}
.sched{{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;font-size:15px}}
.sched span:nth-child(odd){{color:var(--mut)}}
.map{{border-radius:var(--r);overflow:hidden;border:1px solid var(--line);aspect-ratio:4/3;background:var(--bg2)}}
.map iframe{{width:100%;height:100%;border:0}}
form{{display:grid;gap:12px}}
label{{font-size:13.5px;color:var(--mut);font-weight:600}}
input,textarea{{width:100%;padding:14px 16px;border-radius:11px;background:var(--bg3);border:1.5px solid var(--line);color:var(--fg);font:inherit;font-size:15px;transition:border-color .18s}}
input:focus,textarea:focus{{outline:0;border-color:var(--acc)}}
input:user-invalid{{border-color:#ef4444}}
textarea{{resize:vertical;min-height:88px}}
.note{{font-size:12.5px;color:var(--mut);line-height:1.5}}
.sent{{display:none;background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.4);color:#16a34a;border-radius:11px;padding:14px 16px;font-size:15px;font-weight:600;margin-bottom:14px}}
.gal{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}
.gal img{{border-radius:var(--r);border:1px solid var(--line);aspect-ratio:4/3;object-fit:cover;width:100%;cursor:zoom-in;transition:transform .25s var(--ease)}}
.gal img:hover{{transform:scale(1.02)}}
dialog{{border:0;padding:0;background:transparent;max-width:min(94vw,1100px)}}
dialog::backdrop{{background:rgba(0,0,0,.86);backdrop-filter:blur(4px)}}
dialog img{{border-radius:var(--r);max-height:88vh;width:auto;margin:0 auto}}
footer{{border-top:1px solid var(--line);padding:var(--s4) 0 120px;color:var(--mut);font-size:14px}}
.fgrid{{display:flex;gap:var(--s3);flex-wrap:wrap;align-items:center;justify-content:space-between}}
footer a:hover{{color:var(--acc)}}
.bar{{position:fixed;left:0;right:0;bottom:0;z-index:70;display:none;gap:10px;padding:11px 14px;background:{hdr_bg};backdrop-filter:blur(14px);border-top:1px solid var(--line);transform:translateY(110%);transition:transform .3s var(--ease)}}
.bar.on{{transform:none}}
.bar .btn{{flex:1;justify-content:center;padding:14px 12px;font-size:15px}}
@media(max-width:760px){{.bar{{display:flex}}footer{{padding-bottom:96px}}}}
.rise{{opacity:0;transform:translateY(22px);transition:opacity .6s var(--ease),transform .6s var(--ease)}}
.rise.in{{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}.rise{{opacity:1;transform:none}}html{{scroll-behavior:auto}}}}
:focus-visible{{outline:2px solid var(--acc);outline-offset:3px;border-radius:4px}}
</style>
</head>
<body>
<header id="hdr"><div class="wrap nav">
  <div class="logo">{open_dot}{brand}</div>
  <a class="lnk" href="#services">Услуги</a>
  <a class="lnk" href="#why">Почему мы</a>
  <a class="lnk" href="#reviews">Отзывы</a>
  <a class="lnk" href="#contacts">Контакты</a>
  <a class="btn btn-a" href="tel:{tel_raw}">Позвонить</a>
</div></header>
<main>
<section class="hero{split}">
  <div class="hero-bg"><img src="{hero_img}" alt="{name}, {city}" fetchpriority="high"></div>
  <div class="wrap">
    <div>
      <div class="badge">{badge}</div>
      <h1>{h1}</h1>
      <p class="lead">{sub}</p>
      <div class="cta">
        <a class="btn btn-a" href="tel:{tel_raw}">{tel}</a>
        <a class="btn btn-b" href="#services">Услуги и цены</a>
      </div>
      <div class="stats">{stats}</div>
    </div>
    {shot}
  </div>
</section>

<section id="services"><div class="wrap">
  <h2 class="rise">{services_title}</h2>
  <p class="lead rise" style="margin-bottom:40px">{services_lead}</p>
  <div class="grid g3">{services}</div>
</div></section>

<section id="why" class="alt"><div class="wrap">
  <h2 class="rise">Почему к нам возвращаются</h2>
  <div class="grid g2">{why}</div>
</div></section>

{gallery}

<section id="reviews"><div class="wrap">
  <h2 class="rise">Что говорят клиенты</h2>
  <div class="rating-box rise">
    <div><div class="big">{rating}</div><div class="stars" style="font-size:18px">★★★★★</div></div>
    <div style="flex:1;min-width:200px">
      <b style="font-size:17px">{reviews_count} отзывов в 2ГИС</b>
      <p style="color:var(--mut);font-size:14.5px;margin-top:4px">Отзывы ниже настоящие, скопированы с карточки без правок.</p>
    </div>
    <a class="btn btn-b" href="{url2gis}" target="_blank" rel="noopener">Читать все</a>
  </div>
  <div class="grid g3">{reviews}</div>
</div></section>

<section id="contacts" class="alt"><div class="wrap">
  <h2 class="rise">Как доехать</h2>
  <div class="contact">
    <div class="rise">
      <ul class="info">
        <li><svg class="ic" viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          <div><div class="k">Адрес</div><div class="v">{addr}</div><div class="k" style="margin-top:4px">{district}, {city}</div></div></li>
        <li><svg class="ic" viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/></svg>
          <div><div class="k">Телефон</div>{phones}</div></li>
        {email_row}
        <li><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
          <div><div class="k">Режим работы</div><div class="sched">{sched}</div></div></li>
      </ul>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:24px">
        <a class="btn btn-a" href="{url2gis}" target="_blank" rel="noopener">Маршрут в 2ГИС</a>
        <a class="btn btn-b" href="https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto" target="_blank" rel="noopener">Маршрут в Яндексе</a>
      </div>
    </div>
    <div class="rise"><div class="map">
      <iframe loading="lazy" title="Карта: {addr}" src="https://yandex.ru/map-widget/v1/?ll={lon}%2C{lat}&z=17&pt={lon},{lat},pm2rdm"></iframe>
    </div></div>
  </div>
</div></section>

<section><div class="wrap" style="max-width:640px">
  <h2 class="rise" style="text-align:center">Оставьте заявку</h2>
  <p class="lead rise" style="text-align:center;margin:0 auto 32px">{form_lead}</p>
  <div class="sent" id="sent"></div>
  <form class="rise" id="frm" data-endpoint="" data-mail="{email}" novalidate>
    <div><label for="n">Как вас зовут</label><input id="n" name="name" required autocomplete="name" placeholder="Иван"></div>
    <div><label for="p">Телефон</label><input id="p" name="phone" type="tel" required autocomplete="tel" placeholder="+7 913 000-00-00"></div>
    <div><label for="m">Что нужно сделать (необязательно)</label><textarea id="m" name="message" placeholder="{form_ph}"></textarea></div>
    <button class="btn btn-a" type="submit" style="justify-content:center">Жду звонка</button>
    <p class="note">Нажимая кнопку, вы соглашаетесь на обработку своих контактов, чтобы мы могли перезвонить. Больше ни для чего они не используются.</p>
  </form>
</div></section>
</main>
<footer><div class="wrap fgrid">
  <div><div class="logo" style="margin-bottom:8px">{brand}</div><div>{addr}, {city} · {hours_short}</div></div>
  <div style="display:flex;gap:20px;flex-wrap:wrap">
    <a href="tel:{tel_raw}">{tel}</a>
    <a href="{url2gis}" target="_blank" rel="noopener">2ГИС</a>
  </div>
</div></footer>
<div class="bar" id="bar">
  <a class="btn btn-a" href="tel:{tel_raw}">Позвонить</a>
  <a class="btn btn-b" href="{url2gis}" target="_blank" rel="noopener">Маршрут</a>
</div>
<dialog id="lb"><img alt=""></dialog>
<script type="application/ld+json">{jsonld}</script>
<script>
const hdr=document.getElementById('hdr'),bar=document.getElementById('bar');
addEventListener('scroll',()=>{{hdr.classList.toggle('on',scrollY>10);bar.classList.toggle('on',scrollY>620)}},{{passive:true}});
const io=new IntersectionObserver(es=>es.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}}),{{threshold:.12,rootMargin:'0px 0px -60px'}});
document.querySelectorAll('.rise').forEach((el,i)=>{{el.style.transitionDelay=(i%3*70)+'ms';io.observe(el)}});
const lb=document.getElementById('lb');
document.querySelectorAll('.gal img').forEach(im=>im.addEventListener('click',()=>{{lb.querySelector('img').src=im.src;lb.querySelector('img').alt=im.alt;lb.showModal()}}));
lb?.addEventListener('click',()=>lb.close());
/* Заявка. Пока приём заявок не подключён — открывается почта.
   Чтобы заявки приходили автоматически: зарегистрируйтесь на formspree.io,
   создайте форму и вставьте её адрес в data-endpoint у <form>. Больше ничего менять не нужно. */
const frm=document.getElementById('frm'),sent=document.getElementById('sent');
frm.addEventListener('submit',async e=>{{
  e.preventDefault();
  if(!frm.reportValidity())return;
  const d=Object.fromEntries(new FormData(frm)),url=frm.dataset.endpoint,mail=frm.dataset.mail;
  if(url){{try{{const r=await fetch(url,{{method:'POST',headers:{{'Accept':'application/json'}},body:new FormData(frm)}});
    if(r.ok){{sent.textContent='Спасибо! Заявка принята, перезвоним в ближайшее время.';sent.style.display='block';frm.reset();return}}}}catch(_){{}}}}
  if(mail){{location.href='mailto:'+mail+'?subject='+encodeURIComponent('Заявка с сайта — '+d.name)
    +'&body='+encodeURIComponent('Имя: '+d.name+'\\nТелефон: '+d.phone+'\\nКомментарий: '+(d.message||'—'));
    sent.textContent='Открылось окно почты — отправьте письмо, и мы перезвоним.';}}
  else{{sent.textContent='Спасибо! Позвоните нам — так быстрее всего: {tel}';}}
  sent.style.display='block';
}});
</script>
</body>
</html>
"""


def esc(text):
    return html.escape(str(text), quote=True)


def render_services(items):
    out = []
    for it in items:
        icon = ICONS.get(it.get("icon", "wrench"), ICONS["wrench"])
        price = (
            f'<p style="color:var(--acc);font-weight:700;margin-top:12px">{esc(it["price"])}</p>'
            if it.get("price") else ""
        )
        out.append(
            f'<article class="card rise"><div class="ico">'
            f'<svg class="ic" viewBox="0 0 24 24">{icon}</svg></div>'
            f'<h3>{esc(it["title"])}</h3><p>{esc(it["text"])}</p>{price}</article>'
        )
    return "".join(out)


def render_why(items):
    return "".join(
        f'<article class="card rise"><h3>{esc(t)}</h3><p>{esc(x)}</p></article>'
        for t, x in items
    )


def render_reviews(items, url2gis, total):
    out = []
    for r in items:
        stars = "★" * int(r.get("rating", 5))
        out.append(
            f'<article class="rev rise"><div class="stars">{stars}</div>'
            f'<p>«{esc(r["text"])}»</p><div class="who"><div class="av">{esc(r["author"][0])}</div>'
            f'<div><b>{esc(r["author"])}</b><small>{esc(r["date"])}</small></div></div></article>'
        )
    out.append(
        f'<article class="rev rise" style="justify-content:center;border-style:dashed">'
        f'<h3>Ещё {total - len(items)} отзывов</h3>'
        f'<p style="color:var(--mut)">Мы не прячем и те, где нами были недовольны. Читайте всё как есть.</p>'
        f'<a class="btn btn-b" style="align-self:flex-start" href="{url2gis}" target="_blank" rel="noopener">Смотреть в 2ГИС</a></article>'
    )
    return "".join(out)


def render_stats(items):
    return "".join(
        f'<div class="stat"><b>{esc(b)}</b><span>{esc(s)}</span></div>' for b, s in items
    )


def render_gallery(photos, name):
    if not photos:
        return ""
    imgs = "".join(
        f'<img src="{p}" alt="{esc(name)} — фото {i}" loading="lazy" decoding="async">'
        for i, p in enumerate(photos, 1)
    )
    return (
        '<section><div class="wrap"><h2 class="rise">Как у нас</h2>'
        '<p class="lead rise" style="margin-bottom:40px">Настоящие фото, а не стоки: '
        'снято клиентами и выложено в карточке 2ГИС.</p>'
        f'<div class="gal rise">{imgs}</div></div></section>'
    )


def build(spec):
    theme = THEMES[spec["theme"]]
    dark = theme["dark"]
    acc = theme["acc"]
    rgb = tuple(int(acc.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    badge_bg = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{'.12' if dark else '.09'})"
    badge_bd = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},.3)"

    slug = spec["slug"]
    out_dir = DOCS / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    photos = sorted(p.name for p in (out_dir / "img").glob("*.jpg")) if (out_dir / "img").exists() else []
    hero_img = f"img/{photos[0]}" if photos else ""
    gallery_photos = [f"img/{p}" for p in photos[1:]]

    phones_html = "".join(
        f'<a class="v" href="tel:{re.sub(r"[^+0-9]", "", p)}" style="display:block">{esc(p)}</a>'
        for p in spec["phones"]
    )
    email_row = ""
    if spec.get("email"):
        email_row = (
            '<li><svg class="ic" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/>'
            '<path d="m2 7 10 6 10-6"/></svg><div><div class="k">Почта</div>'
            f'<a class="v" href="mailto:{spec["email"]}">{esc(spec["email"])}</a></div></li>'
        )
    sched = "".join(f"<span>{esc(d)}</span><span class='v'>{esc(h)}</span>" for d, h in spec["sched"])

    jsonld = {
        "@context": "https://schema.org", "@type": spec.get("schema_type", "AutoRepair"),
        "name": spec["name"], "description": spec["desc"],
        "telephone": re.sub(r"[^+0-9]", "", spec["phones"][0]),
        "address": {"@type": "PostalAddress", "streetAddress": spec["addr"],
                    "addressLocality": spec["city"], "addressRegion": "Новосибирская область",
                    "addressCountry": "RU"},
        "geo": {"@type": "GeoCoordinates", "latitude": spec["lat"], "longitude": spec["lon"]},
        "openingHoursSpecification": spec["hours_ld"],
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": str(spec["rating"]),
                            "reviewCount": str(spec["reviews_count"]), "bestRating": "5"},
        "sameAs": [spec["url2gis"]],
        "review": [{"@type": "Review", "author": {"@type": "Person", "name": r["author"]},
                    "reviewRating": {"@type": "Rating", "ratingValue": str(r.get("rating", 5))},
                    "reviewBody": r["text"]} for r in spec["reviews"][:3]],
    }
    if hero_img:
        jsonld["image"] = hero_img
    if spec.get("email"):
        jsonld["email"] = spec["email"]

    hdr_bg = "rgba(8,15,26,.86)" if dark else "rgba(255,255,255,.88)"
    if spec["theme"] == "graphite":
        hdr_bg = "rgba(16,18,21,.86)"

    html_out = TPL.format(
        title=esc(spec["title"]), desc=esc(spec["desc"]), ogtitle=esc(spec.get("ogtitle", spec["title"])),
        fav_bg=theme["bg"].replace("#", "%23"), fav_fg=acc.replace("#", "%23"),
        letter=esc(spec["name"][0]),
        bg=theme["bg"], bg2=theme["bg2"], bg3=theme["bg3"], line=theme["line"],
        fg=theme["fg"], mut=theme["mut"], acc=acc, acc2=theme["acc2"],
        on_acc=theme["on_acc"], grad=theme["grad"],
        hdr_bg=hdr_bg, badge_bg=badge_bg, badge_bd=badge_bd,
        card_shadow="0 12px 32px rgba(0,0,0,.35)" if dark else "0 12px 30px rgba(15,23,41,.10)",
        hero_filter="filter:saturate(1.05) contrast(1.03)" if not dark else "filter:grayscale(.25) contrast(1.05)",
        hero_veil=(
            f"linear-gradient(100deg,{theme['bg']} 20%,{theme['bg']}e6 50%,{theme['bg']}8c 100%)"
            if dark else
            f"linear-gradient(100deg,{theme['bg']} 18%,{theme['bg']}f2 48%,{theme['bg']}b3 100%)"
        ),
        split="" if dark else " split",
        shot=(
            "" if dark or not hero_img else
            f'<figure class="shot rise"><img src="{hero_img}" alt="{esc(spec["name"])}, {esc(spec["city"])}" '
            f'fetchpriority="high"><figcaption>{esc(spec["shot_caption"])}</figcaption></figure>'
        ),
        open_dot='<span class="dot" aria-hidden="true"></span>' if spec.get("open_now") else "",
        brand=spec["brand_html"], name=esc(spec["name"]), city=esc(spec["city"]),
        hero_img=hero_img, badge=esc(spec["badge"]), h1=spec["h1_html"], sub=esc(spec["sub"]),
        tel=esc(spec["phones"][0]), tel_raw=re.sub(r"[^+0-9]", "", spec["phones"][0]),
        stats=render_stats(spec["stats"]),
        services_title=esc(spec["services_title"]), services_lead=esc(spec["services_lead"]),
        services=render_services(spec["services"]), why=render_why(spec["why"]),
        gallery=render_gallery(gallery_photos, spec["name"]),
        rating=spec["rating"], reviews_count=spec["reviews_count"],
        reviews=render_reviews(spec["reviews"], spec["url2gis"], spec["reviews_count"]),
        url2gis=spec["url2gis"], addr=esc(spec["addr"]), district=esc(spec["district"]),
        phones=phones_html, email_row=email_row, email=spec.get("email", ""),
        sched=sched, lat=spec["lat"], lon=spec["lon"],
        hours_short=esc(spec["hours_short"]),
        form_lead=esc(spec["form_lead"]), form_ph=esc(spec["form_ph"]),
        jsonld=json.dumps(jsonld, ensure_ascii=False),
    )
    (out_dir / "index.html").write_text(html_out, encoding="utf-8")
    return out_dir / "index.html"


def main():
    from site_specs import SITES
    for spec in SITES:
        path = build(spec)
        print(f"{path}  {path.stat().st_size // 1024} КБ")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
