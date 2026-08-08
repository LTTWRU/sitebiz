"""Классификация «есть ли у бизнеса нормальный сайт»."""

import re
import urllib.parse

# Конструкторы и бесплатные поддомены: формально сайт есть, но продавать новый — можно.
BUILDER_HOSTS = (
    "clients.site",  # бесплатный сайт-визитка от самого 2ГИС
    "taplink.cc",
    "taplink.ru",
    "tilda.ws",
    "wixsite.com",
    "ucoz.ru",
    "ucoz.net",
    "narod.ru",
    "nethouse.ru",
    "a5.ru",
    "umi.ru",
    "business.site",
    "mozello.ru",
    "flexbe.ru",
    "site123.me",
    "webnode.ru",
    "jimdosite.com",
    "sitebuilder.ru",
    "bitrix24.site",
    "shopify.com",
    "ecwid.com",
    "prodamus.ru",
    "getcourse.ru",
    "notion.site",
    "github.io",
)

# Соцсети и мессенджеры — это не сайт.
SOCIAL_HOSTS = (
    "vk.com",
    "vk.ru",
    "instagram.com",
    "facebook.com",
    "ok.ru",
    "t.me",
    "telegram.me",
    "wa.me",
    "whatsapp.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "dzen.ru",
    "max.ru",
    "pinterest.com",
    "twitter.com",
    "x.com",
)

# Агрегаторы и каталоги — чужие площадки, а не собственный сайт.
DIRECTORY_HOSTS = (
    "2gis.ru",
    "2gis.com",
    "yandex.ru",
    "yandex.com",
    "google.com",
    "zoon.ru",
    "prodoctorov.ru",
    "docdoc.ru",
    "napopravku.ru",
    "avito.ru",
    "yell.ru",
    "flamp.ru",
    "hh.ru",
    "otzovik.com",
    "irecommend.ru",
    "delivery-club.ru",
    "eda.yandex.ru",
    "ozon.ru",
    "wildberries.ru",
    "restoclub.ru",
    "tripadvisor.ru",
    "booking.com",
    "sberbank.ru",
    "gosuslugi.ru",
)

WEBSITE_TYPES = {"website", "site", "home_page"}
SOCIAL_TYPES = {
    "vkontakte",
    "instagram",
    "facebook",
    "odnoklassniki",
    "twitter",
    "youtube",
    "telegram",
    "whatsapp",
    "viber",
    "tiktok",
    "max",
    "icq",
    "skype",
}

# Итоговые статусы.
NONE = "none"  # сайта нет вообще
WEAK = "weak"  # вместо сайта соцсеть, конструктор или каталог
HAS = "has"  # свой полноценный сайт

STATUS_LABELS = {
    NONE: "нет сайта",
    WEAK: "нет нормального сайта",
    HAS: "сайт есть",
}


def host_of(url: str) -> str:
    """Домен без www из произвольной ссылки."""
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def _matches(host: str, patterns) -> bool:
    return any(host == p or host.endswith("." + p) for p in patterns)


def clean_url(contact: dict) -> str:
    """Достать «чистый» адрес из контакта, минуя редирект link.2gis.ru."""
    for key in ("url", "value", "text"):
        candidate = (contact.get(key) or "").strip()
        if not candidate:
            continue
        if "link.2gis.ru" in candidate:
            # В редиректе настоящая ссылка идёт после последнего "?".
            tail = candidate.split("?", 1)[-1]
            if tail.startswith("http"):
                candidate = tail
            else:
                continue
        if candidate.startswith("http") or "." in candidate:
            # У ссылок мессенджеров 2ГИС дописывает свой текст сообщения — режем.
            host = host_of(candidate)
            if host in ("wa.me", "t.me", "telegram.me", "api.whatsapp.com"):
                candidate = candidate.split("?", 1)[0]
            return candidate
    return ""


def extract_contacts(item: dict) -> dict:
    """Разложить contact_groups карточки на телефоны, сайты, соцсети и почту."""
    phones, sites, socials, emails = [], [], [], []

    for group in item.get("contact_groups") or []:
        for contact in group.get("contacts") or []:
            ctype = (contact.get("type") or "").lower()
            if ctype == "phone":
                value = contact.get("value") or contact.get("text")
                if value and value not in phones:
                    phones.append(value)
            elif ctype == "email":
                value = contact.get("value") or contact.get("text")
                if value and value not in emails:
                    emails.append(value)
            elif ctype in WEBSITE_TYPES:
                url = clean_url(contact)
                if url and url not in sites:
                    sites.append(url)
            elif ctype in SOCIAL_TYPES:
                url = clean_url(contact)
                if url:
                    entry = {"type": ctype, "url": url}
                    if entry not in socials:
                        socials.append(entry)

    return {"phones": phones, "sites": sites, "socials": socials, "emails": emails}


def classify(sites: list, socials: list) -> tuple:
    """Вернуть (статус, пояснение) по списку сайтов и соцсетей."""
    real, builders, junk = [], [], []

    for url in sites:
        host = host_of(url)
        if not host:
            continue
        if _matches(host, SOCIAL_HOSTS) or _matches(host, DIRECTORY_HOSTS):
            junk.append(host)
        elif _matches(host, BUILDER_HOSTS):
            builders.append(host)
        else:
            real.append(host)

    if real:
        return HAS, ", ".join(sorted(set(real)))
    if builders:
        return WEAK, "конструктор: " + ", ".join(sorted(set(builders)))
    if junk:
        return WEAK, "вместо сайта каталог/соцсеть: " + ", ".join(sorted(set(junk)))
    if socials:
        kinds = sorted({s["type"] for s in socials})
        return WEAK, "только соцсети: " + ", ".join(kinds)
    return NONE, "контактов сайта нет"


_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:ru|рф|com|net|org|su|io|site|store|shop|online|pro|club|info|biz))\b",
    re.IGNORECASE,
)


def find_domain_in_text(*texts: str) -> str:
    """Иногда владелец пишет сайт прямо в описании — вылавливаем и такое."""
    for text in texts:
        if not text:
            continue
        match = _DOMAIN_RE.search(text)
        if match:
            host = match.group(1).lower()
            if not _matches(host, SOCIAL_HOSTS + DIRECTORY_HOSTS):
                return host
    return ""
