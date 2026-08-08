"""Проверка того, что «сайт есть» — это правда работающий сайт.

Наличие ссылки в карточке 2ГИС ничего не гарантирует: домен мог протухнуть,
на нём может висеть парковка регистратора или страница «сайт в разработке».
Такой бизнес — тёплый лид: он уже понимает ценность сайта и один раз за него
платил, но остался ни с чем.
"""

import concurrent.futures
import gzip
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib

from . import config

# Статусы живости
DEAD = "dead"        # не открывается вообще
STUB = "stub"        # открывается, но там пусто или «в разработке»
PARKED = "parked"    # парковка регистратора / домен на продажу
LIVE = "live"        # нормальный работающий сайт
UNKNOWN = "unknown"  # не смогли проверить (блокирует ботов и т.п.)

LABELS = {
    DEAD: "сайт не открывается",
    STUB: "заглушка вместо сайта",
    PARKED: "домен припаркован",
    LIVE: "рабочий сайт",
    UNKNOWN: "проверить вручную",
}

# Маркеры заглушек и парковок в тексте страницы.
STUB_MARKERS = (
    "сайт в разработке", "страница в разработке", "в разработке",
    "сайт находится в разработке", "скоро открытие", "скоро здесь",
    "coming soon", "under construction", "site is under construction",
    "страница не найдена", "ничего не найдено", "default web page",
    "тестовая страница", "it works!", "welcome to nginx", "apache2 default",
    "index of /", "заглушка",
)
PARKED_MARKERS = (
    "домен припаркован", "domain is parked", "parked domain", "домен продаётся",
    "домен продается", "купить домен", "this domain is for sale", "buy this domain",
    "срок регистрации домена истёк", "срок регистрации домена истек",
    "домен не делегирован", "hosting expired", "хостинг приостановлен",
    "аккаунт заблокирован", "услуга приостановлена", "reg.ru/domain",
)

# Страница, которую нам не отдали: фильтр сети, антибот, капча. Сайт при этом
# может быть совершенно живым — просто мы его не увидели.
BLOCKED_MARKERS = (
    "has been blocked", "access denied", "доступ запрещён", "доступ запрещен",
    "attention required", "cloudflare", "проверка браузера", "checking your browser",
    "captcha", "are you a robot", "ddos-guard", "запрос заблокирован",
    "request blocked", "403 forbidden",
)

# Признаки одностраничника на JS: разметки почти нет, весь контент рисует скрипт.
_SPA_RE = re.compile(
    r'<div[^>]+id=["\'](root|app|__next|__nuxt)["\']|window\.__(INITIAL|NUXT|NEXT)',
    re.I,
)
_SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=", re.I)

_TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _decode(raw, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    try:
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    except (OSError, zlib.error):
        pass
    charset = "utf-8"
    ctype = headers.get("Content-Type", "")
    match = re.search(r"charset=([\w-]+)", ctype, re.I)
    if match:
        charset = match.group(1)
    text = raw.decode(charset, "replace")
    if "charset" not in ctype:
        meta = re.search(r'charset=["\']?([\w-]+)', text[:2000], re.I)
        if meta and meta.group(1).lower() not in ("utf-8", "utf8"):
            text = raw.decode(meta.group(1), "replace")
    return text


def _visible_text(html_text):
    """Текст без скриптов и тегов — чтобы измерить, есть ли на странице контент."""
    body = _TAG_RE.sub(" ", html_text)
    body = _ANY_TAG_RE.sub(" ", body)
    return _WS_RE.sub(" ", body).strip()


def _fetch(url, timeout):
    """Один заход за страницей. Возвращает (код, финальный_url, текст) или бросает."""
    ctx = ssl.create_default_context()
    # Часть небольших сайтов живёт на просроченных сертификатах — для нас это
    # всё равно «сайт открывается», поэтому проверку сертификата не делаем.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers={
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
        raw = response.read(400_000)
        return response.status, response.geturl(), _decode(raw, response.headers)


def check_url(url, timeout=None):
    """Вернуть {'status', 'label', 'code', 'title', 'chars', 'final_url', 'note'}.

    Осторожничаем сознательно: лучше пометить сомнительный сайт как «проверить
    вручную», чем сказать владельцу рабочего сайта, что он не работает.
    """
    result = {"url": url, "status": UNKNOWN, "code": None, "title": "",
              "chars": 0, "final_url": "", "note": ""}
    if not url:
        result["label"] = LABELS[UNKNOWN]
        return result
    if "://" not in url:
        url = "http://" + url

    timeout = timeout or 15
    text = None
    for attempt in (1, 2):  # разовый сбой или 5xx — не приговор, пробуем второй раз
        try:
            result["code"], result["final_url"], text = _fetch(url, timeout)
            break
        except urllib.error.HTTPError as exc:
            result["code"] = exc.code
            if exc.code in (401, 403, 405, 429):
                result["status"] = UNKNOWN
                result["note"] = f"HTTP {exc.code}, сайт закрыт от автопроверки"
                result["label"] = LABELS[UNKNOWN]
                return result
            if exc.code >= 500 and attempt == 1:
                continue  # второй заход
            result["status"] = DEAD
            result["note"] = (f"HTTP {exc.code}"
                              + (", возможно временно" if exc.code >= 500 else ""))
            result["label"] = LABELS[DEAD]
            return result
        except (urllib.error.URLError, TimeoutError, ssl.SSLError,
                ConnectionError, OSError) as exc:
            if attempt == 1:
                continue
            result["status"] = DEAD
            result["note"] = str(getattr(exc, "reason", exc))[:80]
            result["label"] = LABELS[DEAD]
            return result
        except Exception as exc:  # экзотика вроде битой кодировки в заголовках
            result["status"] = UNKNOWN
            result["note"] = str(exc)[:80]
            result["label"] = LABELS[UNKNOWN]
            return result

    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    result["title"] = _WS_RE.sub(" ", title.group(1)).strip()[:120] if title else ""

    visible = _visible_text(text)
    result["chars"] = len(visible)
    title_low = result["title"].lower()
    head_low = visible[:1200].lower()
    full_low = (title_low + " " + visible[:6000]).lower()

    def stub_marker():
        """Маркер заглушки, но только там, где он что-то значит."""
        for m in STUB_MARKERS:
            if m in title_low:
                return m
            # В теле — только на короткой странице: на живом сайте фраза
            # «в разработке» может быть просто частью текста об услугах.
            if result["chars"] < 1500 and m in head_low:
                return m
        return None

    if any(m in full_low for m in BLOCKED_MARKERS) and result["chars"] < 2000:
        result["status"] = UNKNOWN
        result["note"] = "страницу отдал фильтр или антибот, а не сам сайт"
    elif any(m in full_low for m in PARKED_MARKERS):
        result["status"] = PARKED
    elif (marker := stub_marker()):
        result["status"] = STUB
        result["note"] = f"на странице «{marker}»"
    elif result["chars"] < 400:
        # Пусто в HTML — либо правда заглушка, либо всё рисует JavaScript.
        if _SPA_RE.search(text) or len(_SCRIPT_SRC_RE.findall(text)) >= 3:
            result["status"] = UNKNOWN
            result["note"] = "контент рисуется скриптом, глазами надёжнее"
        else:
            result["status"] = STUB
            result["note"] = f"на странице всего {result['chars']} символов текста"
    else:
        result["status"] = LIVE

    result["label"] = LABELS[result["status"]]
    return result


def check_many(urls, workers=12, timeout=15, on_done=None):
    """Проверить пачку адресов параллельно. Возвращает {url: результат}."""
    out = {}
    urls = [u for u in dict.fromkeys(urls) if u]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_url, u, timeout): u for u in urls}
        for i, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            url = futures[future]
            try:
                out[url] = future.result()
            except Exception as exc:
                out[url] = {"url": url, "status": UNKNOWN, "note": str(exc)[:80],
                            "label": LABELS[UNKNOWN], "code": None, "title": "",
                            "chars": 0, "final_url": ""}
            if on_done:
                on_done(i, len(urls), out[url])
    for value in out.values():
        value.setdefault("label", LABELS[value["status"]])
    return out


def needs_site(lead_status, live_status):
    """Итоговый вердикт: стоит ли предлагать этому бизнесу сайт.

    Возвращает (нужен_ли, короткая_причина).
    """
    if lead_status == "none":
        return True, "сайта нет вообще"
    if lead_status == "weak":
        return True, "вместо сайта соцсети или конструктор"
    if live_status in (DEAD, STUB, PARKED):
        return True, LABELS[live_status]
    if live_status == UNKNOWN:
        return None, "сайт есть, но проверить не удалось"
    return False, "рабочий сайт уже есть"
